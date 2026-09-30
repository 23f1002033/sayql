"use client";

import { useEffect, useState } from "react";

import { fetchHistory, fetchMetrics } from "@/lib/api";
import type { HistoryItem, MetricInfo } from "@/lib/types";

export function Sidebar({
  activeMetric,
  refreshKey,
  isOpen,
  onClose,
}: {
  activeMetric: string | null;
  refreshKey: number;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [metrics, setMetrics] = useState<MetricInfo[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  useEffect(() => {
    fetchMetrics().then(setMetrics);
  }, []);

  useEffect(() => {
    fetchHistory().then(setHistory);
  }, [refreshKey]);

  const visibleHistory = history.filter((h) => h.question);

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`w-72 shrink-0 border-r border-border bg-surface flex flex-col h-full overflow-hidden fixed inset-y-0 left-0 z-50 transition-transform md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Sidebar"
      >
      <div className="p-4 border-b border-border flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-muted">Workspace</div>
          <div className="text-lg font-semibold">Demo Store</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close sidebar"
          className="md:hidden text-muted hover:text-foreground text-xl leading-none px-1"
        >
          &times;
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <section className="p-4 border-b border-border">
          <h2 className="text-xs uppercase tracking-wide text-muted mb-2">Metrics</h2>
          <ul className="space-y-1">
            {metrics.map((m) => (
              <li
                key={m.name}
                className={`rounded-md px-2 py-1.5 text-sm transition-colors ${
                  m.name === activeMetric ? "bg-accent-soft border border-accent/30" : "border border-transparent"
                }`}
              >
                <div className="font-medium">
                  {m.name.replace(/_/g, " ")} <span className="text-muted font-normal">v{m.version}</span>
                </div>
                <div className="text-xs text-muted">{m.description}</div>
              </li>
            ))}
          </ul>
        </section>

        <section className="p-4">
          <h2 className="text-xs uppercase tracking-wide text-muted mb-2">History</h2>
          {visibleHistory.length === 0 ? (
            <p className="text-xs text-muted">No questions yet.</p>
          ) : (
            <ul className="space-y-2">
              {visibleHistory.map((h) => (
                <li key={h.id} className="text-xs">
                  <div className="text-foreground">{h.question}</div>
                  <div className="text-muted">
                    {h.status}
                    {h.elapsed_ms != null ? ` - ${h.elapsed_ms}ms` : ""}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </aside>
    </>
  );
}
