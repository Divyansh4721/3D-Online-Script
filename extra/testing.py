import asyncio
import json
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
EMAIL = "divyanshbansal4224@gmail.com"
BASE_URL = "https://www.3donlinefilms.com"
SEARCH_URL_MAIN = "https://www.3donlinefilms.com/search=Marvel"
LOGIN_URL = "https://www.3donlinefilms.com/login.php"


def get_player_urls():
    print("Fetching search results from all pages...")
    player_urls = []
    seen = set()
    page_num = 0
    while True:
        search_url = (
            f"{SEARCH_URL_MAIN}/page/{page_num}/"
        )
        print(f"Checking page {page_num}: {search_url}")
        try:
            response = requests.get(
                search_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed on page {page_num}: {e}")
            break
        soup = BeautifulSoup(response.text, "html.parser")
        widget_main = soup.select_one("div.widget.main")
        if not widget_main:
            print("div.widget.main not found, stopping.")
            break
        page_links = []
        for a in widget_main.select('a[href*="/player.php?title="]'):
            href = a.get("href")
            if not href:
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url not in seen:
                seen.add(full_url)
                page_links.append(full_url)
        # Stop when a page contains no matching links
        if not page_links:
            print(f"No player URLs found on page {page_num}. Stopping.")
            break
        print(f"Found {len(page_links)} URLs on page {page_num}")
        player_urls.extend(page_links)
        page_num += 1
    print(f"Total unique player URLs found: {len(player_urls)}")
    return player_urls


async def login(page):
    print("Logging in...")
    await page.goto(LOGIN_URL, wait_until="commit")
    await page.fill('input[name="user"]', EMAIL)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("load")
    print("Login completed")


async def process_url(context, url):
    print(f"\nProcessing: {url}")
    page = await context.new_page()
    media_found_future = asyncio.get_running_loop().create_future()

    def on_request(request):
        if "play.php" in request.url:
            media_data = {
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
            }
            if not media_found_future.done():
                media_found_future.set_result(media_data)
    page.on("request", on_request)
    try:
        asyncio.create_task(
            page.goto(url, wait_until="commit")
        )
        try:
            found_target = await asyncio.wait_for(
                media_found_future,
                timeout=15
            )
            print("  -> SUCCESS")
            return {
                "page_url": url,
                "status": "success",
                "media_request": found_target
            }
        except asyncio.TimeoutError:
            print("  -> TIMEOUT")
            return {
                "page_url": url,
                "status": "timeout",
                "media_request": None
            }
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {
            "page_url": url,
            "status": "error",
            "error": str(e)
        }
    finally:
        await page.close()


async def main():
    player_urls = get_player_urls()
    player_urls = [
        url for url in player_urls
        if url != "https://www.3donlinefilms.com/player.php?title="
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )
        context = await browser.new_context()
        login_page = await context.new_page()
        await login(login_page)
        await login_page.close()
        results = []
        for url in player_urls:
            result = await process_url(context, url)
            results.append(result)
        await browser.close()
    with open(
        "network_requests.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(results, f, indent=2)
    print(
        f"\nSaved {len(results)} results to network_requests.json"
    )
if __name__ == "__main__":
    asyncio.run(main())
