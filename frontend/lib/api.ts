import type { Card, FeedItem, HistoryItem, MetricInfo } from "./types";

export async function fetchMetrics(): Promise<MetricInfo[]> {
  const resp = await fetch("/api/metrics");
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.metrics ?? [];
}

export async function fetchHistory(limit = 20): Promise<HistoryItem[]> {
  const resp = await fetch(`/api/history?limit=${limit}`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.history ?? [];
}

// Fixed to the same "today" anchor (2026-09-30) the demo data and system
// prompt use elsewhere: previous full month, and the 7 full days before today.
const SAMPLE_REQUESTS: { id: string; args: Record<string, unknown> }[] = [
  {
    id: "sample-net-revenue",
    args: { metric: "net_revenue", time_range: { start: "2026-08-01", end: "2026-08-31" } },
  },
  {
    id: "sample-returns-by-city",
    args: {
      metric: "refund_amount",
      dimensions: ["city"],
      time_range: { start: "2026-09-23", end: "2026-09-29" },
    },
  },
];

// Calls the same query pipeline a real question uses, but directly over
// /api/agent/query_metric - no /api/voice-token call, no WebSocket, no voice
// session. Safe to run on first load before the user has asked anything.
export async function fetchSampleCards(): Promise<FeedItem[]> {
  const results = await Promise.all(
    SAMPLE_REQUESTS.map(async ({ id, args }) => {
      try {
        const resp = await fetch("/api/agent/query_metric", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(args),
        });
        if (!resp.ok) return null;
        const data = await resp.json();
        const card: Card | undefined = data.card;
        if (!card) return null;
        return { id, toolName: "query_metric", card, timestamp: Date.now(), isSample: true } as FeedItem;
      } catch {
        return null;
      }
    })
  );
  return results.filter((item): item is FeedItem => item !== null);
}

export interface ReplayItem {
  id: string;
  title: string;
  item: FeedItem | null;
}

// Fixed demo questions for slide screenshots, hitting the planted stories in
// the seed data. Same date anchors as SAMPLE_REQUESTS and the voice system
// prompt (today = 2026-09-30).
const REPLAY_REQUESTS: { id: string; title: string; tool: string; args: Record<string, unknown> }[] = [
  {
    id: "kpi",
    title: "KPI",
    tool: "query_metric",
    args: { metric: "net_revenue", time_range: { start: "2026-08-01", end: "2026-08-31" } },
  },
  {
    id: "breakdown",
    title: "Breakdown",
    tool: "query_metric",
    args: {
      metric: "refund_amount",
      dimensions: ["city"],
      time_range: { start: "2026-09-23", end: "2026-09-29" },
    },
  },
  {
    id: "trend",
    title: "Trend",
    tool: "query_metric",
    args: {
      metric: "net_revenue",
      time_range: { start: "2025-10-01", end: "2026-09-30" },
      grain: "month",
    },
  },
  {
    id: "clarification",
    title: "Clarification",
    tool: "resolve_metric",
    args: { term: "revenue" },
  },
  {
    id: "why-additive",
    title: "Why (additive, with volume note)",
    tool: "explain_change",
    args: {
      metric: "refund_amount",
      current_start: "2026-09-01",
      current_end: "2026-09-30",
      compare_start: "2026-08-01",
      compare_end: "2026-08-31",
      dimension: "city",
      filters: [{ field: "product_name", value: "Wireless Earbuds Pro" }],
    },
  },
  {
    id: "why-ratio",
    title: "Why (ratio, with low_base note)",
    tool: "explain_change",
    args: {
      metric: "return_rate",
      current_start: "2026-09-01",
      current_end: "2026-09-30",
      compare_start: "2026-08-01",
      compare_end: "2026-08-31",
      filters: [{ field: "product_name", value: "Wireless Earbuds Pro" }],
    },
  },
];

// Renders the same fixed set of demo questions as real card payloads, for
// slide screenshots. Never touches /api/voice-token or the WebSocket.
export async function fetchReplayItems(): Promise<ReplayItem[]> {
  return Promise.all(
    REPLAY_REQUESTS.map(async ({ id, title, tool, args }) => {
      try {
        const resp = await fetch(`/api/agent/${tool}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(args),
        });
        if (!resp.ok) return { id, title, item: null };
        const data = await resp.json();
        const card: Card | undefined = data.card;
        if (!card) return { id, title, item: null };
        return { id, title, item: { id, toolName: tool, card, timestamp: Date.now() } as FeedItem };
      } catch {
        return { id, title, item: null };
      }
    })
  );
}
