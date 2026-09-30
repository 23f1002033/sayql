import json
import re

from app.analysis.explain_change import explain_change as explain_change_fn
from app.audit.db import record_query
from app.audit.logging import get_logger
from app.compiler.compiler import CompileError, compile_plan
from app.executor.executor import ExecutionError, execute
from app.format import format_value
from app.planner.schema import Filter, QueryPlan, TimeRange
from app.semantic.loader import get_metric as get_metric_def
from app.semantic.products import resolve_product_name
from app.semantic.resolve import resolve
from app.validator.validator import ValidationError, validate_sql

ALLOWED_TABLES = ["customers", "products", "orders", "order_items", "returns"]
WORKSPACE_ID = "demo"

logger = get_logger("app.tools")


def _log(session_id, question, args, sql, metric_def, exec_result, status):
    try:
        record_query(
            workspace_id=WORKSPACE_ID,
            session_id=session_id or "unknown",
            question=question or "",
            plan_json=json.dumps(args, default=str),
            sql=sql,
            definition_version=metric_def.version if metric_def else None,
            row_count=exec_result["row_count"] if exec_result else None,
            elapsed_ms=exec_result["elapsed_ms"] if exec_result else None,
            status=status,
        )
    except Exception:
        logger.exception("failed to record query_history")


def _make_card(
    kind, headline_value=None, period_label=None, delta=None, narration_seed=None,
    chart_series=None, definition=None, evidence=None, sql=None, row_count=None,
    elapsed_ms=None, options=None, message=None, followups=None,
    low_base=False, low_base_note=None,
):
    return {
        "kind": kind,
        "headline_value": headline_value,
        "period_label": period_label,
        "delta": delta,
        "narration_seed": narration_seed,
        "chart_series": chart_series,
        "definition": definition,
        "evidence": evidence,
        "sql": sql,
        "row_count": row_count,
        "elapsed_ms": elapsed_ms,
        "options": options,
        "message": message,
        "followups": followups,
        "low_base": low_base,
        "low_base_note": low_base_note,
    }


def _error_card(message):
    return {"result": {"error": message}, "card": _make_card(kind="error", message=message)}


def _clarification_card(resolve_result):
    return {
        "result": {"status": "ambiguous", "options": resolve_result.options, "message": resolve_result.message},
        "card": _make_card(
            kind="clarification", options=resolve_result.options,
            message=resolve_result.message, narration_seed=resolve_result.message,
        ),
    }


def _lookup_metric(name: str):
    """Accepts either the canonical metric key or a spoken term.

    Returns (metric_def, None) on success, or (None, response_dict) with a
    ready-to-return {result, card} payload for the ambiguous/not_found case.
    """
    try:
        return get_metric_def(name), None
    except KeyError:
        pass

    result = resolve(name)
    if result.status == "found":
        return result.metric, None
    if result.status == "ambiguous":
        return None, _clarification_card(result)
    return None, _error_card(result.message)


def _resolve_product_filters(filters, workspace_id):
    """Replaces any product_name filter with a code-resolved sku filter.

    The model is never allowed to pass a sku it guessed itself - it names a
    product, and this looks it up deterministically against the products
    table. Returns (resolved_filters, None) on success, or (None, response)
    with a ready {result, card} clarification payload on zero or multiple
    matches.
    """
    resolved = []
    for f in filters:
        if f.field != "product_name":
            resolved.append(f)
            continue

        resolution = resolve_product_name(f.value, workspace_id=workspace_id)
        if resolution.sku:
            resolved.append(Filter(field="sku", value=resolution.sku))
            continue

        names = [c["name"] for c in resolution.candidates]
        if names:
            message = f"'{f.value}' matches more than one product: {', '.join(names)}. Which one do you mean?"
        else:
            message = f"No product matches '{f.value}'."
        card = _make_card(kind="clarification", options=names, message=message, narration_seed=message)
        return None, {"result": {"status": "ambiguous" if names else "not_found",
                                  "options": names, "message": message}, "card": card}

    return resolved, None


def _definition_payload(metric_def):
    return {
        "name": metric_def.name,
        "version": metric_def.version,
        "description": metric_def.description,
        "formula": metric_def.formula,
        "unit": metric_def.unit,
    }




def _period_label(time_range: TimeRange) -> str:
    return f"{time_range.start.isoformat()} to {time_range.end.isoformat()}"


DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def _infer_kind(columns, rows):
    if len(columns) <= 1 or not rows:
        return "kpi"
    first_col = [row[0] for row in rows]
    if all(isinstance(v, str) and DATE_RE.match(v) for v in first_col):
        return "trend"
    return "breakdown"


def resolve_metric(term: str, session_id: str = None, question: str = None) -> dict:
    result = resolve(term)

    if result.status == "found":
        m = result.metric
        payload = {"status": "found", "metric": m.name, "description": m.description, "version": m.version}
        card = _make_card(
            kind="kpi",
            definition=_definition_payload(m),
            narration_seed=f"'{term}' maps to {m.name}: {m.description}",
        )
    elif result.status == "ambiguous":
        payload = {"status": "ambiguous", "options": result.options, "message": result.message}
        card = _make_card(kind="clarification", options=result.options, message=result.message,
                           narration_seed=result.message)
    else:
        payload = {"status": "not_found", "message": result.message, "available_terms": result.options}
        card = _make_card(kind="error", message=result.message, options=result.options)

    _log(session_id, question, {"tool": "resolve_metric", "term": term}, None, None, None, result.status)
    return {"result": payload, "card": card}


def query_metric(plan_args: dict, session_id: str = None, question: str = None) -> dict:
    try:
        plan = QueryPlan(**plan_args)
    except Exception as err:
        _log(session_id, question, {"tool": "query_metric", "args": plan_args}, None, None, None, "error")
        return _error_card(f"invalid query plan: {err}")

    metric_def, fallback = _lookup_metric(plan.metric)
    if metric_def is None:
        _log(session_id, question, {"tool": "query_metric", "args": plan_args}, None, None, None, "error")
        return fallback

    resolved_filters, clarification = _resolve_product_filters(plan.filters, WORKSPACE_ID)
    if clarification is not None:
        _log(session_id, question, {"tool": "query_metric", "args": plan_args}, None, metric_def, None, "clarification")
        return clarification
    plan.filters = resolved_filters

    try:
        sql, params = compile_plan(metric_def, plan)
        safe_sql = validate_sql(sql, ALLOWED_TABLES)
        exec_result = execute(safe_sql, params)
    except (CompileError, ValidationError, ExecutionError) as err:
        _log(session_id, question, {"tool": "query_metric", "args": plan_args}, None, metric_def, None, "error")
        return _error_card(str(err))

    kind = "trend" if plan.grain else ("breakdown" if plan.dimensions else "kpi")

    if kind == "kpi":
        raw_value = exec_result["rows"][0][0] if exec_result["rows"] else None
        headline_value = format_value(raw_value, metric_def.unit)
        spoken_value = format_value(raw_value, metric_def.unit, spoken=True)
        chart_series = None
    else:
        headline_value = None
        chart_series = [{"label": row[0], "value": row[-1]} for row in exec_result["rows"]]

    evidence = [
        f"resolved metric: {metric_def.name} (v{metric_def.version})",
        f"period: {_period_label(plan.time_range)}",
        f"{exec_result['row_count']} row(s) in {exec_result['elapsed_ms']} ms",
    ]

    if kind == "kpi":
        narration_seed = (
            f"{metric_def.name.replace('_', ' ')} for {_period_label(plan.time_range)} "
            f"was {spoken_value}, using the {metric_def.name} definition."
        )
    else:
        narration_seed = (
            f"{metric_def.name.replace('_', ' ')} for {_period_label(plan.time_range)}, "
            f"broken down into {exec_result['row_count']} groups, using the {metric_def.name} definition."
        )

    card = _make_card(
        kind=kind,
        headline_value=headline_value,
        period_label=_period_label(plan.time_range),
        chart_series=chart_series,
        definition=_definition_payload(metric_def),
        evidence=evidence,
        sql=safe_sql,
        row_count=exec_result["row_count"],
        elapsed_ms=exec_result["elapsed_ms"],
        narration_seed=narration_seed,
    )

    _log(session_id, question, {"tool": "query_metric", "args": plan_args}, safe_sql, metric_def, exec_result, "ok")
    return {"result": exec_result, "card": card}


def explain_change(
    metric: str, current_start: str, current_end: str, compare_start: str, compare_end: str,
    dimension: str = None, filters: list = None, session_id: str = None, question: str = None,
) -> dict:
    metric_def, fallback = _lookup_metric(metric)
    if metric_def is None:
        _log(session_id, question, {"tool": "explain_change", "metric": metric}, None, None, None, "error")
        return fallback

    filter_objs = [Filter(**f) for f in (filters or [])]
    resolved_filters, clarification = _resolve_product_filters(filter_objs, WORKSPACE_ID)
    if clarification is not None:
        _log(session_id, question, {"tool": "explain_change", "metric": metric}, None, metric_def, None, "clarification")
        return clarification

    try:
        current_range = TimeRange(start=current_start, end=current_end)
        compare_range = TimeRange(start=compare_start, end=compare_end)
        result = explain_change_fn(
            metric_def.name, current_range, compare_range, dimension=dimension,
            filters=resolved_filters, workspace_id=WORKSPACE_ID,
        )
    except Exception as err:
        _log(session_id, question, {"tool": "explain_change", "metric": metric}, None, metric_def, None, "error")
        return _error_card(str(err))

    unit = metric_def.unit
    prev_display = format_value(result["previous_value"], unit)
    curr_display = format_value(result["current_value"], unit)
    prev_spoken = format_value(result["previous_value"], unit, spoken=True)
    curr_spoken = format_value(result["current_value"], unit, spoken=True)
    delta_direction = "up" if result["absolute_change"] > 0 else "down" if result["absolute_change"] < 0 else "flat"
    delta_text = f"{delta_direction} {format_value(abs(result['absolute_change']), unit, is_delta=True)}"
    delta_spoken = f"{delta_direction} {format_value(abs(result['absolute_change']), unit, is_delta=True, spoken=True)}"

    evidence = [
        f"overall change: {prev_display} to {curr_display} ({_fmt_pct(result['percent_change'])} relative)",
    ]

    ratio = result.get("ratio_decomposition")
    low_base = bool(ratio and ratio.get("low_base"))
    low_base_note = ratio.get("low_base_note") if ratio else None

    if ratio:
        evidence.append(f"decomposed into {ratio['numerator_metric']} and {ratio['denominator_metric']}")
        evidence.append(ratio["summary"])
        if low_base_note:
            evidence.append(low_base_note)
        chart_series = [
            {"label": ratio["numerator_metric"], "value": ratio["numerator_change_percent"]},
            {"label": ratio["denominator_metric"], "value": ratio["denominator_change_percent"]},
        ]
        narration_seed = (
            f"{metric_def.name.replace('_', ' ')} went from {prev_spoken} to {curr_spoken} "
            f"({delta_spoken}). {ratio['summary_spoken']}"
        )
        if low_base_note:
            narration_seed += f" {low_base_note}"
        narration_seed += " This shows correlation, not proven cause."
    else:
        evidence.append(f"checked dimension: {dimension}" if dimension else "no dimension breakdown requested")
        for c in result["top_contributors"]:
            evidence.append(
                f"{c['dimension_value']}: change {format_value(c['change'], unit, is_delta=True)} "
                f"({_fmt_pct(c['share_of_total_change'] * 100)} of total change)"
            )
        chart_series = [
            {"label": c["dimension_value"], "value": c["change"]} for c in result["top_contributors"]
        ]
        volume_context = result.get("volume_context")
        if volume_context:
            evidence.append(volume_context["note"])
        top = result["top_contributors"][0] if result["top_contributors"] else None
        if top:
            narration_seed = (
                f"{metric_def.name.replace('_', ' ')} went from {prev_spoken} to {curr_spoken} "
                f"({delta_spoken}). {top['dimension_value']} was the top contributor at "
                f"{_fmt_pct(top['share_of_total_change'] * 100, spoken=True)} of the change."
            )
        else:
            narration_seed = (
                f"{metric_def.name.replace('_', ' ')} went from {prev_spoken} to {curr_spoken} "
                f"({delta_spoken}), with no dimension breakdown requested."
            )
        if volume_context:
            narration_seed += f" {volume_context['note']}"
        narration_seed += " This shows correlation, not proven cause."

    card = _make_card(
        kind="why",
        headline_value=curr_display,
        delta={"absolute": result["absolute_change"], "percent": result["percent_change"], "text": delta_text},
        low_base=low_base,
        low_base_note=low_base_note,
        chart_series=chart_series,
        definition=_definition_payload(metric_def),
        evidence=evidence,
        narration_seed=narration_seed,
    )

    _log(session_id, question, {"tool": "explain_change", "metric": metric, "dimension": dimension},
         None, metric_def, None, "ok")
    return {"result": result, "card": card}


def _fmt_pct(value, spoken=False):
    if value is None:
        return "n/a"
    if spoken:
        return f"{abs(value):.0f} percent" if abs(value) >= 100 else f"{abs(value):.1f} percent"
    return f"{value:.1f}%"


def run_sql(sql: str, session_id: str = None, question: str = None) -> dict:
    try:
        safe_sql = validate_sql(sql, ALLOWED_TABLES)
        exec_result = execute(safe_sql, {})
    except (ValidationError, ExecutionError) as err:
        _log(session_id, question, {"tool": "run_sql", "sql": sql}, sql, None, None, "error")
        return _error_card(str(err))

    kind = _infer_kind(exec_result["columns"], exec_result["rows"])
    headline_value = exec_result["rows"][0][0] if kind == "kpi" and exec_result["rows"] else None
    chart_series = None
    if kind != "kpi":
        chart_series = [{"label": row[0], "value": row[-1]} for row in exec_result["rows"]]

    card = _make_card(
        kind=kind,
        headline_value=headline_value,
        chart_series=chart_series,
        evidence=[f"raw SQL fallback, {exec_result['row_count']} row(s) in {exec_result['elapsed_ms']} ms"],
        sql=safe_sql,
        row_count=exec_result["row_count"],
        elapsed_ms=exec_result["elapsed_ms"],
        narration_seed=None,
    )

    _log(session_id, question, {"tool": "run_sql", "sql": sql}, safe_sql, None, exec_result, "ok")
    return {"result": exec_result, "card": card}


def suggest_followups(questions: list, session_id: str = None, question: str = None) -> dict:
    followups = list(questions or [])[:4]
    card = _make_card(kind="followups", followups=followups)
    _log(session_id, question, {"tool": "suggest_followups", "questions": followups}, None, None, None, "ok")
    return {"result": {"followups": followups}, "card": card}
