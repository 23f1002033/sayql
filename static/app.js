const startBtn = document.getElementById("start-btn");
const stopBtn = document.getElementById("stop-btn");
const statusEl = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");

const SAMPLE_RATE = 24000;

let ws = null;
let audioContext = null;
let micStream = null;
let workletNode = null;
let sessionReady = false;

let nextPlayTime = 0;
let scheduledSources = [];
let partialUserEl = null;
let pendingToolResults = [];

startBtn.addEventListener("click", start);
stopBtn.addEventListener("click", stop);

function setStatus(text) {
  statusEl.textContent = text;
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
    pendingToolResults.push({ call_id: callId, result: JSON.stringify(result) });
  } catch (err) {
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
      setStatus("error: " + msg.message);
      appendLine("system", "error: " + msg.message);
      break;

    case "input.speech.started":
      setStatus("listening (you)");
      break;

    case "input.speech.stopped":
      setStatus("thinking");
      break;

    case "transcript.user.delta":
      updatePartial("user", msg.text);
      break;

    case "transcript.user":
      finalizeTranscript("user", msg.text);
      break;

    case "reply.started":
      setStatus("speaking (agent)");
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
      handleToolCall(msg.name, msg.call_id, args || {});
      break;
    }

    default:
      break;
  }
}

async function start() {
  startBtn.disabled = true;
  setStatus("connecting");

  try {
    const tokenResp = await fetch("/api/voice-token");
    if (!tokenResp.ok) {
      throw new Error("token request failed");
    }
    const { token } = await tokenResp.json();

    audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
    await audioContext.audioWorklet.addModule("worklet.js");

    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: false, channelCount: 1 },
    });

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

    ws = new WebSocket(`wss://agents.assemblyai.com/v1/ws?token=${token}`);

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: "session.update",
          session: {
            system_prompt:
              "You are SayQL, a quick and friendly voice assistant for a demo. Keep replies short and natural.",
            greeting: "Hi, this is SayQL. Say something and I will respond.",
          },
        })
      );
    };

    ws.onmessage = (event) => handleMessage(JSON.parse(event.data));

    ws.onerror = () => {
      setStatus("error: connection failed");
    };

    ws.onclose = () => {
      teardownAudio();
      setStatus("idle");
      startBtn.disabled = false;
      stopBtn.disabled = true;
    };
  } catch (err) {
    setStatus("error: " + err.message);
    startBtn.disabled = false;
    teardownAudio();
  }
}

function stop() {
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
