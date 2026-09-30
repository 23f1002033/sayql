# Date-range policy used by the system prompt in static/app.js. There is no
# backend function that resolves "this month" / "last month" - the agent
# computes literal dates itself - so this test pins the calendar arithmetic
# behind that policy to the same ANCHOR_DATE the demo data is seeded from,
# to catch the two from drifting apart.
from datetime import date, timedelta

from scripts.seed import ANCHOR_DATE


def test_anchor_date_matches_system_prompt():
    assert ANCHOR_DATE == date(2026, 9, 30)


def test_this_month_is_full_september():
    start = date(ANCHOR_DATE.year, ANCHOR_DATE.month, 1)
    end = ANCHOR_DATE
    assert start == date(2026, 9, 1)
    assert end == date(2026, 9, 30)


def test_previous_full_month_is_august():
    this_month_start = date(ANCHOR_DATE.year, ANCHOR_DATE.month, 1)
    previous_end = this_month_start - timedelta(days=1)
    previous_start = date(previous_end.year, previous_end.month, 1)
    assert previous_start == date(2026, 8, 1)
    assert previous_end == date(2026, 8, 31)


def test_last_week_is_seven_full_days_before_anchor_excluding_today():
    end = ANCHOR_DATE - timedelta(days=1)
    start = ANCHOR_DATE - timedelta(days=7)
    assert start == date(2026, 9, 23)
    assert end == date(2026, 9, 29)
    assert (end - start).days == 6  # 7 full days inclusive: 23, 24, ..., 29
