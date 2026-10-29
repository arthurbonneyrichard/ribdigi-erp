"""Customer statement of account: print (HTML/PDF) and email with the PDF attached."""

from __future__ import annotations

import pyotp
import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


@pytest.mark.asyncio
async def test_customer_statement_print_and_email(client, seeded, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()

    made = await ac.post("/api/v1/customers", headers=admin, json={"name": "Statement Buyer", "email": "statement-buyer@example.com"})
    assert made.status_code == 200, made.text
    cid = made.json()["data"]["id"]
    silent = await ac.post("/api/v1/customers", headers=admin, json={"name": "Statement Silent"})
    silent_id = silent.json()["data"]["id"]

    page = await ac.get(f"/api/v1/credit/customers/{cid}/statement/print", headers=admin)
    assert page.status_code == 200, page.text
    assert "Statement of account" in page.text and "Statement Buyer" in page.text and "Still due" in page.text

    pdf = await ac.get(f"/api/v1/credit/customers/{cid}/statement/print?format=pdf", headers=admin)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")

    sent = await ac.post(f"/api/v1/credit/customers/{cid}/statement/send", headers=admin)
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["delivery"]["to"] == "statement-buyer@example.com"
    mail = get_dev_outbox()[-1]
    assert "Statement of account" in mail["subject"]
    assert any(a["filename"].endswith(".pdf") for a in mail.get("attachments") or [])

    missing = await ac.post(f"/api/v1/credit/customers/{silent_id}/statement/send", headers=admin)
    assert missing.status_code == 400, missing.text
    override = await ac.post(f"/api/v1/credit/customers/{silent_id}/statement/send?to=owner@example.com", headers=admin)
    assert override.status_code == 200, override.text
    bad = await ac.post(f"/api/v1/credit/customers/{silent_id}/statement/send?to=not-an-email", headers=admin)
    assert bad.status_code == 422, bad.text
