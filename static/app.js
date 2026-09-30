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
- "last week" means the 7 full days before today.
- "last month" means the full previous calendar month.
- "this month" means the current calendar month, from its start through today.

Rules:
- Before writing SQL for any business term (net revenue, return rate, AOV, active customers, and similar), call get_metric first and use its definition and SQL pattern.
- If get_metric does not find the term, ask one short clarifying question instead of guessing.
- Before the first query that touches a table, call describe_table for that table.
- Use run_sql to answer questions. It only accepts a single SELECT or WITH statement.
- Keep spoken answers to three sentences or fewer. Round numbers for speech (for example, "about 4.2 lakh rupees").
- Always say which metric definition you used when you state a business number.`;

const TOOLS = [
  {
    type: "function",
    name: "list_tables",
    description: "List the tables available in the database, with a short description of each.",
    parameters: { type: "object", properties: {}, required: [] },
  },
  {
    type: "function",
    name: "describe_table",
    description:
      "Get the columns and row count for one table. Call this before the first query that touches a table.",
    parameters: {
      type: "object",
      properties: { name: { type: "string", description: "table name" } },
      required: ["name"],
    },
  },
  {
    type: "function",
    name: "get_metric",
    description:
      "Look up the definition and SQL pattern for a business metric term (for example net revenue, return rate, AOV, active customers). Call this before writing SQL for any business term. If the term is not found, ask one short clarifying question instead of guessing.",
    parameters: {
      type: "object",
      properties: { term: { type: "string", description: "the business term as the user said it" } },
      required: ["term"],
    },
  },
  {
    type: "function",
    name: "run_sql",
    description:
      "Run a single read-only SELECT or WITH query against the store database and get back rows. No writes, no multiple statements.",
    parameters: {
      type: "object",
      properties: { sql: { type: "string", description: "a single SELECT or WITH statement" } },
      required: ["sql"],
    },
  },
];

let ws = null;
let audioContext = null;
let micStream = null;
let workletNode = null;
let sessionReady = false;
let intentionalStop = false;

let nextPlayTime = 0;
let scheduledSources = [];
let partialUserEl = null;
let pendingToolResults = [];

let currentSql = "";
let currentMetric = null;
let lastQueryResult = null;
let chartInstance = null;

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
  const label = (role === "user" ? "You: " : "Agent: ") + text;
  if (partialUserEl && role === "user") {
    partialUserEl.textContent = label;
    partialUserEl.className = "line user";
    partialUserEl = null;
  } else {
    appendLine(role, label);
  }
}

function updateMetricCard(metric) {
  currentMetric = metric;
  if (!metric || !metric.found) {
    metricCardEl.classList.add("hidden");
    return;
  }
  metricCardEl.classList.remove("hidden");
  metricNameEl.textContent = metric.name;
  metricDefinitionEl.textContent = metric.definition;
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
  try {
    const resp = await fetch(`/api/tool/${name}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    const result = await resp.json();

    if (name === "get_metric") {
      updateMetricCard(result);
    }

    if (name === "run_sql") {
      if (result && result.error) {
        updateSqlPanel(args.sql || "", result.error);
        renderTable(null);
        renderChart(null);
      } else {
        lastQueryResult = result;
        updateSqlPanel(args.sql || "", null);
        renderTable(result);
        renderChart(result);
      }
    }

    let compact = result;
    if (name === "run_sql" && result && Array.isArray(result.rows)) {
      compact = {
        columns: result.columns,
        row_count: result.row_count,
        rows: result.rows.slice(0, 20),
        truncated: result.truncated || result.row_count > 20,
      };
    }

    pendingToolResults.push({ call_id: callId, result: JSON.stringify(compact) });
  } catch (err) {
    if (name === "run_sql") {
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
      break;

    case "reply.audio":
      playReplyAudioChunk(msg.data);
      break;

    case "transcript.agent":
      finalizeTranscript("agent", msg.text);
      break;

    case "reply.done":
      if (msg.status === "interrupted") {
        stopPlayback();
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
      if (msg.name === "run_sql") {
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
