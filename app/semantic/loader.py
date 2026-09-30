from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

METRICS_PATH = Path(__file__).parent / "metrics.yaml"


@dataclass
class MetricDef:
    name: str
    version: int
    owner: str
    description: str
    formula: str
    unit: str
    base_table: str
    value_expr: str
    date_column: str
    workspace_column: str
    dimension_columns: Dict[str, str] = field(default_factory=dict)
    default_grain: str = "month"
    aliases: List[str] = field(default_factory=list)
    why_components: Optional[Dict[str, str]] = None


_cache = None


def load_metrics():
    global _cache
    if _cache is None:
        with open(METRICS_PATH) as f:
            raw = yaml.safe_load(f)

        metrics = {}
        for name, m in raw["metrics"].items():
            sql = m["sql"]
            metrics[name] = MetricDef(
                name=name,
                version=m["version"],
                owner=m["owner"],
                description=m["description"].strip(),
                formula=m["formula"],
                unit=m["unit"],
                base_table=" ".join(sql["base_table"].split()),
                value_expr=sql["value_expr"],
                date_column=sql["date_column"],
                workspace_column=sql["workspace_column"],
                dimension_columns=sql.get("dimension_columns", {}),
                default_grain=m.get("default_grain", "month"),
                aliases=m.get("aliases", []),
                why_components=m.get("why_components"),
            )

        ambiguous_terms = raw.get("ambiguous_terms", {})
        _cache = (metrics, ambiguous_terms)

    return _cache


def get_metric(name: str) -> MetricDef:
    metrics, _ = load_metrics()
    return metrics[name]
