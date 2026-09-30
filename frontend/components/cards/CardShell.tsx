"use client";

import { useState } from "react";

import type { Card } from "@/lib/types";

export function CardShell({
  card,
  children,
  isSample,
}: {
  card: Card;
  children: React.ReactNode;
  isSample?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  async function copySql() {
    if (!card.sql) return;
    try {
      await navigator.clipboard.writeText(card.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard denied; nothing to fall back to here
    }
  }

  const hasDetails = card.definition || (card.evidence && card.evidence.length > 0) || card.sql;
  const hasFooter = card.definition || card.row_count != null || card.elapsed_ms != null;

  return (
    <div className="relative rounded-xl border border-border bg-surface p-4 shadow-sm">
      {isSample && (
        <span className="absolute top-3 right-3 text-[10px] uppercase tracking-wide text-muted border border-border rounded-full px-2 py-0.5">
          Sample
        </span>
      )}
      {children}

      {hasDetails && (
        <div className="mt-3 space-y-2 border-t border-border pt-3">
          {card.definition && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted select-none">Definition</summary>
              <div className="mt-1 pl-1">
                <div className="font-medium">
                  {card.definition.name.replace(/_/g, " ")} (v{card.definition.version})
                </div>
                <p className="text-muted">{card.definition.description}</p>
              </div>
            </details>
          )}
          {card.evidence && card.evidence.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted select-none">Evidence</summary>
              <ul className="mt-1 list-disc pl-6 space-y-0.5">
                {card.evidence.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </details>
          )}
          {card.sql && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted select-none">SQL</summary>
              <div className="mt-1">
                <pre className="whitespace-pre-wrap break-words rounded-md bg-background border border-border p-2 text-xs font-mono">
                  {card.sql}
                </pre>
                <button type="button" onClick={copySql} className="mt-1 text-xs text-accent hover:underline">
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </details>
          )}
        </div>
      )}

      {hasFooter && (
        <div className="mt-3 pt-2 border-t border-border text-xs text-muted flex flex-wrap gap-x-2">
          {card.definition && <span>Definition v{card.definition.version}</span>}
          {card.row_count != null && <span>| {card.row_count} rows</span>}
          {card.elapsed_ms != null && <span>| {card.elapsed_ms} ms</span>}
          {card.sql && <span>| read-only</span>}
        </div>
      )}
    </div>
  );
}
