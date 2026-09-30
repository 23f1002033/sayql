import { BreakdownBody, TrendBody } from "@/components/cards/TimeSeriesCards";
import { CardShell } from "@/components/cards/CardShell";
import { ClarificationBody } from "@/components/cards/ClarificationCard";
import { ErrorBody } from "@/components/cards/ErrorCard";
import { KpiBody } from "@/components/cards/KpiCard";
import { WhyBody } from "@/components/cards/WhyCard";
import type { FeedItem } from "@/lib/types";

export function AnswerCard({ item }: { item: FeedItem }) {
  const { card } = item;

  return (
    <CardShell card={card} isSample={item.isSample}>
      {card.kind === "kpi" && <KpiBody card={card} />}
      {card.kind === "breakdown" && <BreakdownBody card={card} />}
      {card.kind === "trend" && <TrendBody card={card} />}
      {card.kind === "why" && <WhyBody card={card} />}
      {card.kind === "clarification" && <ClarificationBody card={card} />}
      {card.kind === "error" && <ErrorBody card={card} />}
    </CardShell>
  );
}
