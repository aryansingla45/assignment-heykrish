"""
Configuration constants for the Shelf Report service.
"""
import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "shelf.db"

# Open Food Facts API
API_BASE_URL = "https://world.openfoodfacts.org/api/v2/search"
USER_AGENT = "aryan45/1.0 (aryansingla45@gmail.com)"
PAGE_SIZE = 100

# Target categories (India, snack shelf)
TARGET_CATEGORIES = [
    "biscuits",
    "cookies",
    "salty-snacks",
    "chips-and-fries",
    "chocolates",
]

# Fields to request from the API
API_FIELDS = [
    "code",
    "product_name",
    "brands",
    "categories_tags",
    "quantity",
    "nutriments",
    "last_modified_t",
]

# Retry configuration (Open Food Facts often returns 503 under load)
MAX_RETRIES = 8
INITIAL_BACKOFF = 2.0       # seconds
REQUEST_DELAY = 2.0         # seconds between paginated requests
