"""Uptime counts real outages, not alerts such as an overdue backup."""

from __future__ import annotations

import pytest

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


def test_backup_check_clears_once_the_latest_backup_succeeds():
    base = {"companies_scheduled": 2, "age_hours": 0.5, "failed_last_24h": 6}
    recovered = {c["key"]: c for c in svc.build_checks({"backups": {**base, "companies_failing": 0}})}["backups"]
    assert recovered["status"] == "ok", recovered
    failing = {c["key"]: c for c in svc.build_checks({"backups": {**base, "companies_failing": 1}})}["backups"]
    assert failing["status"] == "warn" and "1 company" in failing["detail"], failing
    text = svc.backups_fix_text({**base, "companies_failing": 0, "last_error": "Invalid key"})
    assert "since succeeded" in text and "Earlier error (since fixed): Invalid key" in text


@pytest.mark.asyncio
async def test_backup_stats_counts_companies_whose_latest_backup_failed(db_session, client):
    from datetime import datetime, timedelta

    from app import models as m

    _ac, seed = client
    t1, t2 = seed["t1"].id, seed["t2"].id
    now = datetime.utcnow()
    for tenant, status, ago in ((t1, "failed", 3), (t1, "completed", 1), (t2, "completed", 3), (t2, "failed", 1)):
        db_session.add(m.BackupJob(
            tenant_id=tenant, status=status, filename="f", storage_path="", size_bytes=0,
            checksum_sha256="", encrypted=True, record_counts={}, created_at=now - timedelta(hours=ago),
        ))
    await db_session.commit()
    stats = await svc._backup_stats(db_session)
    assert stats["companies_failing"] == 1 and stats["failed_last_24h"] == 2, stats
