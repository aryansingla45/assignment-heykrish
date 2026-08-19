"""
Tests to mathematically prove the loader is idempotent.
"""
import pytest
from src.loader import init_db, load_products, normalize_brand

# A mock product list for testing
MOCK_PRODUCTS = [
    {
        "code": "12345",
        "product_name": "Test Biscuit",
        "brands": "Britannia, OtherBrand",
        "categories_tags": ["en:biscuits", "en:snacks"],
        "nutriments": {"sugars_100g": 25.5},
        "quantity": "100g",
        "last_modified_t": 1600000000
    },
    {
        "code": "67890",
        "product_name": "Salty Chip",
        "brands": " PARLE ",
        "categories_tags": ["en:salty-snacks"],
        "nutriments": {},
        "quantity": "50g",
        "last_modified_t": 1600000001
    }
]


class TestBrandNormalization:
    
    def test_case_normalized(self):
        norm, raw = normalize_brand("BRITANNIA")
        assert norm == "britannia"
        assert raw == "BRITANNIA"
        
    def test_whitespace_stripped(self):
        norm, raw = normalize_brand("  parle  ")
        assert norm == "parle"
        assert raw == "parle"
        
    def test_first_brand_chosen(self):
        norm, raw = normalize_brand("Sunfeast, ITC")
        assert norm == "sunfeast"
        assert raw == "Sunfeast"


class TestIdempotency:
    
    @pytest.fixture
    def test_conn(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = init_db(db_path)
        yield conn
        conn.close()

    def test_load_twice_identical_data(self, test_conn):
        """Proves that running the ingest twice does not duplicate rows."""
        
        # Load once
        load_products(test_conn, MOCK_PRODUCTS)
        
        count_products = test_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert count_products == 2
        
        # Load EXACT same data again
        load_products(test_conn, MOCK_PRODUCTS)
        
        count_products_again = test_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        
        # Still 2!
        assert count_products_again == 2, "Idempotency failed: duplicate rows created!"
        
    def test_updates_existing_data(self, test_conn):
        """Proves that if data changes on the API, our DB updates without duplicating."""
        
        load_products(test_conn, MOCK_PRODUCTS)
        
        # Simulate an API update where the sugar content changed
        updated_mock = dict(MOCK_PRODUCTS[0])
        updated_mock["nutriments"] = {"sugars_100g": 99.9}
        
        load_products(test_conn, [updated_mock])
        
        # Count should still be 2
        count_products = test_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert count_products == 2
        
        # But the sugar should be updated
        sugar = test_conn.execute("SELECT sugars_100g FROM products WHERE barcode='12345'").fetchone()[0]
        assert sugar == 99.9
