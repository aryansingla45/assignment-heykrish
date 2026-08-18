"""
Open Food Facts API client with retry, backoff, and pagination.

Fetches Indian food products by category. Handles 503s with exponential
backoff and spaces requests to avoid hammering a free public service.
"""
import time
import logging
import requests

from src.config import (
    API_BASE_URL,
    API_FIELDS,
    USER_AGENT,
    PAGE_SIZE,
    MAX_RETRIES,
    INITIAL_BACKOFF,
    REQUEST_DELAY,
)

logger = logging.getLogger(__name__)


def _fetch_page(category: str, page: int) -> dict:
    """
    Fetch a single page of products for a given category from India.

    Retries on 503 with exponential backoff.
    """
    params = {
        "countries_tags_en": "india",
        "categories_tags_en": category,
        "fields": ",".join(API_FIELDS),
        "page_size": PAGE_SIZE,
        "page": page,
    }
    headers = {"User-Agent": USER_AGENT}

    backoff = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                API_BASE_URL, params=params, headers=headers, timeout=30
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 503:
                logger.warning(
                    "503 on %s page %d (attempt %d/%d), retrying in %.1fs",
                    category, page, attempt, MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            else:
                resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES:
                raise
            logger.warning(
                "Request error on %s page %d (attempt %d/%d): %s",
                category, page, attempt, MAX_RETRIES, e,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    raise RuntimeError(
        f"Failed to fetch {category} page {page} after {MAX_RETRIES} attempts"
    )


def fetch_products(category: str) -> list[dict]:
    """
    Fetch all products for a category from India, paginating automatically.

    Returns a list of raw product dicts from the API.
    """
    all_products = []
    page = 1

    logger.info("Fetching category: %s", category)

    while True:
        data = _fetch_page(category, page)
        products = data.get("products", [])
        page_count = data.get("page_count", 0)
        total = data.get("count", 0)

        logger.info(
            "  page %d/%d — got %d products (total: %d)",
            page, page_count, len(products), total,
        )

        all_products.extend(products)

        if page >= page_count or not products:
            break

        page += 1
        time.sleep(REQUEST_DELAY)  # Don't hammer the API

    logger.info(
        "Fetched %d products for category '%s'", len(all_products), category
    )
    return all_products


def fetch_all_categories() -> dict[str, list[dict]]:
    """
    Fetch products for all target categories.

    Returns {category: [product_dicts]}.
    """
    from src.config import TARGET_CATEGORIES

    results = {}
    for i, category in enumerate(TARGET_CATEGORIES):
        results[category] = fetch_products(category)
        # Delay between categories too
        if i < len(TARGET_CATEGORIES) - 1:
            time.sleep(REQUEST_DELAY)

    total = sum(len(v) for v in results.values())
    logger.info("Total raw product records fetched: %d", total)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Testing Open Food Facts API client...")
    # Fetch just 'chocolates' as a quick test since it's the smallest category (around 200 products)
    products = fetch_products("chocolates")
    print(f"\nSuccessfully fetched {len(products)} chocolates!")
    if products:
        print(f"Example product: {products[0].get('product_name')} by {products[0].get('brands')}")
