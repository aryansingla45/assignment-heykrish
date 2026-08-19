-- Normalized SQLite schema for the Shelf Report

CREATE TABLE IF NOT EXISTS products (
    barcode         TEXT PRIMARY KEY,
    name            TEXT,
    brand           TEXT,           -- normalized: lowercased, whitespace-trimmed
    brand_raw       TEXT,           -- original casing from API
    sugars_100g     REAL,           -- NULL if nutrition data unavailable
    quantity        TEXT,
    last_modified_t INTEGER,        -- Unix timestamp from Open Food Facts
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Junction table for products that belong to multiple categories (e.g. cookies + biscuits)
CREATE TABLE IF NOT EXISTS product_categories (
    barcode     TEXT NOT NULL,
    category    TEXT NOT NULL,
    PRIMARY KEY (barcode, category),
    FOREIGN KEY (barcode) REFERENCES products(barcode) ON DELETE CASCADE
);

-- Index for fast category queries
CREATE INDEX IF NOT EXISTS idx_category ON product_categories(category);
