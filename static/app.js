const startBtn = document.getElementById("start-btn");
const stopBtn = document.getElementById("stop-btn");
const statusEl = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");
const errorBannerEl = document.getElementById("error-banner");

const metricCardEl = document.getElementById("metric-card");
const metricNameEl = document.getElementById("metric-name");
const metricDefinitionEl = document.getElementById("metric-definition");

const sqlTextEl = document.getElementById("sql-text");
const sqlErrorEl = document.getElementById("sql-error");

const tableWrapEl = document.getElementById("table-wrap");
const chartCardEl = document.getElementById("chart-card");
const chartCanvasEl = document.getElementById("chart-canvas");

const SAMPLE_RATE = 24000;

const SYSTEM_PROMPT = `You are SayQL, a voice analyst for a small D2C business owner.
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

const TOOLS = [
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
          description: "at most one dimension to break down by, e.g. [\"city\"]",
        },
        filters: {
          type: "array",
          description:
            "optional equality filters. Use field \"product_name\" with the product's name as the user said it " +
            "to filter to one product - the system resolves it to a sku, or comes back with a clarification if " +
            "it can't. Never pass field \"sku\" with a value you made up yourself.",
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
            "optional equality filters. Use field \"product_name\" with the product's name as the user said " +
            "it to narrow to one product - the system resolves it to a sku. Never pass field \"sku\" with a " +
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

let ws = null;
let audioContext = null;
let micStream = null;
let workletNode = null;
let sessionReady = false;
let intentionalStop = false;
let sessionId = null;
let lastUserQuestion = null;

let nextPlayTime = 0;
let scheduledSources = [];
let partialUserEl = null;
let pendingToolResults = [];

let currentSql = "";
let currentMetric = null;
let lastQueryResult = null;
let chartInstance = null;

// Empty-reply guard: nudge once if a reply turn ends with no audio and no tool call.
let turnHadAudio = false;
let turnHadToolCall = false;
let nudgedThisTurn = false;

startBtn.addEventListener("click", start);
stopBtn.addEventListener("click", stop);

function setStatus(text) {
  statusEl.textContent = text;
}

function showError(text) {
  errorBannerEl.textContent = text;
  errorBannerEl.classList.remove("hidden");
}

function clearError() {
  errorBannerEl.textContent = "";
  errorBannerEl.classList.add("hidden");
}

function clearChildren(el) {
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
}

function appendLine(role, text) {
  const el = document.createElement("div");
  el.className = "line " + role;
  el.textContent = text;
  transcriptEl.appendChild(el);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
  return el;
}

function updatePartial(role, text) {
  if (!partialUserEl) {
    partialUserEl = appendLine(role + " partial", "");
  }
  partialUserEl.textContent = (role === "user" ? "You: " : "Agent: ") + text;
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function finalizeTranscript(role, text) {
  if (role === "user") {
    lastUserQuestion = text;
  }
  const label = (role === "user" ? "You: " : "Agent: ") + text;
  if (partialUserEl && role === "user") {
    partialUserEl.textContent = label;
    partialUserEl.className = "line user";
    partialUserEl = null;
  } else {
    appendLine(role, label);
  }
}

function updateMetricCard(definition) {
  currentMetric = definition;
  if (!definition) {
    metricCardEl.classList.add("hidden");
    return;
  }
  metricCardEl.classList.remove("hidden");
  metricNameEl.textContent = `${definition.name} (v${definition.version})`;
  metricDefinitionEl.textContent = definition.description;
}

function updateSqlPanel(sql, errorMessage) {
  currentSql = sql || "";
  sqlTextEl.textContent = currentSql;
  if (errorMessage) {
    sqlErrorEl.textContent = errorMessage;
    sqlErrorEl.classList.remove("hidden");
  } else {
    sqlErrorEl.textContent = "";
    sqlErrorEl.classList.add("hidden");
  }
}

function renderTable(result) {
  clearChildren(tableWrapEl);

  if (!result || !result.columns || result.columns.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-hint";
    empty.textContent = "No results yet.";
    tableWrapEl.appendChild(empty);
    return;
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  result.columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  result.rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = cell === null || cell === undefined ? "" : String(cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrapEl.appendChild(table);
}

function isDateLike(value) {
  return typeof value === "string" && /^\d{4}-\d{2}(-\d{2})?$/.test(value);
}

function pickChartType(result) {
  if (!result || !result.columns || result.columns.length !== 2 || result.rows.length === 0) {
    return null;
  }
  const firstCol = result.rows.map((r) => r[0]);
  const secondCol = result.rows.map((r) => r[1]);

  const secondIsNumber = secondCol.every((v) => typeof v === "number");
  if (!secondIsNumber) {
    return null;
  }

  if (firstCol.every(isDateLike)) {
    return "line";
  }
  if (firstCol.every((v) => typeof v === "string")) {
    return "bar";
  }
  return null;
}

function renderChart(result) {
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  const type = pickChartType(result);
  if (!type) {
    chartCardEl.classList.add("hidden");
    return;
  }

  chartCardEl.classList.remove("hidden");
  const labels = result.rows.map((r) => String(r[0]));
  const values = result.rows.map((r) => r[1]);

  chartInstance = new Chart(chartCanvasEl, {
    type,
    data: {
      labels,
      datasets: [
        {
          label: result.columns[1],
          data: values,
          backgroundColor: "#2563eb",
          borderColor: "#2563eb",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#c7cad1" }, grid: { color: "#2a2d36" } },
        y: { ticks: { color: "#c7cad1" }, grid: { color: "#2a2d36" } },
      },
    },
  });
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function playReplyAudioChunk(base64) {
  const bytes = base64ToBytes(base64);
  const int16 = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 0x8000;
  }

  const buffer = audioContext.createBuffer(1, float32.length, SAMPLE_RATE);
  buffer.copyToChannel(float32, 0);

  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioContext.destination);

  const now = audioContext.currentTime;
  if (nextPlayTime < now) {
    nextPlayTime = now;
  }
  source.start(nextPlayTime);
  nextPlayTime += buffer.duration;

  scheduledSources.push(source);
  source.onended = () => {
    scheduledSources = scheduledSources.filter((s) => s !== source);
  };
}

function stopPlayback() {
  scheduledSources.forEach((s) => {
    try {
      s.stop();
    } catch (err) {
      // already stopped
    }
  });
  scheduledSources = [];
  if (audioContext) {
    nextPlayTime = audioContext.currentTime;
  }
}

async function handleToolCall(name, callId, args) {
  const body = { ...args, _session_id: sessionId, _question: lastUserQuestion };

  try {
    const resp = await fetch(`/api/agent/${name}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    const result = data.result;
    const card = data.card;

    console.log("[SayQL card]", name, card);

    updateMetricCard(card ? card.definition : null);

    if (name === "query_metric" || name === "run_sql") {
      if (card && card.kind === "error") {
        updateSqlPanel((card && card.sql) || args.sql || "", card.message || "query failed");
        renderTable(null);
        renderChart(null);
      } else if (result && Array.isArray(result.rows)) {
        lastQueryResult = result;
        updateSqlPanel(card.sql || "", null);
        renderTable(result);
        renderChart(result);
      }
    }

    // The model only ever sees model_payload: pre-formatted spoken strings,
    // never a raw number. It must read numbers exactly as given, never
    // compute or convert them itself (that produced a wrong lakh/crore
    // conversion when it saw raw rows directly).
    const modelPayload = data.model_payload !== undefined ? data.model_payload : { error: "no data" };
    pendingToolResults.push({ call_id: callId, result: JSON.stringify(modelPayload) });
  } catch (err) {
    console.error("[SayQL card]", name, "tool call failed", err);
    if (name === "query_metric" || name === "run_sql") {
      updateSqlPanel(args.sql || "", String(err));
    }
    pendingToolResults.push({
      call_id: callId,
      result: JSON.stringify({ error: String(err) }),
    });
  }
}

function flushToolResults() {
  while (pendingToolResults.length > 0) {
    const item = pendingToolResults.shift();
    ws.send(
      JSON.stringify({ type: "tool.result", call_id: item.call_id, result: item.result })
    );
  }
}

function handleMessage(msg) {
  switch (msg.type) {
    case "session.ready":
      sessionReady = true;
      setStatus("listening");
      stopBtn.disabled = false;
      break;

    case "session.ended":
      setStatus("idle");
      break;

    case "session.error":
    case "error":
      showError(msg.message || "session error");
      appendLine("system", "error: " + msg.message);
      break;

    case "input.speech.started":
    case "input.speech.stopped":
      setStatus("listening");
      break;

    case "transcript.user.delta":
      updatePartial("user", msg.text);
      break;

    case "transcript.user":
      finalizeTranscript("user", msg.text);
      break;

    case "reply.started":
      setStatus("speaking");
      turnHadAudio = false;
      turnHadToolCall = false;
      nudgedThisTurn = false;
      break;

    case "reply.audio":
      turnHadAudio = true;
      playReplyAudioChunk(msg.data);
      break;

    case "transcript.agent":
      finalizeTranscript("agent", msg.text);
      break;

    case "reply.done":
      if (msg.status === "interrupted") {
        stopPlayback();
      } else if (!turnHadAudio && !turnHadToolCall && !nudgedThisTurn) {
        // Empty reply guard: nudge once so the agent tries again this turn.
        nudgedThisTurn = true;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "reply.create" }));
        }
      }
      flushToolResults();
      setStatus(sessionReady ? "listening" : "idle");
      break;

    case "tool.call": {
      let args = msg.arguments;
      if (typeof args === "string") {
        try {
          args = JSON.parse(args);
        } catch (err) {
          args = {};
        }
      }
      args = args || {};
      turnHadToolCall = true;
      if (msg.name === "run_sql" || msg.name === "query_metric" || msg.name === "explain_change") {
        setStatus("running query");
      }
      handleToolCall(msg.name, msg.call_id, args);
      break;
    }

    default:
      break;
  }
}

async function start() {
  startBtn.disabled = true;
  setStatus("connecting");
  clearError();

  try {
    const tokenResp = await fetch("/api/voice-token");
    if (!tokenResp.ok) {
      const body = await tokenResp.json().catch(() => ({}));
      throw new Error("token_failure:" + (body.error || "token request failed"));
    }
    const { token } = await tokenResp.json();

    audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
    await audioContext.audioWorklet.addModule("worklet.js");

    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: false, channelCount: 1 },
      });
    } catch (err) {
      throw new Error("mic_denied:" + err.message);
    }

    workletNode = new AudioWorkletNode(audioContext, "mic-processor");
    workletNode.port.onmessage = (event) => {
      if (!sessionReady || !ws || ws.readyState !== WebSocket.OPEN) {
        return;
      }
      const bytes = new Uint8Array(event.data);
      ws.send(JSON.stringify({ type: "input.audio", audio: bytesToBase64(bytes) }));
    };

    const micSource = audioContext.createMediaStreamSource(micStream);
    micSource.connect(workletNode);

    intentionalStop = false;
    sessionId = (crypto.randomUUID && crypto.randomUUID()) || `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    lastUserQuestion = null;
    ws = new WebSocket(`wss://agents.assemblyai.com/v1/ws?token=${token}`);

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: "session.update",
          session: {
            system_prompt: SYSTEM_PROMPT,
            greeting: "Hi, this is SayQL. Ask me about your sales, returns, or customers.",
            tools: TOOLS,
          },
        })
      );
    };

    ws.onmessage = (event) => handleMessage(JSON.parse(event.data));

    ws.onerror = () => {
      showError("Connection error.");
    };

    ws.onclose = (event) => {
      teardownAudio();
      if (!intentionalStop && event.code !== 1000) {
        showError(`Connection closed unexpectedly (code ${event.code}).`);
      }
      setStatus("idle");
      startBtn.disabled = false;
      stopBtn.disabled = true;
      intentionalStop = false;
    };
  } catch (err) {
    const msg = String((err && err.message) || err);
    if (msg.startsWith("token_failure:")) {
      showError("Could not get a voice token: " + msg.slice("token_failure:".length));
    } else if (msg.startsWith("mic_denied:")) {
      showError("Microphone access was denied or unavailable: " + msg.slice("mic_denied:".length));
    } else {
      showError("Error: " + msg);
    }
    setStatus("idle");
    startBtn.disabled = false;
    teardownAudio();
  }
}

function stop() {
  intentionalStop = true;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "session.end" }));
    ws.close();
  }
  teardownAudio();
  setStatus("idle");
  startBtn.disabled = false;
  stopBtn.disabled = true;
}

function teardownAudio() {
  sessionReady = false;
  stopPlayback();
  if (micStream) {
    micStream.getTracks().forEach((t) => t.stop());
  }
  if (audioContext) {
    audioContext.close();
  }
  micStream = null;
  audioContext = null;
  workletNode = null;
}
