from app.format import format_value


def test_percent_absolute_value():
    assert format_value(0.0546, "percent") == "5.46%"


def test_percent_delta_uses_percentage_points_not_percent():
    text = format_value(0.168 - 0.133, "percent", is_delta=True)
    assert text == "3.5 percentage points"
    assert "percent" not in text.replace("percentage points", "")


def test_percent_delta_negative():
    assert format_value(-0.035, "percent", is_delta=True) == "-3.5 percentage points"


def test_currency_small_value():
    assert format_value(299.0, "currency") == "Rs 299"


def test_currency_thousands():
    assert format_value(4998.0, "currency") == "Rs 5.0 thousand"


def test_currency_lakh():
    assert format_value(5080580.0, "currency") == "Rs 50.81 lakh"


def test_currency_crore():
    assert format_value(15000000.0, "currency") == "Rs 1.50 crore"


def test_currency_negative():
    assert format_value(-500000.0, "currency") == "-Rs 5.00 lakh"


def test_count_integer():
    assert format_value(170, "count") == "170 units"


def test_count_negative():
    assert format_value(-78, "count") == "-78 units"


def test_none_value():
    assert format_value(None, "currency") == "n/a"


def test_unknown_unit_falls_back_to_str():
    assert format_value(42, "mystery") == "42"


def test_tools_explain_change_ratio_narration_uses_percentage_points():
    import app.tools as tools

    response = tools.explain_change(
        "return rate", "2026-09-01", "2026-09-30", "2026-08-01", "2026-08-31",
        filters=[{"field": "product_name", "value": "Wireless Earbuds Pro"}],
    )
    narration = response["card"]["narration_seed"]
    assert "percentage points" in narration
    assert "went from" in narration
    # the rate itself is displayed as a percent (X.XX%), not a raw fraction
    assert "0.1" not in narration.split("went from")[1].split("(")[0]


def test_tools_query_metric_currency_headline_uses_format_value():
    import app.tools as tools

    response = tools.query_metric({
        "metric": "net_revenue",
        "time_range": {"start": "2026-08-01", "end": "2026-08-31"},
    })
    assert response["card"]["headline_value"].startswith("Rs ")


def test_tools_query_metric_count_headline_uses_format_value():
    import app.tools as tools

    response = tools.query_metric({
        "metric": "units_returned",
        "time_range": {"start": "2026-09-01", "end": "2026-09-30"},
    })
    assert response["card"]["headline_value"].endswith(" units")


def test_currency_spoken_form():
    assert format_value(5080580.0, "currency", spoken=True) == "50.8 lakh rupees"


def test_currency_display_form_unchanged():
    assert format_value(5080580.0, "currency", spoken=False) == "Rs 50.81 lakh"


def test_currency_spoken_small_value():
    assert format_value(299.0, "currency", spoken=True) == "299 rupees"


def test_percent_delta_spoken_same_as_display():
    # "percentage points" is already the spoken-safe form, unaffected by spoken=
    assert format_value(0.035, "percent", is_delta=True, spoken=True) == "3.5 percentage points"
    assert format_value(0.035, "percent", is_delta=True, spoken=False) == "3.5 percentage points"


def test_percent_absolute_spoken_says_percent_word():
    assert format_value(0.0546, "percent", spoken=True) == "5.46 percent"


def test_percent_absolute_display_uses_symbol():
    assert format_value(0.0546, "percent", spoken=False) == "5.46%"


def test_count_spoken_same_as_display():
    assert format_value(170, "count", spoken=True) == "170 units"
    assert format_value(170, "count", spoken=False) == "170 units"


def test_currency_spoken_drops_trailing_zero():
    assert format_value(4998.0, "currency", spoken=True) == "5 thousand rupees"
    assert format_value(39984.0, "currency", spoken=True) == "40 thousand rupees"
    assert format_value(34986.0, "currency", is_delta=True, spoken=True) == "35 thousand rupees"


def test_currency_spoken_keeps_nonzero_decimal():
    assert format_value(5080580.0, "currency", spoken=True) == "50.8 lakh rupees"


def test_currency_display_form_unaffected_by_trailing_zero_rule():
    assert format_value(4998.0, "currency", spoken=False) == "Rs 5.0 thousand"


def test_relative_change_words_integer_at_or_above_100():
    from app.analysis.explain_change import _relative_pct_words
    assert _relative_pct_words(533.3333) == "533 percent"
    assert _relative_pct_words(100.0) == "100 percent"
    assert _relative_pct_words(-700.0) == "700 percent"


def test_relative_change_words_one_decimal_below_100():
    from app.analysis.explain_change import _relative_pct_words
    assert _relative_pct_words(26.315) == "26.3 percent"
    assert _relative_pct_words(-99.9) == "99.9 percent"


def test_regression_spoken_currency_values_from_the_reported_bug():
    assert format_value(5381999, "currency", spoken=True) == "53.8 lakh rupees"
    assert format_value(5080580, "currency", spoken=True) == "50.8 lakh rupees"
    assert format_value(150000, "currency", spoken=True) == "1.5 lakh rupees"
    assert format_value(12500000, "currency", spoken=True) == "1.25 crore rupees"


def _find_bare_numbers(obj):
    """Walk a JSON-able structure and collect every int/float found, except
    inside string values (which may legitimately contain digits as words
    like "went from 2 to 16", already spoken-safe small counts)."""
    found = []
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        found.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            found.extend(_find_bare_numbers(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_find_bare_numbers(v))
    return found


def test_model_payload_has_no_raw_currency_number_for_kpi():
    import app.tools as tools

    response = tools.query_metric({
        "metric": "gross_revenue",
        "time_range": {"start": "2026-08-01", "end": "2026-08-31"},
    })
    payload = response["model_payload"]
    assert "headline_spoken" in payload
    assert isinstance(payload["headline_spoken"], str)
    # no raw numeric value anywhere in the model-facing payload
    assert _find_bare_numbers(payload) == []


def test_model_payload_has_no_raw_numbers_for_breakdown():
    import app.tools as tools

    response = tools.query_metric({
        "metric": "refund_amount",
        "dimensions": ["city"],
        "time_range": {"start": "2026-09-01", "end": "2026-09-30"},
    })
    payload = response["model_payload"]
    assert all("value_spoken" in row for row in payload["rows_spoken"])
    for row in payload["rows_spoken"]:
        assert isinstance(row["value_spoken"], str)
    # row_count/showing are plain small integers (count of rows, not a
    # currency value), which is fine - only currency/percent values need
    # the spoken-string treatment.
    assert isinstance(payload["row_count"], int)


def test_model_payload_has_no_raw_numbers_for_why_ratio():
    import app.tools as tools

    response = tools.explain_change(
        "return rate", "2026-09-01", "2026-09-30", "2026-08-01", "2026-08-31",
        filters=[{"field": "sku", "value": "SKU-0001"}],
    )
    payload = response["model_payload"]
    assert isinstance(payload["previous_spoken"], str)
    assert isinstance(payload["current_spoken"], str)
    assert isinstance(payload["delta_spoken"], str)
    assert "ratio_summary_spoken" in payload
