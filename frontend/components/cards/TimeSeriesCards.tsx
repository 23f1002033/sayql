"use client";

import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatByUnit } from "@/lib/format";
import type { Card } from "@/lib/types";

export function BreakdownBody({ card }: { card: Card }) {
  const unit = card.definition?.unit ?? "count";
  const data = card.chart_series ?? [];
  return (
    <div>
      {card.period_label && <div className="text-sm text-muted mb-1">{card.period_label}</div>}
      {card.narration_seed && <p className="text-sm mb-3">{card.narration_seed}</p>}
      <div className="h-56 -ml-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 16, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e6eb" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => formatByUnit(v, unit)} tick={{ fontSize: 11 }} width={72} />
            <Tooltip formatter={(v) => formatByUnit(Number(v), unit)} />
            <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function TrendBody({ card }: { card: Card }) {
  const unit = card.definition?.unit ?? "count";
  const data = card.chart_series ?? [];
  return (
    <div>
      {card.period_label && <div className="text-sm text-muted mb-1">{card.period_label}</div>}
      {card.narration_seed && <p className="text-sm mb-3">{card.narration_seed}</p>}
      <div className="h-56 -ml-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 16, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e6eb" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => formatByUnit(v, unit)} tick={{ fontSize: 11 }} width={72} />
            <Tooltip formatter={(v) => formatByUnit(Number(v), unit)} />
            <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
