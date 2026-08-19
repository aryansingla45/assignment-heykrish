"""
Orchestrator script for the data pipeline.

Fetches data from the API and loads it into the local database.
"""
import logging
from src.api_client import fetch_all_categories
from src.loader import init_db, load_products
from src.config import DB_PATH

logger = logging.getLogger(__name__)

def run_ingest():
    """Run the full ingestion pipeline."""
    logger.info("Starting ingest → %s", DB_PATH)
    
    # 1. Initialize Database
    conn = init_db()
    
    # 2. Fetch all data from API
    results = fetch_all_categories()
    
    # 3. Load into SQLite
    for category, products in results.items():
        if products:
            logger.info("Loading %d items for '%s'", len(products), category)
            load_products(conn, products)
            
    conn.close()
    logger.info("Ingest complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    run_ingest()
