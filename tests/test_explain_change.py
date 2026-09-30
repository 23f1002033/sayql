# Integration tests against the seeded demo data (run scripts/seed.py first).
# They check the pipeline surfaces the two planted stories correctly.
from datetime import date

from app.analysis.explain_change import (
    HIGH_RELATIVE_CHANGE_THRESHOLD,
    LOW_BASE_THRESHOLD,
    explain_change,
)
from app.planner.schema import Filter, TimeRange

SEPTEMBER = TimeRange(start=date(2026, 9, 1), end=date(2026, 9, 29))
AUGUST = TimeRange(start=date(2026, 8, 1), end=date(2026, 8, 31))
JULY = TimeRange(start=date(2026, 7, 1), end=date(2026, 7, 31))


def test_sales_drop_surfaces_planted_sku():
    result = explain_change("units sold", AUGUST, JULY, dimension="sku")
    top = result["top_contributors"][0]
    assert top["dimension_value"] == "SKU-0001"
    assert top["change"] < 0


def test_return_spike_surfaces_mumbai_when_filtered_to_sku():
    # additive metric: keeps the per-dimension contribution breakdown
    result = explain_change(
        "refund amount", SEPTEMBER, AUGUST, dimension="city",
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    assert result["ratio_decomposition"] is None
    top = result["top_contributors"][0]
    assert top["dimension_value"] == "Mumbai"
    assert top["change"] > 0


def test_return_rate_spike_decomposes_for_planted_sku():
    # ratio metric: replaces the dimension breakdown with a
    # numerator/denominator decomposition instead. Both units_returned
    # (700%) and units_sold (533%) moved by more than 100%, so this is a
    # "both moved sharply" case, not a single clean driver.
    result = explain_change(
        "return rate", SEPTEMBER, AUGUST,
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    assert result["top_contributors"] == []
    decomposition = result["ratio_decomposition"]
    assert decomposition["numerator_metric"] == "units_returned"
    assert decomposition["denominator_metric"] == "units_sold"
    assert decomposition["driver"] == "both"
    assert decomposition["current_numerator"] > decomposition["previous_numerator"]
    assert "both moved sharply" in decomposition["summary"]
    assert "percentage points" in decomposition["summary"]


def test_explain_change_reports_definition_version():
    result = explain_change("net revenue", AUGUST, JULY)
    assert result["definition_version"] == 1
    assert result["metric"] == "net_revenue"


def test_planted_story_is_honestly_flagged_low_base():
    # August only had 2 returns for this sku before the spike - that IS a
    # low base, and low_base/low_base_note must still surface even though
    # this particular story also happens to be a "both moved sharply" case
    # (low_base and both_moved_sharply are independent flags).
    result = explain_change(
        "return rate", SEPTEMBER, AUGUST,
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    decomposition = result["ratio_decomposition"]
    assert decomposition["previous_numerator"] < LOW_BASE_THRESHOLD
    assert decomposition["low_base"] is True
    assert "noisy" in decomposition["low_base_note"]


def test_national_return_rate_has_enough_base_to_not_be_flagged_noisy():
    # unfiltered, the whole store's numerator/denominator are in the
    # thousands - a real comparison with real signal, not low_base.
    result = explain_change("return rate", SEPTEMBER, AUGUST)
    decomposition = result["ratio_decomposition"]
    assert decomposition["previous_numerator"] >= LOW_BASE_THRESHOLD
    assert decomposition["previous_denominator"] >= LOW_BASE_THRESHOLD
    assert decomposition["low_base"] is False
    assert decomposition["low_base_note"] is None


def test_low_base_flagged_and_uses_raw_counts_not_percent():
    # a single-day compare window naturally gives tiny counts
    single_day_current = TimeRange(start=date(2026, 9, 29), end=date(2026, 9, 29))
    single_day_previous = TimeRange(start=date(2026, 7, 1), end=date(2026, 7, 1))

    result = explain_change(
        "return rate", single_day_current, single_day_previous,
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    decomposition = result["ratio_decomposition"]
    assert decomposition["previous_numerator"] < LOW_BASE_THRESHOLD
    assert decomposition["low_base"] is True
    assert decomposition["low_base_note"] is not None
    assert "noisy" in decomposition["low_base_note"]

    # the numerator's relative change is either None (0 base) or far above the
    # threshold - either way it must be reported as a raw count, not a percent
    if decomposition["numerator_change_percent"] is not None:
        assert abs(decomposition["numerator_change_percent"]) > HIGH_RELATIVE_CHANGE_THRESHOLD
    assert "%" not in decomposition["summary"].split(",")[0]
    assert "went from" in decomposition["summary"]


def test_tools_explain_change_surfaces_low_base_in_card():
    import app.tools as tools

    response = tools.explain_change(
        "return rate", "2026-09-29", "2026-09-29", "2026-07-01", "2026-07-01",
        filters=[{"field": "product_name", "value": "Wireless Earbuds Pro"}],
    )
    assert response["card"]["low_base"] is True
    assert response["card"]["low_base_note"] is not None
    assert "noisy" in response["card"]["narration_seed"]


def test_tools_explain_change_low_base_false_when_not_flagged():
    import app.tools as tools

    # unfiltered, store-wide counts are in the thousands - not low_base
    response = tools.explain_change(
        "return rate", "2026-09-01", "2026-09-29", "2026-08-01", "2026-08-31",
    )
    assert response["card"]["low_base"] is False
    assert response["card"]["low_base_note"] is None


def test_volume_context_surfaces_for_refund_amount_planted_story():
    result = explain_change(
        "refund amount", SEPTEMBER, AUGUST, dimension="city",
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    context = result["volume_context"]
    assert context is not None
    assert context["units_sold_change_percent"] > 100
    assert "units sold also rose" in context["note"]
    assert "percent" in context["note"]
    assert "%" not in context["note"]
    # top-contributor sentence is kept alongside the volume-context note
    assert result["top_contributors"][0]["dimension_value"] == "Mumbai"


def test_volume_context_surfaces_for_units_returned_planted_story():
    result = explain_change(
        "units returned", SEPTEMBER, AUGUST, dimension="city",
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    assert result["volume_context"] is not None


def test_volume_context_absent_when_units_sold_did_not_move_much():
    # national, unfiltered: overall volume is stable month to month
    result = explain_change("refund amount", SEPTEMBER, AUGUST, dimension="city")
    assert result["volume_context"] is None


def test_volume_context_not_computed_for_non_returns_metrics():
    result = explain_change("net revenue", AUGUST, JULY, dimension="city")
    assert result["volume_context"] is None


def test_tools_explain_change_includes_volume_context_in_narration_and_evidence():
    import app.tools as tools

    response = tools.explain_change(
        "refund_amount", "2026-09-01", "2026-09-29", "2026-08-01", "2026-08-31",
        dimension="city", filters=[{"field": "sku", "value": "SKU-0001"}],
    )
    assert "units sold also rose" in response["card"]["narration_seed"]
    assert any("units sold also rose" in e for e in response["card"]["evidence"])
    # top-contributor sentence is kept
    assert "Mumbai" in response["card"]["narration_seed"]


def test_both_moved_sharply_leads_with_rate_change_and_percentage_points():
    result = explain_change(
        "return rate", SEPTEMBER, AUGUST,
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    decomposition = result["ratio_decomposition"]
    assert decomposition["driver"] == "both"
    assert decomposition["summary"].startswith("both moved sharply")
    assert "percentage points" in decomposition["summary"]
    assert "%" not in decomposition["summary"]


def test_not_both_moved_when_only_one_side_exceeds_threshold():
    # national return_rate: denominator (units_sold) barely moves month to
    # month, so even if the numerator moved a lot this should not trigger
    # the both-moved-sharply rule.
    result = explain_change("return rate", SEPTEMBER, AUGUST)
    decomposition = result["ratio_decomposition"]
    assert not (
        decomposition["numerator_change_percent"] is not None
        and abs(decomposition["numerator_change_percent"]) > 100
        and decomposition["denominator_change_percent"] is not None
        and abs(decomposition["denominator_change_percent"]) > 100
    )
    assert "both moved sharply" not in decomposition["summary"]
