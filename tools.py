import sqlite3
import time
from pathlib import Path

import yaml

DB_PATH = Path(__file__).parent / "data" / "store.db"
METRICS_PATH = Path(__file__).parent / "metrics.yaml"

QUERY_TIMEOUT_SECONDS = 3
MAX_ROWS = 200

TABLE_DESCRIPTIONS = {
    "customers": "One row per customer: customer_id, name, city, signup_date.",
    "products": "One row per product: product_id, sku, name, category, price.",
    "orders": "One row per order: order_id, customer_id, order_date, city.",
    "order_items": "One row per line item: order_item_id, order_id, product_id, quantity, unit_price.",
    "returns": "One row per returned line item: return_id, order_item_id, return_date, quantity, reason.",
}

_metrics_cache = None


def _connect_ro():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def list_tables():
    return {"tables": [{"name": name, "description": desc} for name, desc in TABLE_DESCRIPTIONS.items()]}


def describe_table(name):
    if name not in TABLE_DESCRIPTIONS:
        return {"error": f"unknown table: {name}", "tables": list(TABLE_DESCRIPTIONS)}

    conn = _connect_ro()
    try:
        columns = [
            {"name": row[1], "type": row[2]}
            for row in conn.execute(f"PRAGMA table_info({name})").fetchall()
        ]
        row_count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    finally:
        conn.close()

    return {
        "name": name,
        "description": TABLE_DESCRIPTIONS[name],
        "columns": columns,
        "row_count": row_count,
    }


def _load_metrics():
    global _metrics_cache
    if _metrics_cache is None:
        with open(METRICS_PATH) as f:
            _metrics_cache = yaml.safe_load(f)["metrics"]
    return _metrics_cache


def get_metric(term):
    metrics = _load_metrics()
    term_norm = (term or "").strip().lower()

    for key, metric in metrics.items():
        aliases = [a.lower() for a in metric.get("aliases", [])] + [key.replace("_", " ")]
        if term_norm in aliases:
            return {
                "found": True,
                "name": key,
                "definition": metric["definition"].strip(),
                "unit": metric.get("unit"),
                "sql_pattern": metric["sql"].strip(),
            }

    return {
        "found": False,
        "message": f"'{term}' is not a defined metric.",
        "available_terms": sorted(metrics.keys()),
    }


def run_sql(sql):
    statement = (sql or "").strip().rstrip(";")
    if not statement:
        return {"error": "empty query"}

    first_word = statement.split(None, 1)[0].lower()
    if first_word not in ("select", "with"):
        return {"error": "only a single SELECT or WITH query is allowed"}

    conn = _connect_ro()
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    conn.set_progress_handler(lambda: time.monotonic() > deadline, 1000)

    try:
        cursor = conn.execute(statement)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(MAX_ROWS + 1)
    except sqlite3.OperationalError as err:
        if "interrupted" in str(err):
            return {"error": "query timed out after 3 seconds"}
        return {"error": f"sql error: {err}"}
    except sqlite3.ProgrammingError as err:
        return {"error": f"sql error: {err}"}
    finally:
        conn.close()

    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]

    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
    }
