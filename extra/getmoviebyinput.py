import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- CONFIGURATION ---
BASE_URL = "https://www.3donlinefilms.com"


def get_player_urls(search_query):
    """Scrapes the search result list pages and returns a flat list of page URL strings."""
    print(f"[~] Searching directory for: '{search_query}'...")
    player_urls = []
    seen = set()
    page_num = 0
    # Clean up search query for URL formatting
    formatted_query = search_query.replace(" ", "+")
    search_url_main = f"{BASE_URL}/search={formatted_query}"
    while True:
        search_url = f"{search_url_main}/page/{page_num}/"
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
        # If the expected container isn't found, we've hit the end or an invalid page
        if not widget_main:
            break
        page_links_found = False
        # Extracting the anchor tags targeting the movie page URLs
        for a in widget_main.select('a[href*="/player.php?title="]'):
            href = a.get("href")
            if not href:
                continue
            full_url = urljoin(BASE_URL, href)
            # Skip empty or broken title queries
            if full_url == f"{BASE_URL}/player.php?title=":
                continue
            if full_url not in seen:
                seen.add(full_url)
                player_urls.append(full_url)
                page_links_found = True
        # If no new links were extracted from this page, stop iterating
        if not page_links_found:
            break
        page_num += 1
    return player_urls


if __name__ == "__main__":
    print("--- 3D Online Films Scraper Loop Started ---")
    print("Type 'exit' or press Enter on an empty line to quit.\n")

    while True:
        # 1. Ask the user for input again and again
        query = (
            input("Enter search keyword (e.g. Marvel, Deadpool): ")
            .strip()
            .lower()
        )

        # 2. Check for exit conditions
        if not query or query == "exit":
            print("\nExiting script. Goodbye!")
            break

        # 3. Process the query
        movie_urls = get_player_urls(query)

        # 4. Display results
        print(f"\nCollected {len(movie_urls)} page URLs:")
        print("-" * 60)
        for url in movie_urls:
            print(url)
        print("-" * 60)
        print("\n" + "=" * 40 + "\n")  # Visual separator for the next loop