import type { HistoryItem, MetricInfo } from "./types";

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
