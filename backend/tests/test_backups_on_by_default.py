"""Every company gets a nightly backup unless its admin turns it off."""

from __future__ import annotations

import pytest

from app import backup as backup_svc
from app import server_monitor
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_new_company_backs_up_on_schedule_without_setting_anything(client, db_session):
    ac, seed = client
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    settings_row = (await ac.get("/api/v1/backup/settings", headers=h)).json()["data"]
    assert settings_row["enabled"] is True and settings_row["frequency"] == "daily"

    out = await backup_svc.run_scheduled_backup_if_due(db_session, tenant_id=seed["t1"].id, user_id=None)
    await db_session.commit()
    assert out["ran"] is True, out

    # An admin who turns it off stays off.
    r = await ac.patch("/api/v1/backup/settings", headers=h, json={"enabled": False})
    assert r.status_code == 200 and r.json()["data"]["enabled"] is False
    out = await backup_svc.run_scheduled_backup_if_due(db_session, tenant_id=seed["t1"].id, user_id=None)
    assert out == {"ran": False, "reason": "schedule_disabled", "tenant_id": seed["t1"].id}


def test_backup_launch_check_says_why():
    never = server_monitor.backups_fix_text({"age_hours": None, "failed_last_24h": 0, "companies_scheduled": 0})
    assert "ever finished" in never and "No company has scheduled backups" in never and "run_due_backups" in never
    old = server_monitor.backups_fix_text({"age_hours": 50.0, "failed_last_24h": 2, "companies_scheduled": 3})
    assert "50 hours ago" in old and "2 backup(s) failed" in old and "No company" not in old
