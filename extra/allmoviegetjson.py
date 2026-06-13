from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from bs4 import BeautifulSoup
import requests

# --- CONFIGURATION ---
INPUT_FILE = "all3dmovies.txt"
OUTPUT_FILE = "output.json"
MAX_WORKERS = 50  # Number of parallel pages to fetch at once

# Load URLs from text file safely
if os.path.exists(INPUT_FILE):
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        URLS = [line.strip() for line in f if line.strip().startswith("http")]
else:
    print(f"[❌] Error: '{INPUT_FILE}' not found.")
    URLS = []


def scrape_single_url(url):
    """Worker task that handles fetching and parsing a single URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Extract the inner text from class="art-content"
        art_content_div = soup.select_one(".art-content")
        art_text = ""
        if art_content_div:
            # get_text strips tags and normalizes white spaces cleanly
            art_text = art_content_div.get_text(separator=" ", strip=True)

        # 2. Extract the application/ld+json metadata
        json_ld_tags = soup.find_all("script", type="application/ld+json")
        for tag in json_ld_tags:
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict) and data.get("@type") == "VideoObject":
                    # Package both elements together into a single record object
                    return {
                        "metadata": data,
                        "art_content_text": art_text
                    }
            except (json.JSONDecodeError, TypeError):
                continue
                
        # Fallback: If no metadata was found but art-content exists, you can still return it
        if art_text:
            return {
                "metadata": {},
                "art_content_text": art_text
            }
            
    except Exception as e:
        # Silently absorb network drops or timeouts per thread
        pass
    return None


def main():
    if not URLS:
        print("[❌] No valid URLs to process. Exiting.")
        return

    all_metadata = []
    total_urls = len(URLS)

    print(
        f"[~] Spinning up ThreadPoolExecutor with {MAX_WORKERS} workers for {total_urls} URLs..."
    )

    # Execute requests in parallel threads
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all parsing tasks to the thread pool tracker
        future_to_url = {
            executor.submit(scrape_single_url, url): url for url in URLS
        }

        # Handle completed tasks on the fly
        completed_count = 0
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            completed_count += 1
            try:
                result = future.result()
                if result:
                    all_metadata.append(result)
                    # Safely fetch name for terminal print logs
                    movie_name = result.get("metadata", {}).get("name") or "Unknown Movie"
                    print(
                        f"[{completed_count}/{total_urls}] ✅ Extracted: {movie_name}"
                    )
                else:
                    print(
                        f"[{completed_count}/{total_urls}] ⚠️ Failed/Skipped: {url}"
                    )
            except Exception as exc:
                print(f"[{completed_count}/{total_urls}] ❌ Generated error: {exc}")

    # Write collected array to your output file
    print(f"\n[💾] Writing {len(all_metadata)} items to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, indent=4, ensure_ascii=False)

    print("🎉 Complete!")


if __name__ == "__main__":
    main()