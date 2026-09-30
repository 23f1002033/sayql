from dataclasses import dataclass, field
from typing import List, Optional

from app.executor.executor import execute

EXACT_SQL = (
    "SELECT sku, name FROM products "
    "WHERE workspace_id = :workspace_id AND LOWER(name) = LOWER(:name)"
)
PREFIX_SQL = (
    "SELECT sku, name FROM products "
    "WHERE workspace_id = :workspace_id AND LOWER(name) LIKE LOWER(:prefix)"
)


@dataclass
class ProductResolution:
    sku: Optional[str] = None
    candidates: List[dict] = field(default_factory=list)


def resolve_product_name(name: str, workspace_id: str = "demo") -> ProductResolution:
    """Deterministic, code-side product name -> sku lookup.

    Tries a case-insensitive exact match on the product name first, then a
    unique prefix match. The model never gets to pick or guess a sku itself:
    zero or multiple matches both come back as a list of candidates for the
    caller to turn into a clarification instead of guessing.
    """
    name = (name or "").strip()
    if not name:
        return ProductResolution(candidates=[])

    exact = execute(EXACT_SQL, {"workspace_id": workspace_id, "name": name})
    if exact["row_count"] == 1:
        return ProductResolution(sku=exact["rows"][0][0])
    if exact["row_count"] > 1:
        return ProductResolution(candidates=[{"sku": r[0], "name": r[1]} for r in exact["rows"]])

    prefix = execute(PREFIX_SQL, {"workspace_id": workspace_id, "prefix": name + "%"})
    if prefix["row_count"] == 1:
        return ProductResolution(sku=prefix["rows"][0][0])
    if prefix["row_count"] > 1:
        return ProductResolution(candidates=[{"sku": r[0], "name": r[1]} for r in prefix["rows"]])

    return ProductResolution(candidates=[])
