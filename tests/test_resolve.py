from app.semantic.resolve import resolve


def test_found_by_alias():
    result = resolve("net revenue")
    assert result.status == "found"
    assert result.metric.name == "net_revenue"


def test_found_by_underscored_name_as_words():
    result = resolve("return rate")
    assert result.status == "found"
    assert result.metric.name == "return_rate"


def test_ambiguous():
    result = resolve("revenue")
    assert result.status == "ambiguous"
    assert set(result.options) == {"gross_revenue", "net_revenue"}


def test_not_found():
    result = resolve("churn rate")
    assert result.status == "not_found"
    assert "net_revenue" in result.options


def test_case_and_whitespace_insensitive():
    result = resolve("  Net Revenue  ")
    assert result.status == "found"
    assert result.metric.name == "net_revenue"


def test_plain_returns_resolves_to_refund_amount_currency():
    result = resolve("returns")
    assert result.status == "found"
    assert result.metric.name == "refund_amount"
    assert result.metric.unit == "currency"


def test_how_many_returns_resolves_to_units_returned_count():
    result = resolve("how many returns")
    assert result.status == "found"
    assert result.metric.name == "units_returned"
    assert result.metric.unit == "count"


def test_number_of_returns_resolves_to_units_returned_count():
    result = resolve("number of returns")
    assert result.status == "found"
    assert result.metric.name == "units_returned"
    assert result.metric.unit == "count"


def test_return_count_resolves_to_units_returned_count():
    result = resolve("return count")
    assert result.status == "found"
    assert result.metric.name == "units_returned"
    assert result.metric.unit == "count"


def test_refunds_resolves_to_refund_amount_currency():
    result = resolve("refunds")
    assert result.status == "found"
    assert result.metric.name == "refund_amount"
    assert result.metric.unit == "currency"


def test_return_rate_resolves_to_return_rate_percent():
    result = resolve("return rate")
    assert result.metric.unit == "percent"


def test_sales_is_not_ambiguous():
    result = resolve("sales")
    assert result.status == "found"
    assert result.metric.name == "gross_revenue"


def test_customers_resolves_to_active_customers():
    result = resolve("customers")
    assert result.status == "found"
    assert result.metric.name == "active_customers"


def test_kpi_narration_names_currency_unit():
    import app.tools as tools

    response = tools.query_metric({
        "metric": "net_revenue",
        "time_range": {"start": "2026-08-01", "end": "2026-08-31"},
    })
    # narration is spoken form ("50.8 lakh rupees"); card headline stays display form ("Rs 50.81 lakh")
    assert "rupees" in response["card"]["narration_seed"]
    assert "Rs" in response["card"]["headline_value"]


def test_kpi_narration_names_count_unit():
    import app.tools as tools

    response = tools.query_metric({
        "metric": "units_returned",
        "time_range": {"start": "2026-09-01", "end": "2026-09-30"},
    })
    assert "units" in response["card"]["narration_seed"]


def test_ambiguous_term_has_a_default():
    result = resolve("revenue")
    assert result.status == "ambiguous"


def test_accept_default_returns_the_default_metric():
    result = resolve("revenue", accept_default=True)
    assert result.status == "found"
    assert result.metric.name == "net_revenue"
    assert result.used_default is True
    assert "net_revenue" in result.message
    assert "default" in result.message


def test_accept_default_false_still_asks():
    result = resolve("revenue", accept_default=False)
    assert result.status == "ambiguous"


def test_tools_resolve_metric_accept_default_narration_names_default():
    import app.tools as tools

    response = tools.resolve_metric("revenue", accept_default=True)
    assert response["result"]["status"] == "found"
    assert response["result"]["used_default"] is True
    assert "default" in response["card"]["narration_seed"]
    assert "net_revenue" in response["card"]["narration_seed"]
