"use client";

import { useEffect, useState } from "react";

import { AnswerCard } from "@/components/AnswerCard";
import { fetchReplayItems, type ReplayItem } from "@/lib/api";

// Renders a fixed list of demo questions as real card payloads, for slide
// screenshots. Calls the same /api/agent/* endpoints the voice tools use;
// no numbers are computed or written by hand here. Never touches
// /api/voice-token or the WebSocket.
export default function ReplayPage() {
  const [items, setItems] = useState<ReplayItem[]>([]);

  useEffect(() => {
    fetchReplayItems().then(setItems);
  }, []);

  return (
    <div className="min-h-screen bg-background px-8 py-10">
      <div className="mx-auto max-w-2xl space-y-10">
        {items.map((r) => (
          <div key={r.id}>
            <h2 className="text-xs uppercase tracking-wide text-muted mb-2">{r.title}</h2>
            <div id={`card-${r.id}`}>{r.item && <AnswerCard item={r.item} />}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
