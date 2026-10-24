"""Create the analytics SQL views from the files in ``sql/``.

The ``.sql`` files are the single source of truth. They also contain
exploratory ``SELECT`` queries, so only ``CREATE VIEW`` statements are
extracted and applied, in dependency order.
"""
import re
from pathlib import Path

from django.conf import settings

SQL_DIR = Path(settings.BASE_DIR) / "sql"

# Order matters: later files build on views from earlier ones.
SQL_FILES = [
    "views_for_bi.sql",
    "product_analytics.sql",
    "rfm_segments.sql",
    "winback_customers.sql",
    "sales_anomaly.sql",
]

VIEW_RE = re.compile(r"CREATE\s+VIEW\s+(\w+)\s+AS\b.*?;", re.IGNORECASE | re.DOTALL)

# Views the REST API reads from.
API_VIEWS = [
    "vw_daily_sales",
    "vw_customer_metrics",
    "vw_product_analytics",
    "vw_rfm_segments",
    "vw_sales_anomaly",
    "vw_winback_candidates",
]


def view_statements():
    """Return ``[(view_name, create_statement), ...]`` in dependency order."""
    statements = []
    for filename in SQL_FILES:
        text = (SQL_DIR / filename).read_text(encoding="utf-8")
        text = re.sub(r"--[^\n]*", "", text)  # a ';' in a comment must not end a statement
        statements += [(m.group(1), m.group(0)) for m in VIEW_RE.finditer(text)]
    return statements


def create_views(connection):
    """Drop and recreate every view. No-op on databases other than PostgreSQL."""
    if connection.vendor != "postgresql":
        return []
    statements = view_statements()
    with connection.cursor() as cursor:
        for name, _ in reversed(statements):
            cursor.execute(f"DROP VIEW IF EXISTS {name} CASCADE")
        for _, statement in statements:
            cursor.execute(statement)
    return [name for name, _ in statements]


def drop_views(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for name, _ in reversed(view_statements()):
            cursor.execute(f"DROP VIEW IF EXISTS {name} CASCADE")
