import type { Card } from "@/lib/types";

export function KpiBody({ card }: { card: Card }) {
  return (
    <div>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-3xl font-semibold tracking-tight">{card.headline_value}</span>
        {card.period_label && <span className="text-sm text-muted">{card.period_label}</span>}
      </div>
      {card.narration_seed && <p className="mt-2 text-sm text-foreground">{card.narration_seed}</p>}
    </div>
  );
}
