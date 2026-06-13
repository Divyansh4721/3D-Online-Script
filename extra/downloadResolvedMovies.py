import os
import json
import sys
import requests
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_JSON_FILE = "resolved_stream_links.json"
DOWNLOAD_DIR = r"C:\Users\divya\Downloads\3Dmovies"

# Concurrency Control (5 downloads at a time)
MAX_CONCURRENT_DOWNLOADS = 10

def sanitize_filename(title):
    """Cleans up the movie title to prevent bad character filesystem errors."""
    cleaned = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
    return cleaned if cleaned else "Unknown_Movie"

def download_worker(movie_node, slot_queue):
    """
    Isolated worker task that handles downloading a single stream 
    with its own strictly bounded network connections and file pointers.
    """
    title = movie_node.get("title") or "Unknown Title"
    stream_url = movie_node.get("stream_url")
    
    if not stream_url or movie_node.get("status") != "success":
        return {"title": title, "status": "skipped", "reason": "No valid stream URL"}

    safe_title = sanitize_filename(title)
    filename = f"{safe_title}.mp4"
    full_save_path = os.path.join(DOWNLOAD_DIR, filename)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.3donlinefilms.com"
    }

    # Grab an available terminal row slot position from the queue
    slot_position = slot_queue.get()

    try:
        with requests.get(stream_url, headers=headers, stream=True, timeout=60) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            custom_format = "📥 {desc:<25} |{bar}| {percentage:3.0f}% ({n_fmt}/{total_fmt}) [{rate_fmt}, ETA: {remaining}]"
            
            # Trim display title to keep bars neat
            display_name = filename[:22] + "..." if len(filename) > 25 else filename
            
            with tqdm(
                total=total_size, 
                unit='B', 
                unit_scale=True, 
                desc=display_name, 
                position=slot_position, 
                bar_format=custom_format,
                leave=False
            ) as pbar:
                with open(full_save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                            
        tqdm.write(f"✅ Finished: {filename}")
        return {"title": title, "status": "completed"}
        
    except Exception as e:
        tqdm.write(f"❌ Failed to download [{filename}]: {e}")
        return {"title": title, "status": "failed", "reason": str(e)}
    finally:
        # Crucial: Always return the slot back to the queue, even if the download fails
        slot_queue.put(slot_position)

def main():
    # 1. Verification and Sanity Checks
    if not os.path.exists(INPUT_JSON_FILE):
        print(f"[❌] Error: Linked input file '{INPUT_JSON_FILE}' does not exist.")
        sys.exit(1)

    if not os.path.exists(DOWNLOAD_DIR):
        print(f"[📁] Target folder missing. Creating directory: {DOWNLOAD_DIR}")
        os.makedirs(DOWNLOAD_DIR)

    with open(INPUT_JSON_FILE, "r", encoding="utf-8") as f:
        try:
            links_data = json.load(f)
        except json.JSONDecodeError:
            print(f"[❌] Error: Could not parse JSON out of '{INPUT_JSON_FILE}'.")
            sys.exit(1)

    # 2. Extract Valid Links
    raw_queue = [
        item for item in links_data 
        if item.get("status") == "success" and item.get("stream_url")
    ]

    # 3. Duplicate Checking Filter Layer
    download_queue = []
    skipped_count = 0
    
    for item in raw_queue:
        title = item.get("title") or "Unknown Title"
        safe_title = sanitize_filename(title)
        filename = f"{safe_title}.mp4"
        full_save_path = os.path.join(DOWNLOAD_DIR, filename)
        
        if os.path.exists(full_save_path):
            skipped_count += 1
        else:
            download_queue.append(item)

    print(f"🚀 Initializing Batch Media Downloader Engine.")
    print(f"📦 Total Resolved Files: {len(raw_queue)}")
    print(f"✨ Already Downloaded (Skipped): {skipped_count}")
    print(f"📥 Pending Downloads Remaining: {len(download_queue)}")
    print(f"⚙️  Concurrency Limit: {MAX_CONCURRENT_DOWNLOADS} parallel streams.\n")

    if not download_queue:
        print("[🎉] All files are already downloaded! Exiting cleanly.")
        return

    # 4. Set up the Thread-Safe UI Slot Queue
    slot_queue = queue.Queue()
    for i in range(MAX_CONCURRENT_DOWNLOADS):
        slot_queue.put(i)

    # 5. Thread Execution Engine
    futures_list = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
        for movie_item in download_queue:
            # Submit all tasks. ThreadPoolExecutor controls its own concurrency internally (max_workers=5)
            # and the slot_queue makes sure they pick up available tracking lines safely.
            future = executor.submit(download_worker, movie_item, slot_queue)
            futures_list.append(future)

        # Let them run to completion and handle exceptions gracefully
        for completed_future in as_completed(futures_list):
            try:
                completed_future.result()
            except Exception as e:
                print(f"Thread task exception caught: {e}")

    print("\n🎉 All download tasks settled down completely!")

if __name__ == "__main__":
    main()