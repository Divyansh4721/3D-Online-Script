import asyncio
import json
import os
import sys
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm import tqdm
# --- FORCE PLAYWRIGHT GLOBAL BROWSER PATH ---
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expandvars(r"%USERPROFILE%\AppData\Local\ms-playwright")
# --- CONFIGURATION ---
EMAIL = "divyanshbansal4224@gmail.com"
BASE_URL = "https://www.3donlinefilms.com"
LOGIN_URL = "https://www.3donlinefilms.com/login.php"
DOWNLOAD_DIR = r"C:\Users\divya\Downloads\3Dmovies"
def get_player_urls(search_query):
    """Scrapes the search result list pages cleanly from the terminal."""
    print(f"\n[~] Searching directory for: '{search_query}'...")
    player_urls = []
    seen = set()
    page_num = 0
    search_url_main = f"https://www.3donlinefilms.com/search={search_query.replace(' ', '+')}"
    
    while True:
        search_url = f"{search_url_main}/page/{page_num}/"
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
            
        page_links = []
        for a in widget_main.select('a[href*="/player.php?title="]'):
            href = a.get("href")
            if not href:
                continue
            full_url = urljoin(BASE_URL, href)
            
            if full_url == "https://www.3donlinefilms.com/player.php?title=":
                continue
                
            if full_url not in seen:
                seen.add(full_url)
                display_title = href.split("title=")[-1].replace("+", " ")
                page_links.append({"title": display_title, "url": full_url})
                
        if not page_links:
            break
            
        player_urls.extend(page_links)
        page_num += 1
        
    return player_urls
async def login(page):
    """Handles background user authentication."""
    await page.goto(LOGIN_URL, wait_until="commit")
    await page.fill('input[name="user"]', EMAIL)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("load")
async def sniff_url(context, url):
    """Background traces a single movie page to extract the stream URL."""
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
            found_url = await asyncio.wait_for(media_found_future, timeout=12)
            return found_url
        except asyncio.TimeoutError:
            return None
    except Exception:
        return None
    finally:
        await page.close()
def download_file_with_cookies(url, title, session_cookies, position):
    """Downloads the file natively using thread-safe tqdm bars showing exact MB progress."""
    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
    filename = f"{safe_title}.mp4"
    full_save_path = os.path.join(DOWNLOAD_DIR, filename)
    cookies_dict = {cookie['name']: cookie['value'] for cookie in session_cookies}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    }
    try:
        with requests.get(url, cookies=cookies_dict, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            # FIXED: Replaced 'speed_fmt' with 'rate_fmt' to fix Python 3.14/tqdm compatibility
            custom_format = "📥 {desc:<20} |{bar}| {percentage:3.0f}% ({n_fmt}/{total_fmt}) [{rate_fmt}, ETA: {elapsed}<{remaining}]"
            
            with tqdm(
                total=total_size, 
                unit='B', 
                unit_scale=True, 
                desc=safe_title, 
                position=position, 
                bar_format=custom_format,
                leave=False
            ) as pbar:
                with open(full_save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                            
        tqdm.write(f"✅ Finished: {filename}")
        return True
    except Exception as e:
        tqdm.write(f"❌ Failed {filename}: {e}")
        return False
async def download_worker(semaphore, url, title, cookies, position):
    """Worker task that handles shifting the blocking download off the async loop."""
    async with semaphore:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, download_file_with_cookies, url, title, cookies, position)
async def pipeline_worker(semaphore, context, item, session_cookies, position):
    """Manages full concurrent lifecycle of an item."""
    stream_url = await sniff_url(context, item['url'])
    
    if stream_url:
        await download_worker(semaphore, stream_url, item['title'], session_cookies, position)
    else:
        tqdm.write(f"⚠️ [Timeout Sniffing] Could not fetch stream for: {item['title']}")
async def process_selected_movies(movies_to_process):
    """Orchestrates parallel pipelines and assigns separate visual rows to each task."""
    print("\n[🤖] Booting headless background network sniffer...")
    
    MAX_CONCURRENT_DOWNLOADS = 10
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            print(f"\n[❌] Playwright Error: Could not find browser executable.\n{e}")
            return
        context = await browser.new_context()
        login_page = await context.new_page()
        
        print("[🔐] Logging into active session platform...")
        await login(login_page)
        await login_page.close()
        
        session_cookies = await context.cookies()
        
        print("\n🚀 Starting Parallel Downloads:\n")
        
        tasks = [
            pipeline_worker(semaphore, context, item, session_cookies, position=idx) 
            for idx, item in enumerate(movies_to_process, 1)
        ]
        
        await asyncio.gather(*tasks)
                
        await browser.close()
def main_terminal_ui():
    print("=" * 60)
    print("      🎬 NATIVE TERMINAL FILM SNIFFER & DOWNLOADER      ")
    print("=" * 60)
    
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    query = input("\nEnter search keyword (e.g. Marvel, Deadpool): ").strip()
    if not query:
        print("[❌] Query cannot be empty. Exiting.")
        return
        
    movies = get_player_urls(query)
    
    if not movies:
        print("[❌] No items found matching that keyword query.")
        return
        
    print(f"\n[💡] Found {len(movies)} movie results matching '{query}':")
    print("-" * 60)
    for idx, item in enumerate(movies, 1):
        print(f"  [{idx}] {item['title']}")
    print("-" * 60)
    
    print("\nHow would you like to proceed?")
    print("  -> Type numbers separated by commas to pick specific files (e.g. 1,3,5)")
    print("  -> Type 'ALL' to grab every link in the list")
    selection = input("\nYour choice: ").strip().upper()
    
    selected_movies = []
    if selection == "ALL":
        selected_movies = movies
    else:
        try:
            indices = [int(x.strip()) for x in selection.split(",")]
            for idx in indices:
                if 1 <= idx <= len(movies):
                    selected_movies.append(movies[idx - 1])
        except ValueError:
            print("[❌] Invalid entry format. Program halted.")
            return
    if not selected_movies:
        print("[❌] No valid items chosen. Exiting.")
        return
    asyncio.run(process_selected_movies(selected_movies))
if __name__ == "__main__":
    main_terminal_ui()