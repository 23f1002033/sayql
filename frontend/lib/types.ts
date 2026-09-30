export type CardKind =
  | "kpi"
  | "breakdown"
  | "trend"
  | "why"
  | "clarification"
  | "error"
  | "followups";

export interface ChartPoint {
  label: string;
  value: number;
}

export interface RatioInfo {
  numerator_metric: string;
  numerator_unit: string;
  denominator_metric: string;
  denominator_unit: string;
  previous_numerator: number;
  current_numerator: number;
  previous_denominator: number;
  current_denominator: number;
  driver: string;
  driver_summary: string;
}

export interface Definition {
  name: string;
  version: number;
  description: string;
  formula: string;
  unit: string;
}

export interface Delta {
  absolute: number;
  percent: number | null;
  text: string;
}

export interface Card {
  kind: CardKind;
  headline_value: string | null;
  previous_value: string | null;
  period_label: string | null;
  delta: Delta | null;
  narration_seed: string | null;
  chart_series: ChartPoint[] | null;
  definition: Definition | null;
  evidence: string[] | null;
  sql: string | null;
  row_count: number | null;
  elapsed_ms: number | null;
  options: string[] | null;
  message: string | null;
  followups: string[] | null;
  low_base: boolean;
  low_base_note: string | null;
  ratio: RatioInfo | null;
  volume_context_note: string | null;
}

export interface FeedItem {
  id: string;
  toolName: string;
  card: Card;
  timestamp: number;
}

export interface MetricInfo {
  name: string;
  version: number;
  description: string;
  unit: string;
}

export interface HistoryItem {
  id: number;
  question: string;
  status: string;
  definition_version: number | null;
  row_count: number | null;
  elapsed_ms: number | null;
  created_at: string | null;
}

export type VoiceStatus = "idle" | "connecting" | "listening" | "speaking" | "running query";
