import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

# --- CONFIGURATION ---
BASE_URL = "https://www.3donlinefilms.com"
SEARCH_URL_MAIN = "https://www.3donlinefilms.com/home"
FILE_PATH = "all3dmovies.txt"


def load_existing_movies(file_path):
    """Reads existing URLs from the file to prevent duplicates and find new additions."""
    if not os.path.exists(file_path):
        return set()

    print(f"[~] Loading existing movies from {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        # Read lines, strip whitespace, and filter out empty lines
        return {line.strip() for line in f if line.strip()}


def get_player_urls(existing_urls):
    """Scrapes the pages and yields ONLY URLs that aren't in the existing text file."""
    print(f"[~] Crawling directory for: {SEARCH_URL_MAIN}")
    new_urls = []
    seen_this_session = set()
    page_num = 0

    while True:
        # Construct the paginated URL
        search_url = f"{SEARCH_URL_MAIN.rstrip('/')}/page/{page_num}/"
        print(f"[~] Fetching page: {search_url}")
        try:
            response = requests.get(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                },
                timeout=20,
            )
            if response.status_code != 200:
                break
        except Exception:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        widget_main = soup.select_one("div.widget.main")

        # If the expected container isn't found, stop crawling
        if not widget_main:
            break

        page_links_found = False

        # Extract the anchor tags targeting the movie page URLs
        for a in widget_main.select('a[href*="/player.php?title="]'):
            href = a.get("href")
            if not href:
                continue

            full_url = urljoin(BASE_URL, href)

            # Skip empty or broken title queries
            if full_url == f"{BASE_URL}/player.php?title=":
                continue

            # Check against local file database and current session cache
            if (
                full_url not in existing_urls
                and full_url not in seen_this_session
            ):
                seen_this_session.add(full_url)
                new_urls.append(full_url)
                page_links_found = True
            elif full_url in existing_urls:
                # If we encounter an old link, we flag that we found links on the page,
                # but we don't save it as a new movie.
                page_links_found = True

        # If absolutely no valid movie layout links are found on this pagination, stop
        if not page_links_found:
            break

        page_num += 1

    return new_urls


def save_new_movies(file_path, new_urls):
    """Appends newly discovered movie URLs to the text file."""
    if not new_urls:
        return
    with open(file_path, "a", encoding="utf-8") as f:
        for url in new_urls:
            f.write(url + "\n")
    print(f"[+] Successfully appended {len(new_urls)} new URLs to {file_path}")


if __name__ == "__main__":
    # 1. Load what we already have
    old_movies = load_existing_movies(FILE_PATH)

    # 2. Extract only the newly published movie URLs
    new_movies = get_player_urls(old_movies)

    # 3. Print the differences directly to your log
    print("\n" + "=" * 60)
    print(f" LOG DIFFERENCE REPORT: {len(new_movies)} NEW MOVIES FOUND")
    print("=" * 60)

    if new_movies:
        for url in new_movies:
            print(f"[NEW] {url}")
        print("-" * 60)

        # 4. Optional: Update your master database file so they aren't 'new' next run
        save_new_movies(FILE_PATH, new_movies)
    else:
        print("[i] No new items discovered. Everything is up to date.")
        print("-" * 60)