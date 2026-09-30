"use client";

import { useEffect, useMemo, useState } from "react";

import { AnswerCard } from "@/components/AnswerCard";
import { AskBar } from "@/components/AskBar";
import { EmptyState } from "@/components/EmptyState";
import { Sidebar } from "@/components/Sidebar";
import { useVoiceAgent } from "@/hooks/useVoiceAgent";
import { fetchSampleCards } from "@/lib/api";
import type { FeedItem } from "@/lib/types";

type DebugApplyCard = (name: string, card: unknown) => void;

declare global {
  interface Window {
    __sayqlDebug?: { applyCard: DebugApplyCard; showError: (text: string) => void };
  }
}

export default function Home() {
  const { status, feed, followups, error, isRunning, start, stop, applyCard, showError } = useVoiceAgent();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [samples, setSamples] = useState<FeedItem[]>([]);

  const activeMetric = useMemo(() => feed[0]?.card.definition?.name ?? null, [feed]);
  const refreshKey = feed.length;

  // Sample cards render on first load so the screen never opens empty; they
  // never touch /api/voice-token or the WebSocket, and they collapse as soon
  // as a real question produces a real card.
  useEffect(() => {
    fetchSampleCards().then(setSamples);
  }, []);

  // Screenshot/E2E harness only: lets Playwright drive real card states via
  // the same /api/agent/* endpoints without needing a live WS voice session.
  useEffect(() => {
    window.__sayqlDebug = { applyCard: applyCard as DebugApplyCard, showError };
    return () => {
      delete window.__sayqlDebug;
    };
  }, [applyCard, showError]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar
        activeMetric={activeMetric}
        refreshKey={refreshKey}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <header className="border-b border-border bg-surface px-4 py-3 flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
            className="md:hidden text-muted hover:text-foreground"
          >
            <MenuIcon />
          </button>
          <div>
            <h1 className="text-base font-semibold">SayQL</h1>
            <p className="text-xs text-muted">Ask about sales, returns, or customers - out loud.</p>
          </div>
        </header>

        {error && (
          <div role="alert" className="bg-danger-soft text-danger text-sm px-4 py-2 border-b border-border">
            {error}
          </div>
        )}

        <main className="flex-1 overflow-y-auto px-4 py-4">
          {feed.length === 0 ? (
            <EmptyState samples={samples} />
          ) : (
            <div className="max-w-2xl mx-auto space-y-4">
              {feed.map((item, idx) => (
                <div key={item.id}>
                  <AnswerCard item={item} />
                  {idx === 0 && followups.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {followups.map((q) => (
                        <span
                          key={q}
                          className="text-xs rounded-full border border-border bg-surface px-3 py-1 text-muted"
                        >
                          {q}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </main>

        <AskBar status={status} isRunning={isRunning} onStart={start} onStop={stop} />
      </div>
    </div>
  );
}

function MenuIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
