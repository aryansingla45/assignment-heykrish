"""
Idempotent database loader.

Uses SQLite INSERT OR REPLACE to ensure multiple runs don't duplicate data.
Normalizes brand names to prevent case-variation fragmentation.
"""
import sqlite3
import logging
from pathlib import Path

from src.config import TARGET_CATEGORIES, DB_PATH

logger = logging.getLogger(__name__)


def init_db(db_path: str = None) -> sqlite3.Connection:
    """Initialize the database with the defined schema."""
    path = db_path or str(DB_PATH)
    schema_path = Path(__file__).parent / "schema.sql"
    
    conn = sqlite3.connect(path)
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
        
    return conn


def normalize_brand(brand: str | None) -> tuple[str | None, str | None]:
    """
    Given a raw brand string, return (normalized, raw).
    Normalized: lowercased, stripped, first brand only if comma-separated.
    """
    if not brand:
        return None, None
        
    brand = str(brand).strip()
    if not brand:
        return None, None
        
    # Take just the first brand if there are multiple comma-separated ones
    primary_brand = brand.split(",")[0].strip()
    normalized = primary_brand.lower()
    
    return normalized, primary_brand


def load_products(conn: sqlite3.Connection, products: list[dict]):
    """
    Load raw API product dicts into the database idempotently.
    Updates existing barcodes, inserts new ones.
    """
    if not products:
        return
        
    cursor = conn.cursor()
    
    # Using parameterized queries for safety and performance
    product_sql = """
        INSERT OR REPLACE INTO products (
            barcode, name, brand, brand_raw, sugars_100g, 
            quantity, last_modified_t, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """
    
    category_sql = """
        INSERT OR IGNORE INTO product_categories (barcode, category)
        VALUES (?, ?)
    """
    
    products_inserted = 0
    categories_inserted = 0
    
    # We use a transaction for speed and atomicity
    with conn:
        for p in products:
            barcode = p.get("code")
            if not barcode:
                continue
                
            brand_norm, brand_raw = normalize_brand(p.get("brands"))
            
            # Extract sugar (can be missing)
            nutriments = p.get("nutriments", {})
            sugars = nutriments.get("sugars_100g")
            
            # Insert product
            cursor.execute(product_sql, (
                barcode,
                p.get("product_name"),
                brand_norm,
                brand_raw,
                sugars,
                p.get("quantity"),
                p.get("last_modified_t")
            ))
            products_inserted += 1
            
            # Map categories (junction table)
            # A product might have many tags, we only care if they map to our TARGET_CATEGORIES
            tags = p.get("categories_tags", [])
            if not tags:
                continue
                
            for tag in tags:
                # tags usually look like "en:biscuits"
                clean_tag = tag.replace("en:", "").replace("fr:", "").strip().lower()
                if clean_tag in TARGET_CATEGORIES:
                    cursor.execute(category_sql, (barcode, clean_tag))
                    categories_inserted += 1

    logger.info("Loaded %d products and %d category links.", products_inserted, categories_inserted)
