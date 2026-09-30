# Roadmap

The intended shape of the product, in order. Each stage assumes the
previous one is working, not replaced.

## 1. Ask

Where this build stops. Answer a spoken question with a number, a
breakdown, or a trend, grounded in a versioned metric definition.

## 2. Analyze

Widen `explain_change` from a single dimension to comparing several at
once, and let a "why" question chain into a follow-up ("and which sku
inside that city?") without restating the whole question.

## 3. Explain

Today, `explain_change` reports one round of contribution or
numerator/denominator decomposition and stops there, with a fixed
correlation-not-cause disclaimer. The next step is letting the agent
propose a plausible next question ("check whether that city's returns
correlate with a specific carrier or product batch") rather than the user
having to think of it.

## 4. Detect

Nothing today watches the data on its own - every question is asked. A
detect stage means a scheduled job that runs the existing metric
definitions on a cadence and flags a change worth asking about, using the
same low-base and volume-context checks `explain_change` already has, so a
flagged change is held to the same honesty standard as a spoken answer.

## 5. Alert

Surface a detected change somewhere the owner will see it outside the app
(email, SMS, a webhook) - deliberately out of scope for a voice-in,
voice-out demo, but the metric dictionary and the query pipeline underneath
it do not change to support this.

## 6. Act

Let a detected, alerted change trigger a real action (pause a listing,
flag an order) - the furthest stage, and the one that most needs the
tenant-isolation and audit work below in place first.

## Deferred (not staged above, needed before any real deployment)

- **Auth and RBAC.** No login exists. Every table has a `workspace_id`
  column, but nothing checks that a request may only touch its own
  workspace's rows.
- **Tenant isolation enforcement.** Follows directly from auth - today
  `workspace_id="demo"` is hardcoded in `app/tools.py`.
- **Staging and production environments.** One environment today, driven
  by one `.env`.
- **Monitoring beyond `query_history`.** The audit table records what ran
  and how long it took; nothing alerts a human when the error rate rises
  or a query starts timing out more often.
- **Shopify / WooCommerce (or other) connectors.** `app/ingest/` takes a
  CSV with a column map; a connector would populate that same shape on a
  schedule, not replace the loader.
