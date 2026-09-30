# Architecture

## Pipeline

```
voice/text -> agent (intent, via AssemblyAI Voice Agent API)
           -> resolve_metric (spoken term -> versioned metric definition, or a clarifying question)
           -> QueryPlan (pydantic: workspace_id, metric, dimensions, filters, time_range, grain, limit)
           -> compiler (plan -> SQL from the metric's structured template - deterministic, parameterized)
           -> validator (sqlglot AST check: single SELECT/WITH, allowlisted tables, no writes, row limit injected)
           -> executor (SQLAlchemy, read-only connection, 3s timeout, 200-row cap)
           -> analysis (explain_change: contribution breakdown for additive metrics, numerator/denominator
              decomposition for ratio metrics, low-base and volume-context flags)
           -> app/format.py (the one place a number becomes text: Rs/lakh/crore, percent vs percentage points,
              spoken vs display form)
           -> card (full numbers and chart data, for the screen) + model_payload (spoken strings only, for the
              agent - it never sees a raw number it could mis-convert)
           -> Next.js UI renders the card; AssemblyAI speaks from model_payload
```

Every tool call writes a row to `query_history` (a separate SQLite file,
`data/audit.db`) regardless of outcome, for the sidebar's History panel and
for future eval scoring.

## Modules

- `app/semantic/` - `metrics.yaml` (the metric dictionary: name, version,
  owner, description, formula, unit, SQL template, allowed dimensions,
  aliases, ambiguous-term defaults), `loader.py`, `resolve.py`,
  `products.py` (deterministic product-name -> sku lookup, so the model
  never guesses a sku).
- `app/planner/schema.py` - the `QueryPlan` pydantic model.
- `app/compiler/compiler.py` - plan to SQL. Dialect-aware via sqlglot
  (SQLite and Postgres share the same code path; only the grain-bucket
  function text differs).
- `app/validator/validator.py` - a second, independent guard on top of the
  compiler's own safety, and the only guard on the `run_sql` fallback path.
- `app/executor/executor.py` - SQLAlchemy engine. SQLite is opened with a
  `mode=ro` URI and a fresh progress-handler deadline per query (`NullPool`,
  so pooling cannot let a stale deadline leak into the next query).
- `app/analysis/explain_change.py` - pure Python over executor results. No
  SQL of its own beyond what the compiler already produces.
- `app/ingest/` - CSV to SQLAlchemy tables, with `workspace_id` injected at
  load time rather than read from the CSV.
- `app/audit/` - `query_history` and `usage` tables, JSON-formatted
  logging to stdout.
- `app/providers/voice.py` - a `VoiceProvider` interface with the one
  AssemblyAI implementation, so a second voice backend would not require
  touching the rest of the app.
- `app/tools.py` - the five agent-facing tools (`resolve_metric`,
  `query_metric`, `explain_change`, `run_sql`, `suggest_followups`); the
  only module that builds `card` and `model_payload`.
- `main.py` - FastAPI app: token minting (rate-limited), the tool
  endpoints, `/api/metrics`, `/api/history`, `/health`, and the two static
  mounts (`/` for the current UI, `/classic` for the original one).
- `frontend/` - Next.js App Router, static export, calling the same
  `/api/agent/*` endpoints the voice loop uses.

## Seams (built as a boundary, not built out)

- **Postgres.** The compiler already branches on dialect; `docker-compose.yml`
  and `infra/postgres_readonly.sql` exist so a Postgres `DATABASE_URL` and a
  read-only role are a config change, not a rewrite. Not exercised for the
  demo, which runs on SQLite.
- **Auth and per-tenant isolation.** Every table carries a `workspace_id`
  column and every tool call threads one through, but nothing enforces
  that a request may only see its own workspace's rows - there is one
  workspace ("demo") and no login. See `docs/roadmap.md`.
- **A second voice provider.** `VoiceProvider` is an interface with one
  implementation; swapping it means writing a second class, not touching
  `main.py`'s routes.
- **Connectors (Shopify, WooCommerce, etc).** `app/ingest/loader.py` takes
  CSVs with a column map; a connector would produce the same CSV shape and
  call the same loader, not replace it.

## What is explicitly not built

Auth/RBAC, tenant isolation enforcement, staging/prod separation, an error
tracking service, e-commerce platform connectors, and alerting are all
deferred - see `docs/roadmap.md` for the intended order.
