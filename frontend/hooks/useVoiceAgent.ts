"use client";

import { useCallback, useRef, useState } from "react";

import { BASE_PATH } from "@/lib/basePath";
import type { Card, FeedItem, VoiceStatus } from "@/lib/types";
import { SAMPLE_RATE, SYSTEM_PROMPT, TOOLS } from "@/lib/voiceConfig";

export interface TranscriptLine {
  id: string;
  role: "user" | "agent" | "system";
  text: string;
  partial?: boolean;
}

let idCounter = 0;
function nextId(): string {
  idCounter += 1;
  return `t${idCounter}-${Date.now()}`;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...Array.from(bytes.subarray(i, i + chunk)));
  }
  return btoa(binary);
}

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// Same protocol as static/app.js: token first, session.update on open,
// tool.result only sent after reply.done, empty-reply guard, barge-in via
// resetting the playback schedule on an interrupted reply.
export function useVoiceAgent() {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [followups, setFollowups] = useState<string[]>([]);
  const [error, setErrorState] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const sessionReadyRef = useRef(false);
  const intentionalStopRef = useRef(false);
  const sessionIdRef = useRef<string | null>(null);
  const lastUserQuestionRef = useRef<string | null>(null);

  const nextPlayTimeRef = useRef(0);
  const scheduledSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const partialLineIdRef = useRef<string | null>(null);
  const pendingToolResultsRef = useRef<{ call_id: string; result: string }[]>([]);

  const turnHadAudioRef = useRef(false);
  const turnHadToolCallRef = useRef(false);
  const nudgedThisTurnRef = useRef(false);

  const showError = useCallback((text: string) => setErrorState(text), []);
  const clearError = useCallback(() => setErrorState(null), []);

  const appendLine = useCallback((role: TranscriptLine["role"], text: string) => {
    setTranscript((prev) => [...prev, { id: nextId(), role, text }]);
  }, []);

  const updatePartial = useCallback((role: "user" | "agent", text: string) => {
    setTranscript((prev) => {
      if (partialLineIdRef.current) {
        const id = partialLineIdRef.current;
        return prev.map((l) => (l.id === id ? { ...l, text, partial: true } : l));
      }
      const id = nextId();
      partialLineIdRef.current = id;
      return [...prev, { id, role, text, partial: true }];
    });
  }, []);

  const finalizeTranscript = useCallback((role: "user" | "agent", text: string) => {
    if (role === "user") {
      lastUserQuestionRef.current = text;
    }
    setTranscript((prev) => {
      if (partialLineIdRef.current && role === "user") {
        const id = partialLineIdRef.current;
        partialLineIdRef.current = null;
        return prev.map((l) => (l.id === id ? { id, role, text, partial: false } : l));
      }
      return [...prev, { id: nextId(), role, text, partial: false }];
    });
  }, []);

  const stopPlayback = useCallback(() => {
    scheduledSourcesRef.current.forEach((s) => {
      try {
        s.stop();
      } catch {
        // already stopped
      }
    });
    scheduledSourcesRef.current = [];
    if (audioContextRef.current) {
      nextPlayTimeRef.current = audioContextRef.current.currentTime;
    }
  }, []);

  const playReplyAudioChunk = useCallback((base64: string) => {
    const audioContext = audioContextRef.current;
    if (!audioContext) return;

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
    if (nextPlayTimeRef.current < now) {
      nextPlayTimeRef.current = now;
    }
    source.start(nextPlayTimeRef.current);
    nextPlayTimeRef.current += buffer.duration;

    scheduledSourcesRef.current.push(source);
    source.onended = () => {
      scheduledSourcesRef.current = scheduledSourcesRef.current.filter((s) => s !== source);
    };
  }, []);

  // Shared by the real tool.call path and the Playwright screenshot harness,
  // which drives the same /api/agent/* endpoints without a live WS session.
  const applyCard = useCallback((name: string, card: Card | undefined) => {
    if (!card) return;

    if (card.kind === "followups") {
      // Rendered as chips under the latest card, not as a card of its own.
      setFollowups(card.followups ?? []);
      return;
    }

    if (name === "resolve_metric" && card.kind === "kpi") {
      // A successful lookup is an intermediate step for the agent, not an
      // answer - it has no headline value of its own. The query_metric or
      // explain_change call that follows carries the same definition and
      // does show up, so the sidebar's "active metric" still updates.
      return;
    }

    setFeed((prev) => [{ id: nextId(), toolName: name, card, timestamp: Date.now() }, ...prev]);
    setFollowups([]);
  }, []);

  const handleToolCall = useCallback(
    async (name: string, callId: string, args: Record<string, unknown>) => {
      const body = { ...args, _session_id: sessionIdRef.current, _question: lastUserQuestionRef.current };

      try {
        const resp = await fetch(`/api/agent/${name}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await resp.json();

        // eslint-disable-next-line no-console
        console.log("[SayQL card]", name, data.card);
        applyCard(name, data.card);

        // The model only ever sees model_payload: pre-formatted spoken
        // strings, never a raw number. It must read numbers exactly as
        // given, never compute or convert them itself.
        const modelPayload = data.model_payload !== undefined ? data.model_payload : { error: "no data" };
        pendingToolResultsRef.current.push({ call_id: callId, result: JSON.stringify(modelPayload) });
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[SayQL card]", name, "tool call failed", err);
        pendingToolResultsRef.current.push({ call_id: callId, result: JSON.stringify({ error: String(err) }) });
      }
    },
    [applyCard]
  );

  const flushToolResults = useCallback(() => {
    const ws = wsRef.current;
    while (pendingToolResultsRef.current.length > 0) {
      const item = pendingToolResultsRef.current.shift();
      if (item) {
        ws?.send(JSON.stringify({ type: "tool.result", call_id: item.call_id, result: item.result }));
      }
    }
  }, []);

  const teardownAudio = useCallback(() => {
    sessionReadyRef.current = false;
    stopPlayback();
    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    audioContextRef.current?.close();
    micStreamRef.current = null;
    audioContextRef.current = null;
  }, [stopPlayback]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleMessage = useCallback(
    (msg: any) => {
      switch (msg.type) {
        case "session.ready":
          sessionReadyRef.current = true;
          setStatus("listening");
          setIsRunning(true);
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
          turnHadAudioRef.current = false;
          turnHadToolCallRef.current = false;
          nudgedThisTurnRef.current = false;
          break;

        case "reply.audio":
          turnHadAudioRef.current = true;
          playReplyAudioChunk(msg.data);
          break;

        case "transcript.agent":
          finalizeTranscript("agent", msg.text);
          break;

        case "reply.done":
          if (msg.status === "interrupted") {
            stopPlayback();
          } else if (!turnHadAudioRef.current && !turnHadToolCallRef.current && !nudgedThisTurnRef.current) {
            nudgedThisTurnRef.current = true;
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({ type: "reply.create" }));
            }
          }
          flushToolResults();
          setStatus(sessionReadyRef.current ? "listening" : "idle");
          break;

        case "tool.call": {
          let args = msg.arguments;
          if (typeof args === "string") {
            try {
              args = JSON.parse(args);
            } catch {
              args = {};
            }
          }
          args = args || {};
          turnHadToolCallRef.current = true;
          if (msg.name === "run_sql" || msg.name === "query_metric" || msg.name === "explain_change") {
            setStatus("running query");
          }
          handleToolCall(msg.name, msg.call_id, args);
          break;
        }

        default:
          break;
      }
    },
    [appendLine, finalizeTranscript, flushToolResults, handleToolCall, playReplyAudioChunk, showError, stopPlayback, updatePartial]
  );

  const start = useCallback(async () => {
    setStatus("connecting");
    clearError();

    try {
      const tokenResp = await fetch("/api/voice-token");
      if (!tokenResp.ok) {
        const body = await tokenResp.json().catch(() => ({}));
        throw new Error("token_failure:" + (body.error || "token request failed"));
      }
      const { token } = await tokenResp.json();

      const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = audioContext;
      await audioContext.audioWorklet.addModule(`${BASE_PATH}/worklet.js`);

      let micStream: MediaStream;
      try {
        micStream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: false, channelCount: 1 },
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        throw new Error("mic_denied:" + message);
      }
      micStreamRef.current = micStream;

      const workletNode = new AudioWorkletNode(audioContext, "mic-processor");
      workletNode.port.onmessage = (event) => {
        if (!sessionReadyRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return;
        }
        const bytes = new Uint8Array(event.data);
        wsRef.current.send(JSON.stringify({ type: "input.audio", audio: bytesToBase64(bytes) }));
      };

      const micSource = audioContext.createMediaStreamSource(micStream);
      micSource.connect(workletNode);

      intentionalStopRef.current = false;
      sessionIdRef.current =
        (crypto.randomUUID && crypto.randomUUID()) || `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      lastUserQuestionRef.current = null;

      const ws = new WebSocket(`wss://agents.assemblyai.com/v1/ws?token=${token}`);
      wsRef.current = ws;

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
        if (!intentionalStopRef.current && event.code !== 1000) {
          showError(`Connection closed unexpectedly (code ${event.code}).`);
        }
        setStatus("idle");
        setIsRunning(false);
        intentionalStopRef.current = false;
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.startsWith("token_failure:")) {
        showError("Could not get a voice token: " + msg.slice("token_failure:".length));
      } else if (msg.startsWith("mic_denied:")) {
        showError("Microphone access was denied or unavailable: " + msg.slice("mic_denied:".length));
      } else {
        showError("Error: " + msg);
      }
      setStatus("idle");
      setIsRunning(false);
      teardownAudio();
    }
  }, [clearError, handleMessage, showError, teardownAudio]);

  const stop = useCallback(() => {
    intentionalStopRef.current = true;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "session.end" }));
      wsRef.current.close();
    }
    teardownAudio();
    setStatus("idle");
    setIsRunning(false);
  }, [teardownAudio]);

  return { status, transcript, feed, followups, error, isRunning, start, stop, applyCard, showError };
}
