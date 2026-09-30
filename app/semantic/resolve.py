from dataclasses import dataclass
from typing import List, Optional

from app.semantic.loader import MetricDef, load_metrics

DISMISSIVE_TERMS = {"any", "either", "whatever", "you pick", "either one", "doesn't matter", "does not matter"}


@dataclass
class ResolveResult:
    status: str  # "found" | "ambiguous" | "not_found"
    metric: Optional[MetricDef] = None
    options: Optional[List[str]] = None
    message: Optional[str] = None
    used_default: bool = False


def resolve(term: str, accept_default: bool = False) -> ResolveResult:
    metrics, ambiguous_terms = load_metrics()
    term_norm = (term or "").strip().lower()

    if term_norm in ambiguous_terms:
        entry = ambiguous_terms[term_norm]
        options = entry["options"]
        default = entry.get("default")

        if accept_default and default:
            metric = metrics[default]
            return ResolveResult(
                status="found",
                metric=metric,
                used_default=True,
                message=f"'{term}' is ambiguous, so I used {default}, the default for '{term}'.",
            )

        return ResolveResult(
            status="ambiguous",
            options=options,
            message=f"'{term}' could mean {' or '.join(options)}. Which one do you want?",
        )

    # A dismissive answer on its own (no ambiguous term repeated alongside
    # it) can't be resolved without knowing which prior question it answers -
    # resolve() is stateless. The agent is expected to re-call with the
    # original term and accept_default=True instead; this only documents
    # the case so a bare "whatever" doesn't get treated as an unknown metric.
    if term_norm in DISMISSIVE_TERMS:
        return ResolveResult(
            status="not_found",
            options=sorted(metrics.keys()),
            message=f"'{term}' does not name a metric on its own; resolve the original term with accept_default.",
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
