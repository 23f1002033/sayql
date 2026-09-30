"use client";

import type { VoiceStatus } from "@/lib/types";

export function AskBar({
  status,
  isRunning,
  onStart,
  onStop,
}: {
  status: VoiceStatus;
  isRunning: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  const isActive = status === "listening" || status === "speaking";

  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={isRunning ? onStop : onStart}
          aria-label={isRunning ? "Stop listening" : "Start listening"}
          className={`h-11 w-11 shrink-0 rounded-full flex items-center justify-center text-white transition-colors ${
            isRunning ? "bg-danger hover:bg-danger/90" : "bg-accent hover:bg-accent/90"
          }`}
        >
          {isRunning ? <StopIcon /> : <MicIcon />}
        </button>

        <p className="flex-1 min-w-0 text-sm text-muted">Tap the mic and ask out loud.</p>

        {isActive && (
          <div className="hidden sm:flex items-end gap-0.5 h-6" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <span
                key={i}
                className="w-1 bg-accent rounded-full animate-pulse"
                style={{ height: `${8 + (i % 2) * 8}px`, animationDelay: `${i * 120}ms` }}
              />
            ))}
          </div>
        )}

        <span className="text-xs text-muted w-24 text-right capitalize shrink-0">{status}</span>
      </div>
    </div>
  );
}

function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M19 11v1a7 7 0 0 1-14 0v-1M12 19v3"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor" />
    </svg>
  );
}
