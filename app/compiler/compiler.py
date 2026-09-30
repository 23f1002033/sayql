import re

import sqlglot

from app.planner.schema import QueryPlan
from app.semantic.loader import MetricDef

MAX_LIMIT = 200

# Grain bucket expressions, dialect-specific. The compiler picks the right
# fragment before parsing, so sqlglot only has to validate and pretty-print
# text that is already correct for the target dialect.
GRAIN_EXPR = {
    "sqlite": {
        "day": "strftime('%Y-%m-%d', {col})",
        "week": "strftime('%Y-W%W', {col})",
        "month": "strftime('%Y-%m', {col})",
    },
    "postgres": {
        "day": "to_char(date_trunc('day', {col}), 'YYYY-MM-DD')",
        "week": "to_char(date_trunc('week', {col}), 'IYYY-IW')",
        "month": "to_char(date_trunc('month', {col}), 'YYYY-MM')",
    },
}

_PLACEHOLDER_RE = re.compile(r"%\((\w+)\)s")


class CompileError(Exception):
    pass


def _normalize_placeholders(sql_text: str) -> str:
    # sqlglot renders bound params as %(name)s for the postgres dialect;
    # SQLAlchemy's text() always wants :name regardless of the driver.
    return _PLACEHOLDER_RE.sub(r":\1", sql_text)


def compile_plan(metric_def: MetricDef, plan: QueryPlan, dialect: str = "sqlite"):
    grain_exprs = GRAIN_EXPR.get(dialect)
    if grain_exprs is None:
        raise CompileError(f"unsupported dialect: {dialect}")
    if plan.grain and plan.grain not in grain_exprs:
        raise CompileError(f"unsupported grain: {plan.grain}")

    for dim in plan.dimensions:
        if dim not in metric_def.dimension_columns:
            raise CompileError(f"dimension not allowed for {metric_def.name}: {dim}")
    for f in plan.filters:
        if f.field not in metric_def.dimension_columns:
            raise CompileError(f"filter field not allowed for {metric_def.name}: {f.field}")

    select_cols = []
    group_cols = []

    if plan.grain:
        bucket = grain_exprs[plan.grain].format(col=metric_def.date_column)
        select_cols.append(f"{bucket} AS period")
        group_cols.append("period")

    for dim in plan.dimensions:
        col = metric_def.dimension_columns[dim]
        select_cols.append(f"{col} AS {dim}")
        group_cols.append(dim)

    select_cols.append(f"{metric_def.value_expr} AS value")

    sql = f"SELECT {', '.join(select_cols)} FROM {metric_def.base_table}"
    sql += f" WHERE {metric_def.workspace_column} = :workspace_id"
    sql += f" AND {metric_def.date_column} BETWEEN :start_date AND :end_date"

    params = {
        "workspace_id": plan.workspace_id,
        "start_date": plan.time_range.start.isoformat(),
        "end_date": plan.time_range.end.isoformat(),
    }

    for i, f in enumerate(plan.filters):
        col = metric_def.dimension_columns[f.field]
        key = f"filter_{i}"
        sql += f" AND {col} = :{key}"
        params[key] = f.value

    if group_cols:
        sql += " GROUP BY " + ", ".join(group_cols)
        sql += " ORDER BY " + group_cols[0]

    limit = min(plan.limit, MAX_LIMIT)
    sql += f" LIMIT {limit}"

    try:
        parsed = sqlglot.parse_one(sql, read=dialect)
    except Exception as err:
        raise CompileError(f"generated invalid sql: {err}") from err

    final_sql = _normalize_placeholders(parsed.sql(dialect=dialect))
    return final_sql, params
