# Integration tests against the seeded demo data (run scripts/seed.py first).
from app.semantic.products import resolve_product_name


def test_exact_name_resolves():
    result = resolve_product_name("Wireless Earbuds Pro")
    assert result.sku == "SKU-0001"
    assert result.candidates == []


def test_case_insensitive_exact_match():
    result = resolve_product_name("wireless earbuds pro")
    assert result.sku == "SKU-0001"


def test_unique_prefix_resolves():
    result = resolve_product_name("Wireless Earbuds")
    assert result.sku == "SKU-0001"


def test_ambiguous_prefix_lists_candidates():
    result = resolve_product_name("Wireless")
    assert result.sku is None
    names = {c["name"] for c in result.candidates}
    assert names == {"Wireless Earbuds Pro", "Wireless Mouse", "Wireless Charger Pad"}


def test_misspelling_has_no_match():
    result = resolve_product_name("Wireles Earbud Pro")
    assert result.sku is None
    assert result.candidates == []


def test_unknown_product_has_no_match():
    result = resolve_product_name("Quantum Toaster 9000")
    assert result.sku is None
    assert result.candidates == []


def test_tools_query_metric_resolves_product_name_filter():
    import app.tools as tools

    by_name = tools.query_metric({
        "metric": "net_revenue",
        "filters": [{"field": "product_name", "value": "Wireless Earbuds Pro"}],
        "time_range": {"start": "2026-09-01", "end": "2026-09-30"},
    })
    by_sku = tools.query_metric({
        "metric": "net_revenue",
        "filters": [{"field": "sku", "value": "SKU-0001"}],
        "time_range": {"start": "2026-09-01", "end": "2026-09-30"},
    })

    assert by_name["card"]["kind"] == "kpi"
    # sku is bound as a query parameter, not string-interpolated into the sql
    assert ":filter_0" in by_name["card"]["sql"]
    # resolving "Wireless Earbuds Pro" gives the exact same filtered result as sku=SKU-0001
    assert by_name["result"]["rows"] == by_sku["result"]["rows"]


def test_tools_query_metric_clarifies_on_misspelling():
    import app.tools as tools

    response = tools.query_metric({
        "metric": "net_revenue",
        "filters": [{"field": "product_name", "value": "Wireles Earbud Pro"}],
        "time_range": {"start": "2026-09-01", "end": "2026-09-30"},
    })
    assert response["card"]["kind"] == "clarification"


def test_tools_explain_change_clarifies_on_ambiguous_product_name():
    import app.tools as tools

    response = tools.explain_change(
        "return rate", "2026-09-01", "2026-09-30", "2026-08-01", "2026-08-31",
        filters=[{"field": "product_name", "value": "Wireless"}],
    )
    assert response["card"]["kind"] == "clarification"
    assert len(response["card"]["options"]) == 3
