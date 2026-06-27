import json
import asyncio
import random
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai import JsonCssExtractionStrategy

BASE_URL = "https://www.cnnindonesia.com/hiburan/indeks/9?page={}"
OUTPUT_FILE = "5_hiburan_cnn_index_results.json"
START_PAGE = 1
END_PAGE = 500
MAX_RETRIES = 3


async def extract_index_url():
    # 1. Define a simple extraction schema
    schema = {
        "name": "News",
        "baseSelector": "article",  # Repeated elements
        "fields": [
            # tambah tag: video, breaking news, etc
            {"name": "tag", "selector": "span.subjudul", "type": "text", "default": ""},
            {"name": "title", "selector": "h2", "type": "text"},
            {
                "name": "url",
                "selector": "a[aria-label='link description']",
                "type": "attribute",
                "attribute": "href",
            },
        ],
    }

    # 2. Create the extraction strategy
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

    # 3. Set up crawler config with anti-block measures
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy,
        # Anti-block: randomized delay between requests
        mean_delay=2.0,
        max_range=3.0,
        # Anti-block: mimic real user behavior
        simulate_user=True,
        override_navigator=True,
    )

    async with AsyncWebCrawler(verbose=True) as crawler:
        for page in range(START_PAGE, END_PAGE + 1):
            url = BASE_URL.format(page)
            print(f"\n{'='*60}")
            print(f"[Page {page}/{END_PAGE}] Crawling: {url}")
            print(f"{'='*60}")

            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    result = await crawler.arun(url=url, config=config)

                    if not result.success:
                        print(
                            f"  [Attempt {attempt}/{MAX_RETRIES}] Crawl failed: {result.error_message}"
                        )
                        if attempt < MAX_RETRIES:
                            backoff = (2**attempt) + random.uniform(0, 1)
                            print(f"  Retrying in {backoff:.1f}s...")
                            await asyncio.sleep(backoff)
                        continue

                    # Parse the extracted JSON
                    data = json.loads(result.extracted_content)
                    if not data:
                        print(f"  [Page {page}] No data extracted, skipping.")
                        success = True
                        break

                    print(f"  Extracted {len(data)} entries")

                    # Commit to JSON file after every page
                    existing_data = []
                    try:
                        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                            existing_data = json.load(f)
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass

                    existing_data.extend(data)

                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(existing_data, f, indent=2, ensure_ascii=False)

                    print(
                        f"  Saved to {OUTPUT_FILE} (total: {len(existing_data)} entries)"
                    )
                    success = True
                    break

                except json.JSONDecodeError as e:
                    print(f"  [Attempt {attempt}/{MAX_RETRIES}] JSON parse error: {e}")
                except IOError as e:
                    print(f"  [Attempt {attempt}/{MAX_RETRIES}] File write error: {e}")
                except Exception as e:
                    print(f"  [Attempt {attempt}/{MAX_RETRIES}] Unexpected error: {e}")

                if attempt < MAX_RETRIES:
                    backoff = (2**attempt) + random.uniform(0, 1)
                    print(f"  Retrying in {backoff:.1f}s...")
                    await asyncio.sleep(backoff)

            if not success:
                print(
                    f"  [Page {page}] Failed after {MAX_RETRIES} attempts, moving to next page."
                )

            # Polite delay between pages (3-6s randomized)
            if page < END_PAGE:
                delay = random.uniform(3.0, 6.0)
                print(f"  Waiting {delay:.1f}s before next page...")
                await asyncio.sleep(delay)

    print(f"\nDone! Results saved to {OUTPUT_FILE}")


asyncio.run(extract_index_url())
