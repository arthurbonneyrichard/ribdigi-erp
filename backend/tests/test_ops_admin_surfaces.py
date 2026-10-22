"""Ops/admin surfaces: isolation, department create, audit 403, backup honesty, AI scope."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_department_create_unique_name_and_list(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "UXOPS", "name": "Ops UX Dept"},
    )
    assert created.status_code == 200, created.text
    dup = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "UXOPS2", "name": "Ops UX Dept"},
    )
    assert dup.status_code == 409, dup.text
    listed = await ac.get("/api/v1/departments", headers=headers)
    assert listed.status_code == 200
    names = {r["name"] for r in listed.json()["data"]}
    assert "Ops UX Dept" in names
    assert "Beta" not in names


@pytest.mark.asyncio
async def test_cashier_audit_logs_403(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/audit-logs", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_cannot_be_erased(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    listed = await ac.get("/api/v1/audit-logs?limit=1", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    if not rows:
        pytest.skip("no audit rows")
    log_id = rows[0]["id"]
    deleted = await ac.delete(f"/api/v1/audit-logs/{log_id}", headers=headers)
    assert deleted.status_code == 403
    patched = await ac.patch(f"/api/v1/audit-logs/{log_id}", headers=headers, json={"action": "x"})
    assert patched.status_code == 403
    for row in rows:
        blob = str(row.get("details") or {})
        assert "password" not in blob.lower() or "[redacted]" in blob.lower()


@pytest.mark.asyncio
async def test_backup_create_reports_completed_status(client, tmp_path, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    headers = await _admin(ac, seed)
    r = await ac.post("/api/v1/backup", headers=headers, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["status"] == "completed"
    assert "created" in (body.get("message") or "").lower()
    assert "storage_path" not in body["data"]


@pytest.mark.asyncio
async def test_ai_insights_and_chat_tenant_scope(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    insights = await ac.get("/api/v1/ai/insights", headers=headers)
    assert insights.status_code == 200, insights.text
    data = insights.json()["data"]
    text = " ".join(data.get("insights") or [])
    assert "Beta" not in text
    chat = await ac.post("/api/v1/ai/chat", headers=headers, json={"message": "hello books"})
    assert chat.status_code == 503
