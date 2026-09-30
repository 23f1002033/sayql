from datetime import date

import pytest

from app.compiler.compiler import CompileError, compile_plan
from app.planner.schema import Filter, QueryPlan, TimeRange
from app.semantic.resolve import resolve

RANGE = TimeRange(start=date(2026, 8, 1), end=date(2026, 8, 31))


def test_compile_simple_metric():
    metric = resolve("net revenue").metric
    plan = QueryPlan(metric="net_revenue", time_range=RANGE)
    sql, params = compile_plan(metric, plan)
    assert "SELECT" in sql.upper()
    assert "GROUP BY" not in sql.upper()
    assert params == {
        "workspace_id": "demo",
        "start_date": "2026-08-01",
        "end_date": "2026-08-31",
    }


def test_compile_with_dimension_adds_group_by():
    metric = resolve("net revenue").metric
    plan = QueryPlan(metric="net_revenue", dimensions=["city"], time_range=RANGE)
    sql, _ = compile_plan(metric, plan)
    assert "GROUP BY" in sql.upper()
    assert "AS city" in sql or "AS CITY" in sql.upper()


def test_compile_with_grain_adds_period_bucket():
    metric = resolve("net revenue").metric
    plan = QueryPlan(metric="net_revenue", grain="month", time_range=RANGE)
    sql, _ = compile_plan(metric, plan)
    assert "AS period" in sql or "AS PERIOD" in sql.upper()
    assert "STRFTIME" in sql.upper()


def test_compile_with_filter_adds_bound_param():
    metric = resolve("net revenue").metric
    plan = QueryPlan(metric="net_revenue", filters=[Filter(field="city", value="Mumbai")], time_range=RANGE)
    sql, params = compile_plan(metric, plan)
    assert params["filter_0"] == "Mumbai"
    assert ":filter_0" in sql


def test_compile_rejects_disallowed_dimension():
    metric = resolve("net revenue").metric
    plan = QueryPlan(metric="net_revenue", dimensions=["not_a_dimension"], time_range=RANGE)
    with pytest.raises(CompileError):
        compile_plan(metric, plan)


def test_compile_rejects_disallowed_filter_field():
    metric = resolve("net revenue").metric
    plan = QueryPlan(metric="net_revenue", filters=[Filter(field="not_a_dimension", value="x")], time_range=RANGE)
    with pytest.raises(CompileError):
        compile_plan(metric, plan)


def test_compile_clamps_limit():
    metric = resolve("net revenue").metric
    plan = QueryPlan(metric="net_revenue", time_range=RANGE, limit=100000)
    sql, _ = compile_plan(metric, plan)
    assert "LIMIT 200" in sql.upper()
