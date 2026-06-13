import asyncio
import json
import os
import re
import subprocess
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm import tqdm

EMAIL = "divyanshbansal4224@gmail.com"
BASE_URL = "https://www.3donlinefilms.com"
SEARCH_URL_MAIN = "https://www.3donlinefilms.com/home"
LOGIN_URL = "https://www.3donlinefilms.com/login.php"
FINAL_JSON_FILE = "zNew/finalData.json"
BLACKLIST_FILE = "zNew/blacklist.json"
TEMP_DOWNLOAD_DIR = r"C:\Users\divya\Downloads\3Dmovies_temp"
RCLONE_REMOTE_NAME = "gdrive"
RCLONE_FOLDER_PATH = "3DMovies"


def upload_and_get_id(local_filepath, filename):
    destination = f"{RCLONE_REMOTE_NAME}:{RCLONE_FOLDER_PATH}/{filename}"
    print(f"[📤] Uploading via rclone to -> {destination}")
    cmd_upload = ["rclone", "copyto", local_filepath, destination, "-P"]
    try:
        subprocess.run(cmd_upload, capture_output=True, text=True, check=True)
        print(f"✅ Upload successful!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Rclone copy operations failed:\n{e.stderr}")
        return None
    except FileNotFoundError:
        print("❌ Error: 'rclone' executable not found in your system PATH variables.")
        return None
    print(f"[🔗] Fetching Drive ID via rclone link...")
    cmd_link = ["rclone", "link", destination]
    try:
        result = subprocess.run(cmd_link, capture_output=True, text=True, check=True)
        link = result.stdout.strip()
        match = re.search(r"(?:id=|/d/)([a-zA-Z0-9-_]{25,})", link)
        if match:
            drive_id = match.group(1)
            print(f"🆔 Extracted Drive ID: {drive_id}")
            return drive_id
        else:
            print(f"⚠️ Could not extract ID from rclone link result: {link}")
            return None
    except subprocess.CalledProcessError as e:
        print(
            f"⚠️ Rclone link failed (Folder or file may not be publicly linkable yet): {e.stderr}"
        )
        return None


def crawl_new_movie_links(existing_player_urls, blacklist_urls):
    print("[~] Crawling home pages for new movies...")
    new_movies = []
    seen_this_session = set()
    page_num = 0
    while True:
        search_url = f"{SEARCH_URL_MAIN.rstrip('/')}/page/{page_num}/"
        try:
            response = requests.get(
                search_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=20,
            )
            if response.status_code != 200:
                break
        except Exception:
            break
        soup = BeautifulSoup(response.text, "html.parser")
        widget_main = soup.select_one("div.widget.main")
        if not widget_main:
            break
        page_links_found = False
        for a in widget_main.select('a[href*="/player.php?title="]'):
            href = a.get("href")
            if not href:
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url == f"{BASE_URL}/player.php?title=":
                continue
            if (
                full_url not in existing_player_urls
                and full_url not in seen_this_session
                and full_url not in blacklist_urls
            ):
                seen_this_session.add(full_url)
                display_title = href.split("title=")[-1].replace("+", " ")
                new_movies.append({"title": display_title, "player_url": full_url})
                page_links_found = True
            elif full_url in existing_player_urls:
                page_links_found = True
        if not page_links_found:
            break
        page_num += 1
    return new_movies


async def login(page):
    await page.goto(LOGIN_URL, wait_until="commit")
    await page.fill('input[name="user"]', EMAIL)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("load")


async def sniff_stream_url(context, url):
    page = await context.new_page()
    media_found_future = asyncio.get_running_loop().create_future()

    def on_request(request):
        if "play.php" in request.url:
            if not media_found_future.done():
                media_found_future.set_result(request.url)

    page.on("request", on_request)
    try:
        asyncio.create_task(page.goto(url, wait_until="commit"))
        try:
            found_url = await asyncio.wait_for(media_found_future, timeout=15)
            return found_url
        except asyncio.TimeoutError:
            return None
    except Exception:
        return None
    finally:
        await page.close()


def extract_page_data(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    extracted_fields = {
        "url": "",
        "name": "",
        "description": "",
        "thumbnailUrl": "",
        "duration": "",
        "context": "",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return extracted_fields
        soup = BeautifulSoup(response.text, "html.parser")
        art_content_div = soup.select_one(".art-content")
        if art_content_div:
            extracted_fields["context"] = art_content_div.get_text(
                separator=" ", strip=True
            )
        json_ld_tags = soup.find_all("script", type="application/ld+json")
        for tag in json_ld_tags:
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict) and data.get("@type") == "VideoObject":
                    extracted_fields["url"] = data.get("url", "")
                    extracted_fields["name"] = data.get("name", "")
                    extracted_fields["description"] = data.get("description", "")
                    extracted_fields["thumbnailUrl"] = data.get("thumbnailUrl", "")
                    extracted_fields["duration"] = data.get("duration", "")
                    break
            except Exception:
                continue
        return extracted_fields
    except Exception:
        return extracted_fields


def download_file(url, filename, session_cookies):
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    full_save_path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
    cookies_dict = {c["name"]: c["value"] for c in session_cookies}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": BASE_URL,
    }
    try:
        with requests.get(
            url, cookies=cookies_dict, headers=headers, stream=True, timeout=60
        ) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            custom_format = "📥 {desc:<12} |{bar}| {percentage:3.0f}% ({n_fmt}/{total_fmt}) [{rate_fmt}]"
            with tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc=filename[:12],
                bar_format=custom_format,
                leave=False,
            ) as pbar:
                with open(full_save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
        return full_save_path
    except Exception as e:
        print(f"\n❌ Local write block failed for {filename}: {e}")
        return None


async def main():
    if os.path.exists(FINAL_JSON_FILE):
        with open(FINAL_JSON_FILE, "r", encoding="utf-8") as f:
            try:
                master_json_data = json.load(f)
            except json.JSONDecodeError:
                master_json_data = []
    else:
        master_json_data = []
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            try:
                blacklist_data = json.load(f)
            except json.JSONDecodeError:
                blacklist_data = []
    else:
        blacklist_data = []
    existing_player_urls = {
        item["player_url"] for item in master_json_data if "player_url" in item
    }
    new_movies = crawl_new_movie_links(existing_player_urls, blacklist_data)
    if not new_movies:
        print(
            "\n🎉 Everything is up to date! finalData.json contains all processed items."
        )
        return
    print(f"\n🚀 Found {len(new_movies)} new video paths to process.")
    for movie in new_movies:
        print(f"  - {movie['title']}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        login_page = await context.new_page()
        print("[🔐] Authorizing connection state...")
        await login(login_page)
        await login_page.close()
        session_cookies = await context.cookies()
        for idx, item in enumerate(new_movies, 1):
            print(f"\n" + "=" * 60)
            print(f"🎬 Processing Film [{idx}/{len(new_movies)}]: {item['title']}")
            print("=" * 60)
            stream_url = await sniff_stream_url(context, item["player_url"])
            if not stream_url:
                print(
                    f"⚠️ Timeout: Could not find valid network token for {item['title']}. Skipping."
                )
                continue
            print(f"🔍 Stream URL found: {stream_url}")
            page_data = extract_page_data(item["player_url"])
            print(f"📄 Extracted Page Data: {json.dumps(page_data)}")
            local_filepath = download_file(
                stream_url, item["title"] + ".mp4", session_cookies
            )
            print(
                f"📁 Local file path: {local_filepath if local_filepath else 'Download failed'}"
            )
            if local_filepath and os.path.exists(local_filepath):
                drive_id = upload_and_get_id(local_filepath, item["title"] + ".mp4")
                print(
                    f"Upload and ID retrieval result: {'Success' if drive_id else 'Failed'}"
                )
                try:
                    print(f"🗑️ Local temp file removed: {local_filepath}")
                except OSError:
                    pass
                if drive_id:
                    new_clean_record = {
                        "player_url": item["player_url"],
                        "url": page_data["url"],
                        "name": (
                            page_data["name"] if page_data["name"] else item["title"]
                        ),
                        "description": page_data["description"],
                        "thumbnailUrl": page_data["thumbnailUrl"],
                        "duration": page_data["duration"],
                        "context": page_data["context"],
                        "gdrive_id": drive_id,
                    }
                    master_json_data.append(new_clean_record)
                    with open(FINAL_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump(master_json_data, f, indent=4, ensure_ascii=False)
                    print(f"💾 finalData.json updated completely for: {item['title']}")
        await browser.close()
    print("\n🏁 Integration cycle completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
