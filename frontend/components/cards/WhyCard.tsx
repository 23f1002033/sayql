"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatByUnit } from "@/lib/format";
import type { Card } from "@/lib/types";

export function WhyBody({ card }: { card: Card }) {
  const unit = card.definition?.unit ?? "count";
  const isUp = card.delta ? card.delta.absolute >= 0 : true;

  return (
    <div>
      <div className="flex items-baseline gap-2 flex-wrap">
        {card.previous_value && <span className="text-lg text-muted line-through decoration-1">{card.previous_value}</span>}
        <span className="text-2xl font-semibold tracking-tight">{card.headline_value}</span>
        {card.delta && (
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              isUp ? "bg-accent-soft text-accent" : "bg-danger-soft text-danger"
            }`}
          >
            {card.delta.text}
          </span>
        )}
      </div>

      {card.narration_seed && <p className="mt-2 text-sm text-foreground">{card.narration_seed}</p>}

      {card.low_base && card.low_base_note && (
        <p className="mt-2 text-xs rounded-md bg-amber-50 border border-amber-200 text-amber-800 px-2 py-1.5">
          Note: {card.low_base_note}
        </p>
      )}
      {card.volume_context_note && (
        <p className="mt-2 text-xs rounded-md bg-accent-soft text-accent px-2 py-1.5">{card.volume_context_note}</p>
      )}

      {card.ratio ? (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <RatioBar
            label={card.ratio.numerator_metric}
            unit={card.ratio.numerator_unit}
            previous={card.ratio.previous_numerator}
            current={card.ratio.current_numerator}
          />
          <RatioBar
            label={card.ratio.denominator_metric}
            unit={card.ratio.denominator_unit}
            previous={card.ratio.previous_denominator}
            current={card.ratio.current_denominator}
          />
          <p className="sm:col-span-2 text-sm text-foreground bg-background border border-border rounded-md p-2">
            {card.ratio.driver_summary}
          </p>
        </div>
      ) : (
        card.chart_series &&
        card.chart_series.length > 0 && (
          <div className="h-48 mt-4 -ml-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={card.chart_series}
                layout="vertical"
                margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e3e6eb" />
                <XAxis type="number" tickFormatter={(v) => formatByUnit(v, unit)} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="label" width={90} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => formatByUnit(Number(v), unit)} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {card.chart_series.map((entry, idx) => (
                    <Cell key={entry.label} fill={idx === 0 ? "#2563eb" : "#c7d2fe"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )
      )}
    </div>
  );
}

function RatioBar({
  label,
  unit,
  previous,
  current,
}: {
  label: string;
  unit: string;
  previous: number;
  current: number;
}) {
  const max = Math.max(previous, current, 1);
  return (
    <div>
      <div className="text-xs text-muted mb-1">{label.replace(/_/g, " ")}</div>
      <div className="space-y-1">
        <BarRow value={previous} max={max} unit={unit} color="#c7d2fe" tag="before" />
        <BarRow value={current} max={max} unit={unit} color="#2563eb" tag="now" />
      </div>
    </div>
  );
}

function BarRow({
  value,
  max,
  unit,
  color,
  tag,
}: {
  value: number;
  max: number;
  unit: string;
  color: string;
  tag: string;
}) {
  const pct = Math.max(4, (value / max) * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-10 text-muted shrink-0">{tag}</span>
      <div className="flex-1 h-3 rounded bg-gray-100 overflow-hidden">
        <div className="h-full rounded" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="w-20 text-right shrink-0">{formatByUnit(value, unit)}</span>
    </div>
  );
}
