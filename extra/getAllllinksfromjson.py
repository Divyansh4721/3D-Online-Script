import asyncio
import json
import os
import sys
from playwright.async_api import async_playwright
from tqdm import tqdm

# --- FORCE PLAYWRIGHT GLOBAL BROWSER PATH ---
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expandvars(r"%USERPROFILE%\AppData\Local\ms-playwright")

# --- CONFIGURATION ---
EMAIL = "divyanshbansal4224@gmail.com"
LOGIN_URL = "https://www.3donlinefilms.com/login.php"
INPUT_JSON_FILE = "filteredMovies.json"
OUTPUT_JSON_FILE = "resolved_stream_links.json"

SNIFFER_TIMEOUT = 20000  # 20 seconds timeout per page

async def login(page):
    """Handles background platform authentication."""
    print("[🔐] Logging into active session platform...")
    await page.goto(LOGIN_URL, wait_until="commit")
    await page.fill('input[name="user"]', EMAIL)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("load")
    print("[✅] Login successful.\n")

async def sniff_stream_url(context, movie_title, page_url):
    """Opens a single page instance, sniffs for play.php, and extracts the stream URL."""
    page = await context.new_page()
    media_found_future = asyncio.get_running_loop().create_future()
    
    def on_request(request):
        if "play.php" in request.url:
            if not media_found_future.done():
                media_found_future.set_result(request.url)
                
    page.on("request", on_request)
    
    try:
        # Start navigation
        await page.goto(page_url, wait_until="commit")
        # Wait for the network sniffer to find the play.php URL or timeout
        stream_url = await asyncio.wait_for(media_found_future, timeout=SNIFFER_TIMEOUT / 1000)
        
        return {
            "title": movie_title,
            "page_url": page_url,
            "stream_url": stream_url,
            "status": "success"
        }
    except asyncio.TimeoutError:
        return {
            "title": movie_title,
            "page_url": page_url,
            "stream_url": None,
            "status": "timeout"
        }
    except Exception as e:
        return {
            "title": movie_title,
            "page_url": page_url,
            "stream_url": None,
            "status": f"error: {str(e)}"
        }
    finally:
        await page.close()

async def main():
    movies_to_process = []
    existing_results = []
    mode = "fresh"

    # 1. Check for existing progress / output file
    if os.path.exists(OUTPUT_JSON_FILE):
        print(f"[🔍] Found existing output file '{OUTPUT_JSON_FILE}'. Scanning for timeouts...")
        try:
            with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
            
            movies_to_process = [item for item in existing_results if item.get("status") == "timeout"]
            
            if movies_to_process:
                mode = "retry"
                print(f"[🔄] Found {len(movies_to_process)} timed-out links to process.")
            else:
                print("[✨] Great news! No timed-out items found in the existing file. Nothing to update.")
                return
        except json.JSONDecodeError:
            print(f"[⚠️] Existing '{OUTPUT_JSON_FILE}' is corrupted. Falling back to fresh run.")

    # 2. Fresh Run Setup
    if mode == "fresh":
        print(f"[🚀] Starting fresh run. Loading source file '{INPUT_JSON_FILE}'...")
        if not os.path.exists(INPUT_JSON_FILE):
            print(f"[❌] Error: Input file '{INPUT_JSON_FILE}' not found.")
            sys.exit(1)
            
        with open(INPUT_JSON_FILE, "r", encoding="utf-8") as f:
            try:
                movies_data = json.load(f)
            except json.JSONDecodeError:
                print(f"[❌] Error: Failed to parse '{INPUT_JSON_FILE}'.")
                sys.exit(1)

        for item in movies_data:
            meta = item.get("metadata", {})
            title = meta.get("name") or item.get("title") or "Unknown Title"
            page_url = meta.get("url") or item.get("url")
            if page_url and page_url != "https://www.3donlinefilms.com/player.php?title=":
                movies_to_process.append({"title": title, "page_url": page_url})

    if not movies_to_process:
        print("[⚠️] No video URLs available to process.")
        return

    # 3. Boot Playwright & Login ONCE
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            print(f"\n[❌] Playwright Error: Could not find browser executable binary.\n{e}")
            return
            
        context = await browser.new_context()
        
        # Open an initial page to complete the login sequence
        login_page = await context.new_page()
        await login(login_page)
        # Session cookies are saved in 'context' automatically now
        
        desc_msg = "Retrying Timeouts" if mode == "retry" else "Sniffing Video URLs"
        
        # 4. Processing Loop: Pure 1-by-1 Sequence
        with tqdm(total=len(movies_to_process), desc=desc_msg, unit="film") as pbar:
            for item in movies_to_process:
                title = item.get("title")
                url = item.get("page_url")
                
                # Execute exactly 1 page task and wait for it to finish completely
                result = await sniff_stream_url(context, title, url)
                
                # Immediate Console Printing as we receive it
                pbar.write("--------------------------------------------------")
                pbar.write(f"🎬 Movie: {result['title']}")
                pbar.write(f"📡 Status: {result['status'].upper()}")
                pbar.write(f"🔗 Stream: {result['stream_url']}")
                pbar.write("--------------------------------------------------")
                
                # Update our live results dataset
                if mode == "retry":
                    # Update the specific item inside our existing list
                    for idx, old_item in enumerate(existing_results):
                        if old_item.get("page_url") == url:
                            existing_results[idx] = result
                            break
                    final_output = existing_results
                else:
                    existing_results.append(result)
                    final_output = existing_results
                
                # Live-save progress to disk instantly after each film finishes
                with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                    json.dump(final_output, f, indent=4, ensure_ascii=False)
                    
                pbar.update(1)

        await browser.close()
    
    print("\n🎉 All films processed and tracked successfully!")

if __name__ == "__main__":
    asyncio.run(main())