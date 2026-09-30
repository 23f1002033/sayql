import type { Card } from "@/lib/types";

// Tested against a real synthesized voice session: nudging the agent via
// reply.create + instructions naming the chosen option DOES sometimes work
// (it called resolve_metric and query_metric correctly once), but it
// stalled after the first tool call in 2 of 3 runs even with a fully
// explicit, step-by-step instruction. That's not reliable enough to wire as
// a real control - a button that silently does nothing most of the time is
// worse than an honest hint. So these are plain, non-interactive chips.
export function ClarificationBody({ card }: { card: Card }) {
  return (
    <div>
      <p className="text-sm mb-3">{card.message}</p>
      <div className="flex flex-wrap gap-2">
        {(card.options ?? []).map((opt) => (
          <span
            key={opt}
            className="text-sm rounded-full border border-dashed border-border bg-background px-3 py-1.5 text-muted"
          >
            Say: {opt.replace(/_/g, " ")}
          </span>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">
        The Voice Agent API has no text-input channel, so these are reminders of the wording, not buttons - say
        your choice out loud.
      </p>
    </div>
  );
}
