import os
import sqlite3
import time
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "store.db"
QUERY_TIMEOUT_SECONDS = 3
MAX_ROWS = 200

_engine = None


class ExecutionError(Exception):
    pass


def _sqlite_creator(db_path: str):
    def creator():
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
        conn.set_progress_handler(lambda: time.monotonic() > deadline, 1000)
        return conn

    return creator


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    url = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

    if url.startswith("sqlite"):
        db_path = url.split("sqlite:///", 1)[1] if "sqlite:///" in url else str(DEFAULT_DB_PATH)
        # NullPool: a fresh connection (and a fresh timeout deadline) per checkout.
        _engine = create_engine("sqlite://", creator=_sqlite_creator(db_path), poolclass=NullPool)
    else:
        _engine = create_engine(url)

        @event.listens_for(_engine, "connect")
        def _set_statement_timeout(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("SET statement_timeout TO 3000")
            cursor.close()

    return _engine


def execute(sql: str, params=None, max_rows: int = MAX_ROWS) -> dict:
    engine = get_engine()
    params = params or {}
    start = time.monotonic()

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            columns = list(result.keys())
            rows = result.fetchmany(max_rows + 1)
    except Exception as err:
        message = str(err)
        if "interrupted" in message.lower():
            raise ExecutionError("query timed out after 3 seconds") from err
        raise ExecutionError(f"sql error: {message}") from err

    elapsed_ms = int((time.monotonic() - start) * 1000)
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]

    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
    }
