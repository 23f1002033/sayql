import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import tools
import app.tools as agent_tools

load_dotenv()

ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
TOKEN_URL = "https://agents.assemblyai.com/v1/token"

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
        args.get("term", ""), session_id=sid, question=q
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


@app.get("/api/voice-token")
async def voice_token():
    if not ASSEMBLYAI_API_KEY:
        return JSONResponse(
            {"error": "server is missing ASSEMBLYAI_API_KEY"}, status_code=500
        )

    params = {"expires_in_seconds": 60, "max_session_duration_seconds": 600}
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")
