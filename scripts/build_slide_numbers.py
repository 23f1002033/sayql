"""Builds docs/slides/data/slide_numbers.json from repo sources.

Run after changing tests, reseeding data, or updating evals/results.md, then
refresh the deck without touching its HTML. Only numbers backed by a repo
source go in: pytest's own pass count, live row counts from data/store.db,
and (once it exists) evals/results.md.
"""
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "store.db"
RESULTS_PATH = ROOT / "evals" / "results.md"
OUT_PATH = ROOT / "docs" / "slides" / "data" / "slide_numbers.json"

ROW_COUNT_TABLES = ["customers", "products", "orders", "order_items", "returns"]


def get_pytest_count() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    match = re.search(r"(\d+) passed", proc.stdout)
    if not match:
        raise RuntimeError("could not parse pytest output:\n" + proc.stdout + proc.stderr)
    return int(match.group(1))


def get_row_counts() -> dict:
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        counts = {}
        for table in ROW_COUNT_TABLES:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0]
        return counts
    finally:
        conn.close()


def get_eval_results() -> dict:
    if not RESULTS_PATH.exists():
        return {"available": False}

    text = RESULTS_PATH.read_text()
    values = {}
    for line in text.splitlines():
        match = re.match(r"^\s*[-*]?\s*([a-zA-Z_ ]+):\s*([0-9.]+%?)\s*$", line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            values[key] = match.group(2)
    values["available"] = True
    return values


def main():
    data = {
        "pytest_passed": get_pytest_count(),
        "row_counts": get_row_counts(),
        "eval_results": get_eval_results(),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print("wrote", OUT_PATH)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
