import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import tools

load_dotenv()

ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
TOKEN_URL = "https://agents.assemblyai.com/v1/token"

TOOL_FUNCTIONS = {
    "list_tables": lambda args: tools.list_tables(),
    "describe_table": lambda args: tools.describe_table(args.get("name", "")),
    "get_metric": lambda args: tools.get_metric(args.get("term", "")),
    "run_sql": lambda args: tools.run_sql(args.get("sql", "")),
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")
