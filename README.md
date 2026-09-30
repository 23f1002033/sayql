# SayQL

A voice analyst for a small D2C business owner. Ask a question out loud
about your sales, returns, or customers, and it answers in speech while the
screen shows the number, a chart, and the exact SQL it ran.

## Try it

Live URL: TODO (add after deploy)

Needs a microphone and headphones (or a quiet room - it will hear its own
voice through open speakers and can get confused).

Click Start, allow microphone access, then say these out loud, one at a
time, waiting for the answer before the next:

1. "What was net revenue last month?"
   A number appears with the period and definition used; the agent says
   the same number out loud, rounded for speech (for example "50.8 lakh
   rupees").
2. "What were returns last week by city?"
   A bar chart appears, broken down by city; the agent names the top city
   and its share.
3. "What was our revenue last month?"
   "Revenue" is deliberately undefined - the agent asks one short question
   back (gross revenue or net revenue) instead of guessing. The screen
   shows the same two options as a reminder of the wording, not clickable
   buttons - there is no way to answer by tapping (see Limits).
4. "Why did returns go up for the Wireless Earbuds Pro this month?"
   A "why" card appears: the overall change, the top contributing city (or,
   for a rate, which side of it moved), and a note that this shows
   correlation, not proven cause.

## What it is

Every business term (net revenue, return rate, AOV, active customers, and
so on) is defined once in a metric dictionary, with a version and an exact
SQL pattern. The voice agent never writes SQL freehand for a business term
and never invents a number - it looks up the definition, runs a
deterministic query, and reads back a value the code already formatted.
When a term is ambiguous, it asks instead of guessing, and every answer
states which definition it used.

## How AssemblyAI is used

The whole voice loop - speech in, language understanding, tool calls,
speech out - runs on a single AssemblyAI Voice Agent WebSocket session.
The backend only mints a short-lived token
(`GET https://agents.assemblyai.com/v1/token`) so the API key never reaches
the browser; the browser streams microphone audio to AssemblyAI over that
session and plays back the synthesized reply. When the agent decides it
needs data, it calls one of five tools (resolve a metric, run a metric
query, explain a change, a validated raw-SQL fallback, or suggest
follow-up questions); the browser relays each tool call to this backend
and returns the result over the same WebSocket, after `reply.done`, per
the Voice Agent API's tool-calling protocol.

## Run locally

Backend:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put your real ASSEMBLYAI_API_KEY in .env
python scripts/seed.py
uvicorn main:app --reload
```

Frontend (only needed if you change it - a built copy is not committed):

```
cd frontend
npm ci
npm run build
```

Open `http://127.0.0.1:8000`. The old plain UI is kept at
`http://127.0.0.1:8000/classic` for comparison.

## Deploy

Render, Docker environment, free tier:

1. Push this repository to GitHub.
2. On Render: New -> Blueprint, point it at the repo (it will read
   `render.yaml`).
3. Render prompts for the `ASSEMBLYAI_API_KEY` secret (marked
   `sync: false` in `render.yaml`) - paste your real key.
4. Deploy. The build runs both Docker stages (frontend build, then the
   Python image) and seeds the demo database at build time, so the first
   request already has data.
5. Render's health check hits `/health`; once it is green, the URL is
   live.

## Architecture

```
voice/text -> AssemblyAI Voice Agent (speech, language, tool calls)
           -> resolve_metric   (spoken term -> versioned metric definition)
           -> query_metric / explain_change
           -> compiler (plan -> SQL, deterministic) -> sqlglot validator (read-only, single statement)
           -> SQLAlchemy executor (read-only connection, 3s timeout, 200-row cap)
           -> pure-Python formatting (app/format.py: Rs, lakh/crore, percent, percentage points)
           -> card (full numbers, for the screen) + model_payload (spoken strings only, for the agent)
           -> Next.js UI renders the card; the agent speaks from model_payload
Every tool call is logged to query_history (SQLite) for the sidebar and future eval.
```

## Accuracy

TODO: fill in after running `evals/run_eval.py` against the golden
questions in `evals/questions.yaml`.

## Limits

- The demo data is fixed and synthetic, anchored to 2026-09-30 as "today" -
  real dates outside that window will not mean anything to it.
- The Voice Agent API has no text-input message type as of this writing,
  so the clarification options and example questions on screen are
  reminders of the wording, not clickable controls; every answer has to be
  spoken.
- Rate limiting (3 tokens per IP per 10 minutes, 150 per day total) and
  in-memory session counters reset if the server restarts, and do not work
  correctly across more than one running instance.
- The read-only SQL guard blocks writes and multi-statement input, but it
  is not a substitute for a real per-tenant database role in a
  multi-tenant deployment - see `docs/roadmap.md`.
- Single demo workspace ("demo") - no login, no per-user data, by design
  for this hackathon scope.
