import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, insert,
)

DEFAULT_AUDIT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "audit.db"

METADATA = MetaData()

QUERY_HISTORY = Table(
    "query_history", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_id", String, nullable=False),
    Column("session_id", String, nullable=False),
    Column("question", Text, nullable=False),
    Column("plan_json", Text),
    Column("sql", Text),
    Column("definition_version", Integer),
    Column("row_count", Integer),
    Column("elapsed_ms", Integer),
    Column("status", String, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

USAGE = Table(
    "usage", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_id", String, nullable=False),
    Column("session_id", String, nullable=False),
    Column("session_seconds", Float),
    Column("tool_calls", Integer),
    Column("created_at", DateTime, nullable=False),
)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("AUDIT_DATABASE_URL", f"sqlite:///{DEFAULT_AUDIT_DB_PATH}")
        _engine = create_engine(url)
        METADATA.create_all(_engine)
    return _engine


def record_query(
    workspace_id, session_id, question, plan_json, sql,
    definition_version, row_count, elapsed_ms, status,
):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(insert(QUERY_HISTORY).values(
            workspace_id=workspace_id,
            session_id=session_id,
            question=question,
            plan_json=plan_json,
            sql=sql,
            definition_version=definition_version,
            row_count=row_count,
            elapsed_ms=elapsed_ms,
            status=status,
            created_at=datetime.now(timezone.utc),
        ))


def record_usage(workspace_id, session_id, session_seconds, tool_calls):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(insert(USAGE).values(
            workspace_id=workspace_id,
            session_id=session_id,
            session_seconds=session_seconds,
            tool_calls=tool_calls,
            created_at=datetime.now(timezone.utc),
        ))
