"use client";

import { useState } from "react";

import type { Card } from "@/lib/types";

// The Voice Agent API has no text-turn message type (confirmed against the
// docs: only session.update/resume/end, input.audio, tool.result, and
// reply.create with an optional instructions field - none of which inject a
// user utterance). So these options are hints to say out loud, not buttons
// that actually answer the agent.
export function ClarificationBody({ card }: { card: Card }) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div>
      <p className="text-sm mb-3">{card.message}</p>
      <div className="flex flex-wrap gap-2">
        {(card.options ?? []).map((opt) => (
          <button
            key={opt}
            type="button"
            title="Voice only - say this out loud"
            onClick={() => setSelected(opt)}
            aria-pressed={selected === opt}
            className={`text-sm rounded-full border px-3 py-1.5 transition-colors ${
              selected === opt
                ? "border-accent bg-accent-soft text-accent"
                : "border-border bg-background hover:bg-accent-soft"
            }`}
          >
            {opt.replace(/_/g, " ")}
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">
        Say your choice out loud - the Voice Agent API has no text-input channel, so tapping a button here is
        just a reminder of the wording, not an answer sent to the agent.
      </p>
    </div>
  );
}
