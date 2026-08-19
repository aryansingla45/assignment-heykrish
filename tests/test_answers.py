"""
Regression tests for Priya's three answers.

These tests intentionally fail if someone re-introduces the 
agency's flawed SQL logic.
"""
import sqlite3
import pytest

from src.loader import init_db, load_products
from src.queries import (
    count_biscuit_products,
    brand_shelf_share,
    sugar_stats,
    data_quality_report,
    get_connection,
)

# Mock data simulating edge cases the agency missed
MOCK_PRODUCTS = [
    {
        "code": "001",
        "product_name": "Biscuit Only",
        "brands": "BrandA",
        "categories_tags": ["en:biscuits"],
        "nutriments": {"sugars_100g": 20.0},
    },
    {
        "code": "002",
        "product_name": "Multi Tag Biscuit",
        "brands": "BrandB",
        "categories_tags": ["en:biscuits", "en:cookies"],
        "nutriments": {"sugars_100g": 30.0},
    },
    {
        "code": "003",
        "product_name": "Chips",
        "brands": "BrandC",
        "categories_tags": ["en:salty-snacks"],
        "nutriments": {"sugars_100g": 5.0},
    },
    {
        "code": "004",
        "product_name": "Impossible Sugar Biscuit",
        "brands": "BrandA",
        "categories_tags": ["en:biscuits"],
        "nutriments": {"sugars_100g": 250.0},  # Error > 100g
    },
    {
        "code": "005",
        "product_name": "No Sugar Biscuit",
        "brands": "BrandB",
        "categories_tags": ["en:biscuits"],
        "nutriments": {},  # Missing
    },
]

@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    load_products(conn, MOCK_PRODUCTS)
    conn.close()
    return db_path


class TestShelfCount:
    
    def test_biscuit_count_uses_distinct_barcodes(self, test_db):
        """Must not double-count product 002 which is both biscuit and cookie."""
        conn = get_connection(test_db)
        count = count_biscuit_products(conn)
        assert count == 4, f"Expected 4 distinct biscuits, got {count}. Possible flat-schema double counting."
        conn.close()

    def test_shelf_share_denominator_is_category_specific(self, test_db):
        """
        BrandA has 2 biscuits out of 4 total biscuits = 50%.
        If denominator uses ALL products (5), it would report 40% (the agency defect).
        """
        conn = get_connection(test_db)
        brands = brand_shelf_share(conn, "biscuits")
        
        brand_a = next(b for b in brands if b["brand"] == "branda")
        assert brand_a["shelf_pct"] == 50.0, "Denominator included non-biscuit products!"
        conn.close()


class TestSugarStats:
    
    def test_sugar_excludes_impossible_values(self, test_db):
        """
        Valid biscuit sugars: 20.0, 30.0. Average should be 25.0.
        Must exclude the 250.0 outlier.
        """
        conn = get_connection(test_db)
        stats = sugar_stats(conn, "biscuits")
        assert stats["avg_sugars"] == 25.0, "Impossible sugar values >100g were included in the average!"
        conn.close()

    def test_sugar_reports_accurate_coverage(self, test_db):
        """
        4 total biscuits. 
        - 1 is missing sugar
        - 1 has impossible sugar (>100)
        Only 2 have valid sugar data. Coverage = 50%.
        """
        conn = get_connection(test_db)
        stats = sugar_stats(conn, "biscuits")
        assert stats["with_sugar_data"] == 2
        assert stats["coverage_pct"] == 50.0
        conn.close()


class TestDataQuality:
    
    def test_multi_category_products_reported(self, test_db):
        """Must identify products sitting in multiple categories."""
        conn = get_connection(test_db)
        report = data_quality_report(conn)
        assert report["products_in_multiple_categories"] == 1  # Product 002
        conn.close()

    def test_sugar_outliers_counted(self, test_db):
        """Must count how many impossible values were dropped."""
        conn = get_connection(test_db)
        report = data_quality_report(conn)
        assert report["sugar_outliers_excluded"] == 1  # Product 004
        conn.close()


class TestRealDatabase:
    """Integration tests to ensure our real data matches expectations."""
    
    @pytest.fixture
    def real_conn(self):
        import os
        from src.config import DB_PATH
        if not os.path.exists(DB_PATH):
            pytest.skip("shelf.db not found — run 'python -m src.ingest' first")
        conn = get_connection(str(DB_PATH))
        yield conn
        conn.close()

    def test_real_biscuit_shelf_shares_sum_correctly(self, real_conn):
        """
        Branded shelf share + unbranded products must equal exactly 100%.
        This proves the denominator is perfectly scoped to the category.
        """
        brands = brand_shelf_share(real_conn, "biscuits")
        total_branded_pct = sum(b["shelf_pct"] for b in brands)
        
        total_biscuits = count_biscuit_products(real_conn)
        unbranded_count = real_conn.execute("""
            SELECT COUNT(DISTINCT p.barcode) FROM products p
            JOIN product_categories pc ON p.barcode = pc.barcode
            WHERE pc.category = 'biscuits' AND p.brand IS NULL
        """).fetchone()[0]
        
        unbranded_pct = unbranded_count * 100.0 / total_biscuits
        
        assert abs((total_branded_pct + unbranded_pct) - 100.0) < 1.0, (
            "Shelf share percentages do not map to 100% — denominator is wrong"
        )
