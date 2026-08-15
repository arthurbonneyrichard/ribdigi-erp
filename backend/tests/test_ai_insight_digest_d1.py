"""BR-21.2 weekly AI insight digest API, delivery, and UI packaging."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import ai_digest
from app import emailer
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _console_email(monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.email_settings.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.email_settings.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.email_settings.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    yield
    emailer.clear_dev_outbox()


def test_digest_renderer_escapes_tenant_content():
    text, html = emailer.render_ai_insight_digest_bodies(
        company_name="<Acme & Co>",
        insights=["Restock <Widget> & review sales."],
    )

    assert "<Acme & Co>" in text
    assert "Restock <Widget> & review sales." in text
    assert "&lt;Acme &amp; Co&gt;" in html
    assert "Restock &lt;Widget&gt; &amp; review sales." in html
    assert "<Widget>" not in html


@pytest.mark.asyncio
async def test_digest_api_emails_current_user_with_tenant_scoped_insights(
    client,
    db_session,
    seeded,
):
    ac, seed = client
    seed["p1"].stock_qty = 0
    seed["p1"].reorder_level = 5
    seed["p2"].stock_qty = 0
    seed["p2"].reorder_level = 5
    db_session.add(
        m.Product(
            tenant_id=seed["t2"].id,
            name="Beta Second Product",
            sku="B-2",
            cost_price=1,
            selling_price=2,
            stock_qty=0,
            reorder_level=5,
        )
    )
    await db_session.commit()

    headers = await auth_headers(
        ac,
        email="admin@alpha.example.com",
        tenant_slug="alpha",
    )
    response = await ac.post("/api/v1/ai/insights/digest", headers=headers, json={})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["recipient_count"] == 1
    assert data["sent"] == 1
    assert data["failed"] == 0
    assert data["delivery_modes"] == {"console": 1}
    assert data["insights"] == ["1 product(s) are at or below reorder level."]

    outbox = emailer.get_dev_outbox()
    assert len(outbox) == 1
    assert outbox[0]["to"] == ["admin@alpha.example.com"]
    assert outbox[0]["subject"] == "Weekly AI insight digest — Alpha Co"
    assert "1 product(s)" in outbox[0]["text_body"]
    assert "Beta" not in outbox[0]["text_body"]
    assert "<ol>" in outbox[0]["html_body"]

    query = (
        await db_session.execute(
            select(m.AiQuery).where(
                m.AiQuery.tenant_id == seed["t1"].id,
                m.AiQuery.endpoint == "insight_digest",
            )
        )
    ).scalar_one()
    assert query.user_id == seed["admin1"].id
    assert query.status == "ok"
    assert query.details["recipient_count"] == 1


@pytest.mark.asyncio
async def test_scheduled_digest_targets_only_active_tenant_admins(db_session, seeded):
    result = await ai_digest.send_tenant_digest(
        db_session,
        tenant_id=seeded["t1"].id,
        actor_user_id="system",
    )

    assert result["recipient_count"] == 2
    assert result["sent"] == 2
    assert {entry["to"][0] for entry in emailer.get_dev_outbox()} == {
        "admin@alpha.example.com",
        "super@alpha.example.com",
    }


def test_ai_digest_frontend_is_packaged():
    ai_page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    jobs_page = (ROOT / "frontend/app/jobs/page.tsx").read_text(encoding="utf-8")

    assert "/ai/insights/digest" in ai_page
    assert "Email digest to me" in ai_page
    assert "send_weekly_ai_insight_digest" in jobs_page
    assert "Weekly AI insight digest" in jobs_page
