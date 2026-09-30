from app.compiler.compiler import compile_plan
from app.executor.executor import execute
from app.planner.schema import Filter, QueryPlan, TimeRange
from app.semantic.resolve import resolve
from app.validator.validator import validate_sql

ALLOWED_TABLES = ["customers", "products", "orders", "order_items", "returns"]


def _run(metric_def, time_range: TimeRange, dimensions, workspace_id: str, filters=None):
    plan = QueryPlan(
        workspace_id=workspace_id, metric=metric_def.name,
        dimensions=dimensions, filters=filters or [], time_range=time_range,
    )
    sql, params = compile_plan(metric_def, plan)
    safe_sql = validate_sql(sql, ALLOWED_TABLES)
    return execute(safe_sql, params)


def explain_change(
    metric_name: str,
    current_range: TimeRange,
    compare_range: TimeRange,
    dimension: str = None,
    filters=None,
    workspace_id: str = "demo",
) -> dict:
    result = resolve(metric_name)
    if result.status != "found":
        raise ValueError(f"unknown metric: {metric_name}")
    metric_def = result.metric
    filters = filters or []

    current_total = _run(metric_def, current_range, [], workspace_id, filters)
    previous_total = _run(metric_def, compare_range, [], workspace_id, filters)

    current_value = (current_total["rows"][0][0] if current_total["rows"] else 0) or 0
    previous_value = (previous_total["rows"][0][0] if previous_total["rows"] else 0) or 0

    absolute_change = current_value - previous_value
    percent_change = (absolute_change / previous_value * 100) if previous_value else None

    contributors = []
    if dimension:
        if dimension not in metric_def.dimension_columns:
            raise ValueError(f"dimension not allowed for {metric_def.name}: {dimension}")

        current_by_dim = _run(metric_def, current_range, [dimension], workspace_id, filters)
        previous_by_dim = _run(metric_def, compare_range, [dimension], workspace_id, filters)

        current_map = {row[0]: (row[1] or 0) for row in current_by_dim["rows"]}
        previous_map = {row[0]: (row[1] or 0) for row in previous_by_dim["rows"]}

        for key in set(current_map) | set(previous_map):
            change = current_map.get(key, 0) - previous_map.get(key, 0)
            contributors.append({
                "dimension_value": key,
                "current_value": current_map.get(key, 0),
                "previous_value": previous_map.get(key, 0),
                "change": change,
            })

        total_dim_change = sum(c["change"] for c in contributors) or 1
        for c in contributors:
            c["share_of_total_change"] = c["change"] / total_dim_change

        contributors.sort(key=lambda c: abs(c["change"]), reverse=True)

    return {
        "metric": metric_def.name,
        "definition_version": metric_def.version,
        "current_value": current_value,
        "previous_value": previous_value,
        "absolute_change": absolute_change,
        "percent_change": percent_change,
        "dimension": dimension,
        "top_contributors": contributors[:3],
    }
