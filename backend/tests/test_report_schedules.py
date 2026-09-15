"""Tests for scheduled report email delivery."""

from datetime import datetime, timedelta

import pytest

from app import emailer
from app import report_schedules as schedules_svc
from tests.conftest import auth_headers


@pytest.fixture(autouse=True)
def _email_console(monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    yield
    emailer.clear_dev_outbox()


@pytest.mark.asyncio
async def test_create_and_run_schedule(db_session, seeded):
    tenant_id = seeded["t1"].id
    row = await schedules_svc.create_schedule(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        name="Daily summary",
        report_type="summary",
        format="csv",
        frequency="daily",
        hour_utc=0,
        recipients=["ops@example.com", "ops@example.com", "finance@example.com"],
        enabled=True,
    )
    await db_session.commit()
    assert row.recipients == ["ops@example.com", "finance@example.com"]

    with pytest.raises(Exception) as bad_exc:
        await schedules_svc.create_schedule(
            db_session,
            tenant_id=tenant_id,
            user_id=seeded["admin1"].id,
            name="Bad recipients",
            report_type="summary",
            format="csv",
            frequency="daily",
            hour_utc=0,
            recipients=["ops@example.com", "bad"],
            enabled=True,
        )
    assert getattr(bad_exc.value, "status_code", None) == 400

    result = await schedules_svc.run_schedule(
        db_session, tenant_id=tenant_id, schedule=row, force=True
    )
    await db_session.commit()
    assert result["ran"] is True
    assert result["mode"] == "console"
    out = emailer.get_dev_outbox()
    assert len(out) == 1
    assert out[0]["to"] == ["ops@example.com", "finance@example.com"]
    assert out[0]["attachments"]
    assert out[0]["attachments"][0]["filename"].endswith(".csv")
    assert row.last_run_at is not None
    assert row.last_error is None


@pytest.mark.asyncio
async def test_is_schedule_due_respects_gap(db_session, seeded):
    tenant_id = seeded["t1"].id
    row = await schedules_svc.create_schedule(
        db_session,
        tenant_id=tenant_id,
        user_id=None,
        name="Weekly",
        report_type="sales_products",
        format="xlsx",
        frequency="weekly",
        weekday=datetime.utcnow().weekday(),
        hour_utc=0,
        recipients="a@x.com",
    )
    row.last_run_at = datetime.utcnow() - timedelta(hours=1)
    await db_session.flush()
    due, reason = schedules_svc.is_schedule_due(row)
    assert due is False
    assert reason == "already_ran"


@pytest.mark.asyncio
async def test_send_email_attachment_metadata():
    emailer.clear_dev_outbox()
    result = await emailer.send_email(
        to="a@example.com",
        subject="With file",
        text_body="see attach",
        attachments=[
            {
                "filename": "r.csv",
                "content": b"a,b\n1,2\n",
                "content_type": "text/csv",
            }
        ],
    )
    assert result.sent is True
    meta = emailer.get_dev_outbox()[0]["attachments"]
    assert meta[0]["filename"] == "r.csv"
    assert meta[0]["size_bytes"] == 8


@pytest.mark.asyncio
async def test_schedules_api_crud(client):
    import pyotp

    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    create = await ac.post(
        "/api/v1/reports/schedules",
        headers=headers,
        json={
            "name": "API schedule",
            "report_type": "inventory_low_stock",
            "format": "pdf",
            "frequency": "daily",
            "hour_utc": 7,
            "recipients": ["finance@example.com"],
        },
    )
    assert create.status_code == 200, create.text
    sid = create.json()["data"]["id"]

    listed = await ac.get("/api/v1/reports/schedules", headers=headers)
    assert listed.status_code == 200
    assert any(r["id"] == sid for r in listed.json()["data"])

    run = await ac.post(f"/api/v1/reports/schedules/{sid}/run?force=true", headers=headers)
    assert run.status_code == 200, run.text
    assert run.json()["data"]["ran"] is True

    deleted = await ac.delete(f"/api/v1/reports/schedules/{sid}", headers=headers)
    assert deleted.status_code == 200
