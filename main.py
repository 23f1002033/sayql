import os
import time
from collections import defaultdict, deque

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

import tools
import app.tools as agent_tools
from app.audit.db import QUERY_HISTORY
from app.audit.db import get_engine as get_audit_engine
from app.semantic.loader import load_metrics

load_dotenv()

ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
TOKEN_URL = "https://agents.assemblyai.com/v1/token"

# In-memory rate limiting for /api/voice-token. Good enough for a single
# free-tier instance; a seam for Phase-later work would move this to Redis
# if the app ever runs multiple worker processes, since counts would no
# longer be shared across them.
RATE_LIMIT_PER_IP = 8
RATE_LIMIT_WINDOW_SECONDS = 10 * 60
DAILY_LIMIT_GLOBAL = 300
DAILY_WINDOW_SECONDS = 24 * 60 * 60

_ip_request_times: dict[str, deque] = defaultdict(deque)
_global_request_times: deque = deque()


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For only for its first hop - the entry our own
    # reverse proxy (Render) sets for the real client - never a later entry,
    # which a client could forge by sending its own X-Forwarded-For header.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _format_retry_after(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = (seconds + 59) // 60  # round up, so "try again" is never too early
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = (minutes + 59) // 60
    return f"{hours} hour{'s' if hours != 1 else ''}"


def _check_rate_limit(ip: str):
    now = time.monotonic()

    ip_times = _ip_request_times[ip]
    while ip_times and now - ip_times[0] > RATE_LIMIT_WINDOW_SECONDS:
        ip_times.popleft()
    if len(ip_times) >= RATE_LIMIT_PER_IP:
        retry_in = _format_retry_after(RATE_LIMIT_WINDOW_SECONDS - (now - ip_times[0]))
        return False, f"Too many voice sessions from your connection. Try again in about {retry_in}."

    while _global_request_times and now - _global_request_times[0] > DAILY_WINDOW_SECONDS:
        _global_request_times.popleft()
    if len(_global_request_times) >= DAILY_LIMIT_GLOBAL:
        retry_in = _format_retry_after(DAILY_WINDOW_SECONDS - (now - _global_request_times[0]))
        return False, f"This demo has reached its daily voice session limit. Try again in about {retry_in}."

    ip_times.append(now)
    _global_request_times.append(now)
    return True, None

# Legacy tools (M1/M2 pipeline), kept working for rollback safety.
TOOL_FUNCTIONS = {
    "list_tables": lambda args: tools.list_tables(),
    "describe_table": lambda args: tools.describe_table(args.get("name", "")),
    "get_metric": lambda args: tools.get_metric(args.get("term", "")),
    "run_sql": lambda args: tools.run_sql(args.get("sql", "")),
}

# Phase 2 semantic-layer tools: resolve_metric -> query_metric / explain_change,
# with run_sql kept only as a validated fallback.
AGENT_TOOL_FUNCTIONS = {
    "resolve_metric": lambda args, sid, q: agent_tools.resolve_metric(
        args.get("term", ""), accept_default=bool(args.get("accept_default", False)), session_id=sid, question=q
    ),
    "query_metric": lambda args, sid, q: agent_tools.query_metric(args, session_id=sid, question=q),
    "explain_change": lambda args, sid, q: agent_tools.explain_change(
        args.get("metric", ""),
        args.get("current_start", ""),
        args.get("current_end", ""),
        args.get("compare_start", ""),
        args.get("compare_end", ""),
        dimension=args.get("dimension"),
        filters=args.get("filters"),
        session_id=sid,
        question=q,
    ),
    "run_sql": lambda args, sid, q: agent_tools.run_sql(args.get("sql", ""), session_id=sid, question=q),
    "suggest_followups": lambda args, sid, q: agent_tools.suggest_followups(
        args.get("questions", []), session_id=sid, question=q
    ),
}

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/voice-token")
async def voice_token(request: Request):
    if not ASSEMBLYAI_API_KEY:
        return JSONResponse(
            {"error": "server is missing ASSEMBLYAI_API_KEY"}, status_code=500
        )

    ok, message = _check_rate_limit(_client_ip(request))
    if not ok:
        return JSONResponse({"error": message}, status_code=429)

    params = {"expires_in_seconds": 60, "max_session_duration_seconds": 180}
    headers = {"Authorization": f"Bearer {ASSEMBLYAI_API_KEY}"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(TOKEN_URL, headers=headers, params=params)

    if resp.status_code != 200:
        return JSONResponse(
            {"error": "token request failed", "detail": resp.text},
            status_code=502,
        )

    return resp.json()


@app.post("/api/tool/{name}")
async def call_tool(name: str, request: Request):
    if name not in TOOL_FUNCTIONS:
        return JSONResponse({"error": f"unknown tool: {name}"}, status_code=404)

    try:
        args = await request.json()
    except Exception:
        args = {}
    if not isinstance(args, dict):
        args = {}

    return TOOL_FUNCTIONS[name](args)


@app.post("/api/agent/{name}")
async def call_agent_tool(name: str, request: Request):
    if name not in AGENT_TOOL_FUNCTIONS:
        return JSONResponse({"error": f"unknown tool: {name}"}, status_code=404)

    try:
        args = await request.json()
    except Exception:
        args = {}
    if not isinstance(args, dict):
        args = {}

    session_id = args.pop("_session_id", None)
    question = args.pop("_question", None)

    return AGENT_TOOL_FUNCTIONS[name](args, session_id, question)


@app.get("/api/metrics")
async def list_metrics():
    metrics, _ = load_metrics()
    return {
        "metrics": [
            {"name": m.name, "version": m.version, "description": m.description, "unit": m.unit}
            for m in metrics.values()
        ]
    }


@app.get("/api/history")
async def get_history(limit: int = 20):
    engine = get_audit_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            select(QUERY_HISTORY).order_by(QUERY_HISTORY.c.id.desc()).limit(limit)
        ).mappings().all()

    return {
        "history": [
            {
                "id": r["id"],
                "question": r["question"],
                "status": r["status"],
                "definition_version": r["definition_version"],
                "row_count": r["row_count"],
                "elapsed_ms": r["elapsed_ms"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


# Old static/ UI, kept at /classic for rollback safety. Registered before
# the "/" mount below, or that mount's prefix match would shadow it.
app.mount("/classic", StaticFiles(directory="static", html=True), name="classic")

# Hackathon slide deck, self-contained HTML. Registered before "/" for the
# same reason as /classic above.
app.mount("/slides", StaticFiles(directory="docs/slides", html=True), name="slides")

# New Next.js UI (Phase 3+5), now the app served at "/".
if os.path.isdir("frontend/out"):
    app.mount("/", StaticFiles(directory="frontend/out", html=True), name="frontend")
else:
    print("WARNING: frontend/out not found (run 'cd frontend && npm run build'); serving /classic at / instead.")
    app.mount("/", StaticFiles(directory="static", html=True), name="static-fallback")
