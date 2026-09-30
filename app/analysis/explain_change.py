from app.compiler.compiler import compile_plan
from app.executor.executor import execute
from app.planner.schema import Filter, QueryPlan, TimeRange
from app.semantic.loader import get_metric as get_metric_def
from app.semantic.resolve import resolve
from app.validator.validator import validate_sql

ALLOWED_TABLES = ["customers", "products", "orders", "order_items", "returns"]

# If one side's counterfactual effect on the rate is not at least this many
# times the other side's, treat the change as jointly driven by both.
DOMINANCE_RATIO = 1.25

# Below this many units in the earlier period, a relative change is noise,
# not signal - a jump from 2 to 16 is technically "+700%" but says nothing
# reliable about the underlying rate.
LOW_BASE_THRESHOLD = 10

# Above this relative change, in a low-base case, state raw counts instead
# of a percentage - "+700%" off a base of 2 is misleading either way.
HIGH_RELATIVE_CHANGE_THRESHOLD = 300

# If numerator AND denominator both moved by more than this, neither one
# "drove" it in a useful sense - they both moved sharply together.
BOTH_MOVED_THRESHOLD = 100

# For an additive returns metric (refund_amount, units_returned), if units
# sold moved by more than this, some of the change is just volume.
VOLUME_CHANGE_THRESHOLD = 100
RETURNS_METRICS_NEEDING_VOLUME_CONTEXT = {"refund_amount", "units_returned"}


def _run(metric_def, time_range: TimeRange, dimensions, workspace_id: str, filters=None):
    plan = QueryPlan(
        workspace_id=workspace_id, metric=metric_def.name,
        dimensions=dimensions, filters=filters or [], time_range=time_range,
    )
    sql, params = compile_plan(metric_def, plan)
    safe_sql = validate_sql(sql, ALLOWED_TABLES)
    return execute(safe_sql, params)


def _scalar(exec_result) -> float:
    return (exec_result["rows"][0][0] if exec_result["rows"] else 0) or 0


def _pct_change(current, previous):
    if not previous:
        return None
    return (current - previous) / previous * 100


def _relative_pct_words(pct: float) -> str:
    # spoken-safe relative-change text: integer once it reads as a big jump.
    if abs(pct) >= 100:
        return f"{abs(pct):.0f} percent"
    return f"{abs(pct):.1f} percent"


def _direction_phrase(pct, spoken: bool = False) -> str:
    if pct is None:
        return "was flat"
    if pct > 0.5:
        return f"rose {_relative_pct_words(pct) if spoken else f'{abs(pct):.1f}%'}"
    if pct < -0.5:
        return f"fell {_relative_pct_words(pct) if spoken else f'{abs(pct):.1f}%'}"
    return "stayed flat"


def _raw_change_phrase(label, previous, current, unit):
    suffix = "units" if unit == "count" else "rupees" if unit == "currency" else unit
    return f"{label} went from {previous:.0f} to {current:.0f} {suffix}"


def _phrase_for_side(label, change_percent, previous, current, unit, is_low, spoken):
    needs_raw_count = is_low and (
        previous == 0
        or (change_percent is not None and abs(change_percent) > HIGH_RELATIVE_CHANGE_THRESHOLD)
    )
    if needs_raw_count:
        return _raw_change_phrase(label, previous, current, unit)
    return f"{label} {_direction_phrase(change_percent, spoken)}"


def _build_summary(
    driver, both_moved_sharply,
    numerator_label, denominator_label,
    numerator_change_percent, denominator_change_percent,
    previous_num, current_num, previous_den, current_den,
    numerator_unit, denominator_unit, numerator_low, denominator_low,
    spoken,
) -> str:
    if both_moved_sharply:
        # The rate's own before/after is already stated by the caller right
        # before this summary - say it once, not again here. Lead with that,
        # then give the raw counts behind it.
        return (
            f"both moved sharply: {numerator_label} went from {previous_num:.0f} to {current_num:.0f}, "
            f"{denominator_label} from {previous_den:.0f} to {current_den:.0f}."
        )

    numerator_phrase = _phrase_for_side(
        numerator_label, numerator_change_percent, previous_num, current_num, numerator_unit, numerator_low, spoken
    )
    denominator_phrase = _phrase_for_side(
        denominator_label, denominator_change_percent, previous_den, current_den,
        denominator_unit, denominator_low, spoken,
    )

    if driver == "numerator":
        return f"{numerator_phrase}, while {denominator_phrase}; the change in {numerator_label} drove it."
    if driver == "denominator":
        return f"{denominator_phrase}, while {numerator_phrase}; the change in {denominator_label} drove it."
    if driver == "both":
        return f"{numerator_phrase} and {denominator_phrase}; both contributed."
    return f"{numerator_phrase} and {denominator_phrase}."


def _decompose_ratio(metric_def, current_range, compare_range, filters, workspace_id, previous_rate):
    numerator_def = get_metric_def(metric_def.why_components["numerator"])
    denominator_def = get_metric_def(metric_def.why_components["denominator"])

    current_num = _scalar(_run(numerator_def, current_range, [], workspace_id, filters))
    previous_num = _scalar(_run(numerator_def, compare_range, [], workspace_id, filters))
    current_den = _scalar(_run(denominator_def, current_range, [], workspace_id, filters))
    previous_den = _scalar(_run(denominator_def, compare_range, [], workspace_id, filters))

    numerator_change_percent = _pct_change(current_num, previous_num)
    denominator_change_percent = _pct_change(current_den, previous_den)

    numerator_label = numerator_def.name.replace("_", " ")
    denominator_label = denominator_def.name.replace("_", " ")

    numerator_low = previous_num < LOW_BASE_THRESHOLD
    denominator_low = previous_den < LOW_BASE_THRESHOLD
    low_base = numerator_low or denominator_low

    both_moved_sharply = (
        numerator_change_percent is not None and abs(numerator_change_percent) > BOTH_MOVED_THRESHOLD
        and denominator_change_percent is not None and abs(denominator_change_percent) > BOTH_MOVED_THRESHOLD
    )

    if both_moved_sharply:
        driver = "both"
    else:
        # Counterfactual (index-decomposition) effect: how much of the
        # rate's movement is explained by each side changing on its own.
        effect_numerator = (current_num / previous_den - previous_rate) if previous_den else 0.0
        effect_denominator = (previous_num / current_den - previous_rate) if current_den else 0.0

        if abs(effect_numerator) < 1e-12 and abs(effect_denominator) < 1e-12:
            driver = "neither"
        elif abs(effect_numerator) >= abs(effect_denominator) * DOMINANCE_RATIO:
            driver = "numerator"
        elif abs(effect_denominator) >= abs(effect_numerator) * DOMINANCE_RATIO:
            driver = "denominator"
        else:
            driver = "both"

    summary_args = (
        driver, both_moved_sharply,
        numerator_label, denominator_label,
        numerator_change_percent, denominator_change_percent,
        previous_num, current_num, previous_den, current_den,
        numerator_def.unit, denominator_def.unit, numerator_low, denominator_low,
    )
    summary = _build_summary(*summary_args, spoken=False)
    summary_spoken = _build_summary(*summary_args, spoken=True)

    low_base_note = None
    if low_base:
        parts = []
        if numerator_low:
            parts.append(f"only {previous_num:.0f} {numerator_label}")
        if denominator_low:
            parts.append(f"only {previous_den:.0f} {denominator_label}")
        low_base_note = f"the earlier period had {' and '.join(parts)}, so the rate is noisy."

    return {
        "numerator_metric": numerator_def.name,
        "numerator_unit": numerator_def.unit,
        "denominator_metric": denominator_def.name,
        "denominator_unit": denominator_def.unit,
        "current_numerator": current_num,
        "previous_numerator": previous_num,
        "numerator_change_percent": numerator_change_percent,
        "current_denominator": current_den,
        "previous_denominator": previous_den,
        "denominator_change_percent": denominator_change_percent,
        "driver": driver,
        "summary": summary,
        "summary_spoken": summary_spoken,
        "low_base": low_base,
        "low_base_note": low_base_note,
    }


def _volume_context(current_range, compare_range, filters, workspace_id):
    units_sold_def = get_metric_def("units_sold")
    current_units = _scalar(_run(units_sold_def, current_range, [], workspace_id, filters))
    previous_units = _scalar(_run(units_sold_def, compare_range, [], workspace_id, filters))
    pct = _pct_change(current_units, previous_units)

    if pct is None or abs(pct) <= VOLUME_CHANGE_THRESHOLD:
        return None

    if pct > 0:
        note = (
            f"units sold also rose {_relative_pct_words(pct)}, so part of the increase "
            "is higher volume, not only a higher return rate."
        )
    else:
        note = (
            f"units sold also fell {_relative_pct_words(pct)}, so part of the decrease "
            "is lower volume, not only a lower return rate."
        )

    return {
        "current_units_sold": current_units,
        "previous_units_sold": previous_units,
        "units_sold_change_percent": pct,
        "note": note,
    }


def explain_change(
    metric_name: str,
    current_range: TimeRange,
    compare_range: TimeRange,
    dimension: str = None,
    filters=None,
    workspace_id: str = "demo",
) -> dict:
    try:
        metric_def = get_metric_def(metric_name)
    except KeyError:
        result = resolve(metric_name)
        if result.status != "found":
            raise ValueError(result.message or f"unknown metric: {metric_name}")
        metric_def = result.metric
    filters = filters or []

    current_total = _run(metric_def, current_range, [], workspace_id, filters)
    previous_total = _run(metric_def, compare_range, [], workspace_id, filters)

    current_value = _scalar(current_total)
    previous_value = _scalar(previous_total)

    absolute_change = current_value - previous_value
    percent_change = _pct_change(current_value, previous_value)

    response = {
        "metric": metric_def.name,
        "definition_version": metric_def.version,
        "current_value": current_value,
        "previous_value": previous_value,
        "absolute_change": absolute_change,
        "percent_change": percent_change,
        "dimension": dimension,
        "top_contributors": [],
        "ratio_decomposition": None,
        "volume_context": None,
    }

    if metric_def.why_components:
        # Ratio metrics decompose into their numerator/denominator instead
        # of a per-dimension contribution breakdown (a percentage-point
        # delta on a rate does not decompose cleanly across dimensions).
        response["ratio_decomposition"] = _decompose_ratio(
            metric_def, current_range, compare_range, filters, workspace_id, previous_value
        )
        return response

    if metric_def.name in RETURNS_METRICS_NEEDING_VOLUME_CONTEXT:
        response["volume_context"] = _volume_context(current_range, compare_range, filters, workspace_id)

    if dimension:
        if dimension not in metric_def.dimension_columns:
            raise ValueError(f"dimension not allowed for {metric_def.name}: {dimension}")

        current_by_dim = _run(metric_def, current_range, [dimension], workspace_id, filters)
        previous_by_dim = _run(metric_def, compare_range, [dimension], workspace_id, filters)

        current_map = {row[0]: (row[1] or 0) for row in current_by_dim["rows"]}
        previous_map = {row[0]: (row[1] or 0) for row in previous_by_dim["rows"]}

        contributors = []
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
        response["top_contributors"] = contributors[:3]

    return response
