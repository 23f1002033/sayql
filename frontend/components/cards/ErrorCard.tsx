import type { Card } from "@/lib/types";

export function ErrorBody({ card }: { card: Card }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-danger font-bold" aria-hidden="true">
        !
      </span>
      <div>
        <p className="text-sm font-medium text-danger">Something went wrong</p>
        <p className="text-sm text-muted">{card.message}</p>
      </div>
    </div>
  );
}
