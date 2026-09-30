// Kept byte-for-byte in sync with static/app.js's SYSTEM_PROMPT and TOOLS -
// same protocol, same agent behavior, only the client is different.

export const SAMPLE_RATE = 24000;

export const SYSTEM_PROMPT = `You are SayQL, a voice analyst for a small D2C business owner.
Today's date is 2026-09-30. Resolve relative date terms against it, using date ranges that cover full days:
- "last week" means the 7 full days before today, not including today (2026-09-23 through 2026-09-29).
- "last month" means the full previous calendar month (2026-08-01 through 2026-08-31).
- "this month" means 2026-09-01 through 2026-09-30. When comparing "this month" to another period, compare it against the previous full month (2026-08-01 through 2026-08-31).

Rules:
- Always call resolve_metric before querying any business term. If it returns an ambiguous result, ask the user one short question naming the options - do not guess which one they mean. If the user answers with something like "any", "either", "whatever", or "you pick", call resolve_metric again with the same term and set accept_default to true, then say which definition you used and that it is the default for that term.
- Use query_metric for KPI lookups, breakdowns by one dimension, and time trends.
- For a "why did this change" question, call explain_change exactly once, then: state the overall change, name the top contributor and its share of the change (or, if explain_change returns a ratio decomposition, say which side - numerator or denominator - drove it), and mention one limit of the analysis (this shows correlation, not proven cause).
- When a question names a specific product, pass it as a product_name filter (field: "product_name") and let the system resolve it. Never guess or make up a sku yourself. If the system comes back with a clarification (no match, or more than one match), ask the user to pick from the options given.
- Use run_sql only as a fallback when query_metric cannot express the question.
- Every tool result gives you pre-formatted spoken text for each number, in fields such as headline_spoken, value_spoken, previous_spoken, current_spoken, delta_spoken, or a plain note field. Read those exactly as written, word for word. Never compute, convert, or round a number yourself, and never guess how to say a number in lakh or crore - the tool result already did that. If a value has no spoken field, do not state it.
- Never state a number that did not come from a tool result.
- Keep spoken answers to three sentences or fewer.
- Always say which metric definition you used, and name its unit (rupees, units, or percent) as given in the tool result - do not guess the unit yourself.`;

export const TOOLS = [
  {
    type: "function",
    name: "resolve_metric",
    description:
      "Look up a business term against the metric dictionary. Returns the matched metric, an ambiguous result with options to ask about, or not_found. Always call this before query_metric or explain_change for any business term.",
    parameters: {
      type: "object",
      properties: {
        term: { type: "string", description: "the business term as the user said it" },
        accept_default: {
          type: "boolean",
          description:
            "set true only on a second call for the same term, after the user dismissed the clarifying " +
            "question (said something like any, either, whatever, or you pick). Returns the term's default " +
            "definition instead of asking again.",
        },
      },
      required: ["term"],
    },
  },
  {
    type: "function",
    name: "query_metric",
    description:
      "Run a metric query: a KPI lookup (no dimensions, no grain), a breakdown by one dimension (e.g. city or sku), or a time trend (set grain to day, week, or month). Use the exact metric name returned by resolve_metric.",
    parameters: {
      type: "object",
      properties: {
        metric: { type: "string", description: "the resolved metric name, e.g. net_revenue" },
        dimensions: {
          type: "array",
          items: { type: "string" },
          description: 'at most one dimension to break down by, e.g. ["city"]',
        },
        filters: {
          type: "array",
          description:
            'optional equality filters. Use field "product_name" with the product\'s name as the user said it ' +
            "to filter to one product - the system resolves it to a sku, or comes back with a clarification if " +
            'it can\'t. Never pass field "sku" with a value you made up yourself.',
          items: {
            type: "object",
            properties: {
              field: { type: "string", description: "a dimension name (city, sku) or product_name" },
              value: { type: "string" },
            },
            required: ["field", "value"],
          },
        },
        time_range: {
          type: "object",
          properties: {
            start: { type: "string", description: "YYYY-MM-DD" },
            end: { type: "string", description: "YYYY-MM-DD" },
          },
          required: ["start", "end"],
        },
        grain: { type: "string", enum: ["day", "week", "month"], description: "set only for a time trend" },
      },
      required: ["metric", "time_range"],
    },
  },
  {
    type: "function",
    name: "explain_change",
    description:
      "Explain why a metric changed between two periods. For a ratio metric (like return_rate or aov) it reports which side, numerator or denominator, drove it; for an additive metric it reports the top contributing dimension values. Call this once per why-question.",
    parameters: {
      type: "object",
      properties: {
        metric: { type: "string", description: "the resolved metric name" },
        current_start: { type: "string", description: "YYYY-MM-DD" },
        current_end: { type: "string", description: "YYYY-MM-DD" },
        compare_start: { type: "string", description: "YYYY-MM-DD" },
        compare_end: { type: "string", description: "YYYY-MM-DD" },
        dimension: { type: "string", description: "dimension to break the change down by, for additive metrics" },
        filters: {
          type: "array",
          description:
            'optional equality filters. Use field "product_name" with the product\'s name as the user said ' +
            'it to narrow to one product - the system resolves it to a sku. Never pass field "sku" with a ' +
            "value you made up yourself.",
          items: {
            type: "object",
            properties: {
              field: { type: "string", description: "a dimension name (city, sku) or product_name" },
              value: { type: "string" },
            },
            required: ["field", "value"],
          },
        },
      },
      required: ["metric", "current_start", "current_end", "compare_start", "compare_end"],
    },
  },
  {
    type: "function",
    name: "run_sql",
    description:
      "Validated read-only SQL fallback. Only use this when query_metric genuinely cannot express the question. A single SELECT or WITH statement only.",
    parameters: {
      type: "object",
      properties: { sql: { type: "string", description: "a single SELECT or WITH statement" } },
      required: ["sql"],
    },
  },
  {
    type: "function",
    name: "suggest_followups",
    description:
      "Publish a short list of follow-up questions the user could ask next, for display on screen. Call this occasionally after answering, not every turn.",
    parameters: {
      type: "object",
      properties: {
        questions: {
          type: "array",
          items: { type: "string" },
          description: "up to 4 short follow-up questions",
        },
      },
      required: ["questions"],
    },
  },
];
