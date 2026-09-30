from dataclasses import dataclass
from typing import List, Optional

from app.semantic.loader import MetricDef, load_metrics


@dataclass
class ResolveResult:
    status: str  # "found" | "ambiguous" | "not_found"
    metric: Optional[MetricDef] = None
    options: Optional[List[str]] = None
    message: Optional[str] = None


def resolve(term: str) -> ResolveResult:
    metrics, ambiguous_terms = load_metrics()
    term_norm = (term or "").strip().lower()

    if term_norm in ambiguous_terms:
        options = ambiguous_terms[term_norm]
        return ResolveResult(
            status="ambiguous",
            options=options,
            message=f"'{term}' could mean {' or '.join(options)}. Which one do you want?",
        )

    for name, metric in metrics.items():
        aliases = [a.lower() for a in metric.aliases] + [name.replace("_", " ")]
        if term_norm in aliases:
            return ResolveResult(status="found", metric=metric)

    return ResolveResult(
        status="not_found",
        options=sorted(metrics.keys()),
        message=f"'{term}' is not a defined metric.",
    )
