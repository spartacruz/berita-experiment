import json
import asyncio
import random
import os
import time
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from newspaper import Article


INPUT_FILE = ".\\1_news-politik\\2_politik_cnn_index_results_filtered.json"
SOURCE_OFFSET = 1020  # Number of items to skip from the beginning
OUTPUT_FILE = ".\\1_news-politik\\3_politik_cnn_articles.json"
CONCURRENCY = 3  # concurrent browser tabs
SAVE_EVERY = 3  # commit to disk every N articles
MAX_RETRIES = 3  # retries per article
DELAY_RANGE = (2.0, 4.0)  # random delay between requests (seconds)
SOURCE_CRAWL_LIMIT: int | None = 1015  # limit source links (e.g. 10), None = no limit


def load_input(filepath):
    """Load the URL index JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing(filepath):
    """Load already-scraped articles for resume support. Returns dict keyed by URL."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {item["url"]: item for item in data}
    except (json.JSONDecodeError, KeyError):
        return {}


def save_results(filepath, results_dict):
    """Atomically write results to JSON file."""
    tmp_file = filepath + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(list(results_dict.values()), f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, filepath)


def parse_with_newspaper(url, html):
    """Use newspaper3k to extract structured article data from raw HTML."""
    article = Article(url)
    article.download(input_html=html)
    article.parse()
    return {"title": article.title or "", "text": article.text}


async def scrape_one(crawler, config, item, semaphore, results, save_counter, lock):
    """Scrape a single article URL with retry + backoff."""
    url = item["url"]

    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Random delay to stagger requests
                await asyncio.sleep(random.uniform(*DELAY_RANGE))

                result = await crawler.arun(url=url, config=config)

                if not result.success:
                    print(
                        f"  [Attempt {attempt}/{MAX_RETRIES}] FAIL {url}: {result.error_message}"
                    )
                    if attempt < MAX_RETRIES:
                        backoff = (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(backoff)
                    continue

                # Parse with newspaper (CPU-bound, run in thread to not block event loop)
                parsed = await asyncio.to_thread(parse_with_newspaper, url, result.html)

                article_data = {
                    "title": parsed["title"] or item.get("title", ""),
                    "url": url,
                    "text": parsed["text"],
                }

                # Thread-safe update
                async with lock:
                    results[url] = article_data
                    save_counter["count"] += 1

                    # Periodic save
                    if save_counter["count"] % SAVE_EVERY == 0:
                        save_results(OUTPUT_FILE, results)
                        print(
                            f"  [SAVED] {len(results)} total articles to {OUTPUT_FILE}"
                        )

                return True

            except Exception as e:
                print(f"  [Attempt {attempt}/{MAX_RETRIES}] ERROR {url}: {e}")
                if attempt < MAX_RETRIES:
                    backoff = (2**attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)

        # All retries exhausted
        print(f"  [SKIPPED] {url} after {MAX_RETRIES} attempts")
        return False


async def main():
    # Load input URLs
    all_items = load_input(INPUT_FILE)
    total_input = len(all_items)
    if SOURCE_OFFSET > 0:
        all_items = all_items[SOURCE_OFFSET:]

    if SOURCE_CRAWL_LIMIT is not None:
        all_items = all_items[:SOURCE_CRAWL_LIMIT]

    end_index = SOURCE_OFFSET + len(all_items)
    if SOURCE_OFFSET > 0:
        print(
            f"Loaded {len(all_items)} URLs from {INPUT_FILE} "
            f"(range [{SOURCE_OFFSET}:{end_index}] of {total_input})"
        )
    else:
        print(
            f"Loaded {len(all_items)} URLs from {INPUT_FILE} (of {total_input} total)"
        )

    # Load existing results for resume
    results = load_existing(OUTPUT_FILE)
    already_done = len(results)
    print(f"Already scraped: {already_done} articles (resume enabled)")

    # Filter pending URLs
    pending = [item for item in all_items if item["url"] not in results]
    print(f"Pending: {len(pending)} articles\n")

    if not pending:
        print("Nothing to scrape. All URLs already processed.")
        return

    # Crawler config — anti-block measures
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        mean_delay=1.5,
        max_range=2.0,
        simulate_user=True,
        override_navigator=True,
    )

    semaphore = asyncio.Semaphore(CONCURRENCY)
    lock = asyncio.Lock()
    save_counter = {"count": 0}
    start_time = time.time()

    async with AsyncWebCrawler(verbose=False) as crawler:
        # Process in chunks to control memory and provide progress updates
        chunk_size = CONCURRENCY * 5  # process 15 at a time
        total_chunks = (len(pending) + chunk_size - 1) // chunk_size

        for chunk_idx in range(total_chunks):
            chunk_start = chunk_idx * chunk_size
            chunk_end = min(chunk_start + chunk_size, len(pending))
            chunk = pending[chunk_start:chunk_end]

            elapsed = time.time() - start_time
            done_so_far = save_counter["count"]
            rate = done_so_far / elapsed if elapsed > 0 else 0
            remaining = len(pending) - done_so_far
            eta_seconds = remaining / rate if rate > 0 else 0
            eta_min = eta_seconds / 60

            offset_label = f" (offset {SOURCE_OFFSET})" if SOURCE_OFFSET > 0 else ""
            print(f"{'='*60}")
            print(
                f"Chunk {chunk_idx + 1}/{total_chunks} "
                f"| Progress: {done_so_far}/{len(pending)} pending "
                f"| Total saved: {len(results)}"
                f"{offset_label} "
                f"| Rate: {rate:.1f}/s "
                f"| ETA: {eta_min:.0f}min"
            )
            print(f"{'='*60}")

            tasks = [
                scrape_one(
                    crawler, config, item, semaphore, results, save_counter, lock
                )
                for item in chunk
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Save after every chunk
            save_results(OUTPUT_FILE, results)

    # Final save
    save_results(OUTPUT_FILE, results)
    elapsed_total = time.time() - start_time
    print(
        f"\nDone! Scraped {save_counter['count']} new articles in {elapsed_total / 60:.1f} minutes"
    )
    print(f"Total articles in {OUTPUT_FILE}: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
