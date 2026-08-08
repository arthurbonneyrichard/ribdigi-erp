from datetime import datetime, timedelta

from app.expenses import next_run_date, requires_approval, steps_required_for_amount


def test_requires_approval_above_threshold():
    assert requires_approval(100.01, 100) is True
    assert requires_approval(100, 100) is False
    assert requires_approval(50, 100) is False


def test_steps_required_helpers():
    assert steps_required_for_amount(100, auto_threshold=100, l2_threshold=1000) == 0
    assert steps_required_for_amount(101, auto_threshold=100, l2_threshold=1000) == 1


def test_next_run_weekly():
    start = datetime(2026, 8, 1, 12, 0, 0)
    assert next_run_date(start, "weekly") == start + timedelta(weeks=1)


def test_next_run_monthly_default():
    start = datetime(2026, 8, 1, 12, 0, 0)
    assert next_run_date(start, "monthly") == start + timedelta(days=30)
