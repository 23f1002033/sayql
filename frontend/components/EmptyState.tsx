const EXAMPLES = [
  { kind: "KPI", text: "What was net revenue last month?" },
  { kind: "Breakdown", text: "What were returns last week by city?" },
  { kind: "Trend", text: "Show me net revenue by month for the last year." },
  { kind: "Why", text: "Why did returns go up for the Wireless Earbuds Pro this month?" },
];

export function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center px-6 py-10">
      <h2 className="text-lg font-semibold mb-1">Ask SayQL about your store</h2>
      <p className="text-sm text-muted mb-6">Press the mic and try one of these out loud:</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl w-full">
        {EXAMPLES.map((ex) => (
          <div key={ex.kind} className="rounded-lg border border-border bg-surface p-3 text-left">
            <div className="text-xs uppercase tracking-wide text-accent mb-1 font-medium">{ex.kind}</div>
            <div className="text-sm">&ldquo;{ex.text}&rdquo;</div>
          </div>
        ))}
      </div>
    </div>
  );
}
