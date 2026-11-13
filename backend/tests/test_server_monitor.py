"""Software owner server monitor: live reading, history, alerts, launch checks."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import metrics as metrics_svc
from app import models as m
from app import server_monitor as svc
from tests.conftest import auth_headers, platform_owner_headers

@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setenv("RIBDIGI_MONITOR_NO_REDIS", "1")
    monkeypatch.setattr("app.server_monitor.settings.MONITOR_PUBLIC_URL", "")
    monkeypatch.setattr("app.server_monitor.settings.FRONTEND_URL", "")
    svc.reset_for_tests()
    metrics_svc.reset_for_tests()
    yield
    svc.reset_for_tests()


@pytest.mark.asyncio
async def test_owner_sees_live_reading_and_tenants_do_not(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)

    res = await ac.get("/api/v1/platform/monitor", headers=owner)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] in {"ok", "warn", "critical"}
    assert data["host"]["cpu_cores"] >= 1
    assert data["database"]["status"] == "ok"
    keys = {c["key"] for c in data["checks"]}
    assert {"cpu", "memory", "disk", "database"} <= keys
    assert data["thresholds"]["cpu_pct"] > 0
    assert "uptime" in data and data["uptime"]["day"]["samples"] >= 1
    # Nothing secret leaks into the reading.
    body = res.text.lower()
    assert "password" not in body and "database_url" not in body

    hist = await ac.get("/api/v1/platform/monitor/history?range=1h", headers=owner)
    assert hist.status_code == 200, hist.text
    assert len(hist.json()["data"]["points"]) >= 1
    assert (await ac.get("/api/v1/platform/monitor/history?range=2y", headers=owner)).status_code == 422

    tenant = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/platform/monitor", headers=tenant)).status_code == 403
    assert (await ac.get("/api/v1/platform/monitor/launch-checks", headers=tenant)).status_code == 403


@pytest.mark.asyncio
async def test_critical_check_alerts_once_then_recovers(client, monkeypatch):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    monkeypatch.setattr("app.server_monitor.settings.MONITOR_CPU_ALERT_PCT", 0.0)

    first = await ac.get("/api/v1/platform/monitor", headers=owner)
    assert any(c["key"] == "cpu" and c["status"] == "critical" for c in first.json()["data"]["checks"])
    svc._mem_samples.clear()  # allow a second stored reading straight away
    await ac.get("/api/v1/platform/monitor", headers=owner)

    alerts = (await ac.get("/api/v1/platform/monitor/alerts", headers=owner)).json()["data"]
    cpu_alerts = [e for e in alerts["events"] if e["key"] == "cpu" and e["kind"] == "alert"]
    assert len(cpu_alerts) == 1, "cooldown keeps it to one alert"
    assert "cpu" in alerts["active"]

    from app import db as db_mod

    async with db_mod.SessionLocal() as db:
        notes = (
            await db.execute(select(m.Notification).where(m.Notification.category == "server_health"))
        ).scalars().all()
    assert any("Processor" in n.title for n in notes)

    monkeypatch.setattr("app.server_monitor.settings.MONITOR_CPU_ALERT_PCT", 1000.0)
    svc._mem_samples.clear()
    await ac.get("/api/v1/platform/monitor", headers=owner)
    alerts = (await ac.get("/api/v1/platform/monitor/alerts", headers=owner)).json()["data"]
    assert "cpu" not in alerts["active"]
    assert alerts["events"][0]["kind"] in {"recovered", "alert"}
    assert any(e["kind"] == "recovered" and e["key"] == "cpu" for e in alerts["events"])


@pytest.mark.asyncio
async def test_launch_checks_and_test_alert(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)

    res = await ac.get("/api/v1/platform/monitor/launch-checks", headers=owner)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    keys = {i["key"] for i in data["items"]}
    assert {"env", "2fa", "keys", "email", "billing", "backups", "https"} <= keys
    assert all(i["status"] in {"pass", "warn", "fail"} for i in data["items"])
    # A failing item always says how to fix it.
    assert all(i["fix"] for i in data["items"] if i["status"] != "pass")
    # Test settings are not production, so the checklist is not ready.
    assert data["ready"] is False

    sent = await ac.post("/api/v1/platform/monitor/test-alert", headers=owner)
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["delivered"] is True


def test_request_window_percentiles_skip_probes():
    metrics_svc.reset_for_tests()
    for i in range(100):
        metrics_svc.observe_request(method="GET", path="/api/v1/sales/invoices", status_code=200,
                                    duration_seconds=(i + 1) / 1000.0)
    metrics_svc.observe_request(method="GET", path="/api/v1/health", status_code=200, duration_seconds=9.0)
    metrics_svc.observe_request(method="POST", path="/api/v1/sales/invoices", status_code=500,
                                duration_seconds=0.05)
    perf = metrics_svc.recent_performance(900)
    assert perf["requests"] == 101
    assert perf["server_errors"] == 1
    assert 90 <= perf["p95_ms"] <= 100
    assert perf["slowest"][0]["path_group"] == "/api/v1/sales"


def test_downsample_keeps_worst_status():
    now = svc._now()
    rows = [{"t": now - 30, "s": "ok", "cpu": 10}, {"t": now - 20, "s": "critical", "cpu": 30}]
    points = svc.downsample(rows, 10, 3600)
    assert len(points) == 1
    assert points[0]["s"] == "critical" and points[0]["cpu"] == 20
    up = svc.uptime_from(rows)
    assert up["healthy_pct"] == 50.0
