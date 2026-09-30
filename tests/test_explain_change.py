# Integration tests against the seeded demo data (run scripts/seed.py first).
# They check the pipeline surfaces the two planted stories correctly.
from datetime import date

from app.analysis.explain_change import explain_change
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
    result = explain_change(
        "refund amount", SEPTEMBER, AUGUST, dimension="city",
        filters=[Filter(field="sku", value="SKU-0001")],
    )
    top = result["top_contributors"][0]
    assert top["dimension_value"] == "Mumbai"
    assert top["change"] > 0


def test_explain_change_reports_definition_version():
    result = explain_change("net revenue", AUGUST, JULY)
    assert result["definition_version"] == 1
    assert result["metric"] == "net_revenue"
