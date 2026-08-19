"""
Analytical queries to answer Priya's three questions:
1. Who is on my shelf?
2. Where does sugar sit?
3. Can I trust this?

Usage:
    python -m src.queries
"""
import sqlite3
import logging
from src.config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Get a read-only database connection for analytics."""
    path = db_path or str(DB_PATH)
    # ?mode=ro ensures we cannot accidentally modify data here
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Q1: Who is on my shelf? ─────────────────────────────────────────────────

def count_biscuit_products(conn: sqlite3.Connection) -> int:
    """How many distinct biscuit products are selling in India?"""
    row = conn.execute("""
        SELECT COUNT(DISTINCT p.barcode) as count
        FROM products p
        JOIN product_categories pc ON p.barcode = pc.barcode
        WHERE pc.category = 'biscuits'
    """).fetchone()
    return row["count"]


def brand_shelf_share(conn: sqlite3.Connection, category: str = "biscuits") -> list[dict]:
    """
    Which brands own the most products in a category?
    Shelf percentage is computed ONLY against the specified category's total.
    """
    rows = conn.execute("""
        SELECT
            p.brand,
            MAX(p.brand_raw) as brand_display,
            COUNT(DISTINCT p.barcode) as products,
            ROUND(COUNT(DISTINCT p.barcode) * 100.0 / (
                SELECT COUNT(DISTINCT p2.barcode)
                FROM products p2
                JOIN product_categories pc2 ON p2.barcode = pc2.barcode
                WHERE pc2.category = :category
            ), 2) as shelf_pct
        FROM products p
        JOIN product_categories pc ON p.barcode = pc.barcode
        WHERE pc.category = :category AND p.brand IS NOT NULL
        GROUP BY p.brand
        ORDER BY products DESC
    """, {"category": category}).fetchall()
    return [dict(r) for r in rows]


# ─── Q2: Where does sugar sit? ───────────────────────────────────────────────

def sugar_stats(conn: sqlite3.Connection, category: str = "biscuits") -> dict:
    """
    Sugar per 100g across a category, excluding impossible outliers (>100g).
    """
    # Exclude impossible >100g/100g values
    row = conn.execute("""
        SELECT
            COUNT(DISTINCT p.barcode) as total,
            COUNT(DISTINCT CASE WHEN p.sugars_100g IS NOT NULL 
                                 AND p.sugars_100g <= 100 
                           THEN p.barcode END) as with_sugar_data,
            ROUND(AVG(CASE WHEN p.sugars_100g IS NOT NULL 
                           AND p.sugars_100g <= 100 
                      THEN p.sugars_100g END), 2) as avg_sugars,
            ROUND(MIN(CASE WHEN p.sugars_100g <= 100 
                      THEN p.sugars_100g END), 2) as min_sugars,
            ROUND(MAX(CASE WHEN p.sugars_100g <= 100 
                      THEN p.sugars_100g END), 2) as max_sugars
        FROM products p
        JOIN product_categories pc ON p.barcode = pc.barcode
        WHERE pc.category = :category
    """, {"category": category}).fetchone()

    result = dict(row)

    # Calculate coverage percentage
    result["coverage_pct"] = round(
        result["with_sugar_data"] * 100.0 / result["total"], 1
    ) if result["total"] > 0 else 0

    return result


# ─── Q3: Can I trust this? ───────────────────────────────────────────────────

def data_quality_report(conn: sqlite3.Connection) -> dict:
    """
    Data quality metrics to establish trust.
    """
    total = conn.execute("SELECT COUNT(*) as c FROM products").fetchone()["c"]

    cat_counts = conn.execute("""
        SELECT category, COUNT(DISTINCT barcode) as products
        FROM product_categories
        GROUP BY category
        ORDER BY products DESC
    """).fetchall()

    no_brand = conn.execute(
        "SELECT COUNT(*) as c FROM products WHERE brand IS NULL"
    ).fetchone()["c"]

    no_sugar = conn.execute(
        "SELECT COUNT(*) as c FROM products WHERE sugars_100g IS NULL"
    ).fetchone()["c"]

    outliers = conn.execute(
        "SELECT COUNT(*) as c FROM products WHERE sugars_100g > 100"
    ).fetchone()["c"]

    multi_cat = conn.execute("""
        SELECT COUNT(*) as c FROM (
            SELECT barcode FROM product_categories
            GROUP BY barcode HAVING COUNT(*) > 1
        )
    """).fetchone()["c"]

    return {
        "total_unique_products": total,
        "categories": {r["category"]: r["products"] for r in cat_counts},
        "products_without_brand": no_brand,
        "products_without_brand_pct": round(no_brand * 100 / total, 1) if total else 0,
        "products_without_sugar": no_sugar,
        "products_without_sugar_pct": round(no_sugar * 100 / total, 1) if total else 0,
        "sugar_outliers_excluded": outliers,
        "products_in_multiple_categories": multi_cat,
        "idempotent": "Yes — loader uses upsert on barcode PK",
    }


# ─── Output formatting ───────────────────────────────────────────────────────

def print_answers(db_path: str = None):
    """Print the formatted report to stdout."""
    conn = get_connection(db_path)

    print("=" * 70)
    print("THE SHELF REPORT — Answers for Priya, Kesari Foods")
    print("=" * 70)

    # Q1
    print("\n─── Q1: Who is on my shelf? ──────────────────────────\n")
    biscuit_count = count_biscuit_products(conn)
    print(f"Distinct biscuit products selling in India: {biscuit_count}")

    print(f"\nTop 15 brands by biscuit shelf share:")
    print(f"{'Brand':<25} {'Products':>10} {'Share':>8}")
    print(f"{'─'*25} {'─'*10} {'─'*8}")
    brands = brand_shelf_share(conn, "biscuits")
    for b in brands[:15]:
        print(f"{b['brand_display']:<25} {b['products']:>10} {b['shelf_pct']:>7.1f}%")

    # Q2
    print("\n─── Q2: Where does sugar sit? ─────────────────────────\n")
    stats = sugar_stats(conn, "biscuits")
    print(f"Biscuit products analyzed:    {stats['total']}")
    print(f"With valid sugar data:        {stats['with_sugar_data']} ({stats['coverage_pct']}%)")
    print(f"Average sugar per 100g:       {stats['avg_sugars']}g")
    print(f"Range:                        {stats['min_sugars']}g – {stats['max_sugars']}g")
    print(f"\nNote: {100 - stats['coverage_pct']:.1f}% of biscuit products lack sugar data.")
    print(f"Impossible values (>100g/100g) have been excluded.")

    # Q3
    print("\n─── Q3: Can I trust this? ─────────────────────────────\n")
    quality = data_quality_report(conn)
    print(f"Unique products (by barcode): {quality['total_unique_products']}")
    print(f"Idempotent ingest:            {quality['idempotent']}")
    print(f"Products in 2+ categories:    {quality['products_in_multiple_categories']}")
    print(f"Products without brand:       {quality['products_without_brand']} ({quality['products_without_brand_pct']}%)")
    print(f"Sugar outliers excluded:       {quality['sugar_outliers_excluded']} (>100g/100g)")

    print(f"\nTrust safeguards:")
    print(f"  ✓ Barcode-keyed upsert — re-running ingest changes nothing")
    print(f"  ✓ Multi-category junction table — no flat-schema double counting")
    print(f"  ✓ Category-scoped denominator — accurate shelf share percentages")
    print(f"  ✓ Sugar outlier filter — impossible values excluded from stats")

    conn.close()


if __name__ == "__main__":
    print_answers()
