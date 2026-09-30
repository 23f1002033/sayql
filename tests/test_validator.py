import pytest

from app.validator.validator import ValidationError, validate_sql

ALLOWED = ["customers", "products", "orders", "order_items", "returns"]


def test_valid_select_passes():
    sql = validate_sql("SELECT city, COUNT(*) FROM orders GROUP BY city", ALLOWED)
    assert "LIMIT" in sql.upper()


def test_valid_with_cte_passes():
    sql = validate_sql(
        "WITH t AS (SELECT city, COUNT(*) AS c FROM orders GROUP BY city) SELECT * FROM t",
        ALLOWED,
    )
    assert "LIMIT" in sql.upper()


def test_rejects_drop():
    with pytest.raises(ValidationError):
        validate_sql("DROP TABLE customers", ALLOWED)


def test_rejects_multiple_statements():
    with pytest.raises(ValidationError):
        validate_sql("SELECT 1; DROP TABLE customers;", ALLOWED)


def test_rejects_pragma():
    with pytest.raises(ValidationError):
        validate_sql("PRAGMA table_info(orders)", ALLOWED)


def test_rejects_attach():
    with pytest.raises(ValidationError):
        validate_sql("ATTACH DATABASE 'x.db' AS x", ALLOWED)


def test_rejects_disallowed_table():
    with pytest.raises(ValidationError):
        validate_sql("SELECT * FROM query_history", ALLOWED)


def test_rejects_disallowed_table_inside_cte():
    with pytest.raises(ValidationError):
        validate_sql("WITH t AS (SELECT * FROM query_history) SELECT * FROM t", ALLOWED)


def test_rejects_insert():
    with pytest.raises(ValidationError):
        validate_sql("INSERT INTO orders (order_id) VALUES (1)", ALLOWED)


def test_rejects_empty_query():
    with pytest.raises(ValidationError):
        validate_sql("   ", ALLOWED)


def test_injects_limit_when_missing():
    sql = validate_sql("SELECT * FROM orders", ALLOWED, max_rows=50)
    assert "LIMIT 50" in sql.upper()


def test_clamps_limit_when_too_large():
    sql = validate_sql("SELECT * FROM orders LIMIT 100000", ALLOWED, max_rows=50)
    assert "LIMIT 50" in sql.upper()


def test_keeps_limit_when_within_bounds():
    sql = validate_sql("SELECT * FROM orders LIMIT 10", ALLOWED, max_rows=50)
    assert "LIMIT 10" in sql.upper()
