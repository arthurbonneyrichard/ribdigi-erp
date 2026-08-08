from datetime import datetime

from app.credit import age_bucket, days_overdue, empty_buckets, add_to_bucket


def test_age_buckets():
    assert age_bucket(0) == "current"
    assert age_bucket(15) == "1_30"
    assert age_bucket(45) == "31_60"
    assert age_bucket(75) == "61_90"
    assert age_bucket(120) == "90_plus"


def test_days_overdue():
    as_of = datetime(2026, 8, 8)
    due = datetime(2026, 7, 9)
    assert days_overdue(as_of, due) == 30


def test_add_to_bucket():
    buckets = empty_buckets()
    add_to_bucket(buckets, 10, 100)
    add_to_bucket(buckets, 40, 50)
    assert buckets["1_30"] == 100
    assert buckets["31_60"] == 50
