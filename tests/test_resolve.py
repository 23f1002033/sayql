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
