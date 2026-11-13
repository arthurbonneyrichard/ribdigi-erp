"""Uptime counts real outages, not alerts such as an overdue backup."""

from __future__ import annotations

from app import server_monitor as svc


def _snap(*checks: tuple[str, str]) -> dict:
    return {"status": "critical", "checks": [{"key": k, "status": s} for k, s in checks]}


def test_overdue_backup_is_an_alert_not_downtime():
    row = svc.compact(_snap(("database", "ok"), ("backups", "critical"), ("tls", "critical")))
    assert row["up"] is True and row["bad"] == ["backups", "tls"] and row["s"] == "critical"


def test_database_redis_desk_or_site_down_is_downtime():
    for key in ("database", "redis", "workers", "web", "desk_db:hotel"):
        row = svc.compact(_snap(("backups", "ok"), (key, "critical")))
        assert row["up"] is False, key


def test_uptime_uses_availability_and_reads_old_rows():
    now = svc._now()
    rows = [
        {"t": now - 50, "s": "critical", "up": True},   # overdue backup only
        {"t": now - 40, "s": "critical", "up": False},  # database down
        {"t": now - 30, "s": "critical", "db": 12.0},   # old reading: database answered
        {"t": now - 20, "s": "critical", "db": None},   # old reading: no database reply
    ]
    assert svc.uptime_from(rows)["healthy_pct"] == 50.0
