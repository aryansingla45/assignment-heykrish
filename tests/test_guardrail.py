"""
Guardrail tests to mathematically prove the database is safe from injection.

The assignment requires: "one guardrail that still holds if someone deletes
your entire system prompt."

We have two:
1. Code-level: validate_sql() blocks non-SELECT keywords via regex.
2. DB-level: SQLite ?mode=ro connection physically rejects write attempts.
"""
import sqlite3
import pytest

from src.chat import validate_sql, execute_query
from src.loader import init_db, load_products

# ─── 1. Code-Level Guardrail Tests ──────────────────────────────────────────

class TestSQLValidator:
    """Proves the validate_sql() regex correctly blocks destructive statements."""
    
    def test_select_allowed(self):
        assert validate_sql("SELECT COUNT(*) FROM products") == "SELECT COUNT(*) FROM products"

    def test_insert_blocked(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_sql("INSERT INTO products VALUES ('1', '2')")

    def test_update_blocked(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_sql("UPDATE products SET name='hacked'")

    def test_delete_blocked(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_sql("DELETE FROM products")

    def test_drop_blocked(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_sql("DROP TABLE products")

    def test_pragma_blocked(self):
        """PRAGMA can be used to alter DB configs. It must be blocked."""
        with pytest.raises(ValueError, match="Blocked keyword"):
            validate_sql("SELECT 1; PRAGMA table_info(products)")

    def test_subquery_injection_blocked(self):
        """Even if the query starts with SELECT, a nested INSERT must be blocked."""
        with pytest.raises(ValueError, match="Blocked keyword"):
            validate_sql("SELECT * FROM (INSERT INTO evil VALUES ('1'))")


# ─── 2. Database-Level Guardrail Tests ───────────────────────────────────────

class TestReadOnlyConnection:
    """
    Proves that even if the code-level regex is bypassed, the database 
    connection itself is Read-Only and will physically reject writes.
    """
    
    @pytest.fixture
    def mock_db(self, tmp_path):
        """Creates a real database with one row for attack testing."""
        db_path = str(tmp_path / "guardrail_test.db")
        conn = init_db(db_path)
        load_products(conn, [{
            "code": "SAFE001",
            "product_name": "Safe Product",
            "brands": "SafeBrand",
            "categories_tags": ["en:biscuits"],
            "nutriments": {},
        }])
        conn.close()
        return db_path

    def test_readonly_mode_survives_attack(self, mock_db):
        """
        Simulate a bypassed regex and send raw destructive SQL directly 
        to the execute_query engine. The DB-level guardrail MUST stop it.
        """
        attacks = [
            "DROP TABLE products",
            "DELETE FROM products",
            "UPDATE products SET name='hacked'",
            "INSERT INTO products (barcode) VALUES ('evil')",
        ]
        
        for attack_sql in attacks:
            # We temporarily monkeypatch validate_sql to simulate a bypass
            with pytest.MonkeyPatch.context() as m:
                m.setattr("src.chat.validate_sql", lambda x: x)
                
                # The read-only connection must catch it and raise an OperationalError
                with pytest.raises(sqlite3.OperationalError, match="readonly database"):
                    execute_query(attack_sql, mock_db)
        
        # Verify the data completely survived the attack unharmed
        verify_conn = sqlite3.connect(mock_db)
        count = verify_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        name = verify_conn.execute("SELECT name FROM products WHERE barcode='SAFE001'").fetchone()[0]
        verify_conn.close()
        
        assert count == 1, "The product was deleted! Guardrail failed."
        assert name == "Safe Product", "The product was modified! Guardrail failed."
