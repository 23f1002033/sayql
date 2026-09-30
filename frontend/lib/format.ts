// Display-only formatting. The backend (app/tools.py, app/format.py) is the
// source of truth for every number - card.headline_value etc. already
// arrive as formatted strings. This file only formats the RAW numbers a
// card also carries for charts (chart_series, ratio numerator/denominator),
// which need axis-friendly numeric values, not pre-baked strings.

const LAKH = 100_000;
const CRORE = 10_000_000;

export function formatByUnit(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "n/a";
  if (unit === "currency") return formatCurrency(value);
  if (unit === "count") return formatCount(value);
  if (unit === "percent") return `${(value * 100).toFixed(2)}%`;
  return String(value);
}

function formatCurrency(value: number): string {
  const sign = value < 0 ? "-" : "";
  const v = Math.abs(value);
  if (v >= CRORE) return `${sign}Rs ${(v / CRORE).toFixed(2)} crore`;
  if (v >= LAKH) return `${sign}Rs ${(v / LAKH).toFixed(2)} lakh`;
  if (v >= 1000) return `${sign}Rs ${(v / 1000).toFixed(1)} thousand`;
  return `${sign}Rs ${indianGrouping(v.toFixed(0))}`;
}

function formatCount(value: number): string {
  const sign = value < 0 ? "-" : "";
  const v = Math.abs(value);
  return Number.isInteger(v) ? `${sign}${v} units` : `${sign}${v.toFixed(1)} units`;
}

// Indian digit grouping: last 3 digits, then groups of 2 (12,34,567).
function indianGrouping(digits: string): string {
  if (digits.length <= 3) return digits;
  const last3 = digits.slice(-3);
  const rest = digits.slice(0, -3);
  const grouped = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${grouped},${last3}`;
}

export function formatPercentPoints(value: number): string {
  return `${value >= 0 ? "up" : "down"} ${Math.abs(value).toFixed(1)} percentage points`;
}
