"""Marketing unsubscribe links and data deletion requests (privacy audit, 15 Nov 2026)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app import emailer
from app import models as m
from app import privacy
from app.security import hash_password
from tests.conftest import auth_headers, platform_owner_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _console_email(monkeypatch):
    emailer.clear_dev_outbox()
    for mod in ("app.email_settings.settings", "app.emailer.settings"):
        monkeypatch.setattr(f"{mod}.EMAIL_ENABLED", True)
        monkeypatch.setattr(f"{mod}.SMTP_HOST", "")
        monkeypatch.setattr(f"{mod}.SMTP_FROM_EMAIL", "noreply@localhost")
    yield
    emailer.clear_dev_outbox()


async def _add_beta_admin(seed) -> str:
    from app import db as db_mod

    async with db_mod.SessionLocal() as db:
        user = m.User(
            tenant_id=seed["t2"].id,
            email="boss@beta.example.com",
            full_name="Beta Boss",
            role="company_admin",
            password_hash=hash_password("SecurePass123!"),
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        await db.commit()
        return user.id


def _link_params(url: str) -> dict:
    q = parse_qs(urlparse(url).query)
    return {"e": q["e"][0], "t": q["t"][0]}


# ---- Unsubscribe links --------------------------------------------------------------


def test_link_verifies_only_for_its_own_address():
    url = privacy.unsubscribe_page_url("Someone@Example.com")
    p = _link_params(url)
    assert privacy.verify_link(p["e"], p["t"]) == "someone@example.com"
    other = _link_params(privacy.unsubscribe_page_url("other@example.com"))
    # Someone else's token does not unlock this address, and a changed token fails.
    assert privacy.verify_link(p["e"], other["t"]) is None
    assert privacy.verify_link(p["e"], p["t"][:-1] + ("A" if p["t"][-1] != "A" else "B")) is None
    assert privacy.verify_link("not-base64!!", p["t"]) is None


async def test_marketing_send_has_unsubscribe_and_skips_unsubscribed(client):
    ac, seed = client
    await _add_beta_admin(seed)
    owner = await platform_owner_headers(ac, seed)
    message = {"subject": "News", "body": "We added reports.", "confirm": True}

    first = await ac.post("/api/v1/platform/email/send", json=message, headers=owner)
    assert first.status_code == 200, first.text
    mail = emailer.get_dev_outbox()[-1]
    assert mail["to"] == ["boss@beta.example.com"]
    assert "Unsubscribe" in mail["text_body"] and "Unsubscribe from these emails" in mail["html_body"]
    assert mail["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    one_click = mail["headers"]["List-Unsubscribe"].strip("<>")
    p = _link_params(one_click)

    # The page shows a masked address; the person unsubscribes without signing in.
    page = await ac.get("/api/v1/email/unsubscribe", params=p)
    assert page.status_code == 200, page.text
    assert page.json()["data"] == {"email": "bo**@beta.example.com", "subscribed": True}
    done = await ac.post("/api/v1/email/unsubscribe", params=p)
    assert done.status_code == 200, done.text
    assert done.json()["data"]["subscribed"] is False
    again = await ac.post("/api/v1/email/unsubscribe", params=p)  # one-click may repeat
    assert again.status_code == 200

    emailer.clear_dev_outbox()
    preview = await ac.post("/api/v1/platform/email/preview", json={}, headers=owner)
    assert preview.json()["data"]["recipient_count"] == 0
    assert preview.json()["data"]["unsubscribed_skipped"] == 1
    blocked = await ac.post("/api/v1/platform/email/send", json=message, headers=owner)
    assert blocked.status_code == 422
    assert emailer.get_dev_outbox() == []

    # A genuine service notice still reaches the admin, without an unsubscribe link.
    notice = await ac.post("/api/v1/platform/email/send", json={**message, "kind": "service"}, headers=owner)
    assert notice.status_code == 200, notice.text
    mail = emailer.get_dev_outbox()[-1]
    assert mail["to"] == ["boss@beta.example.com"]
    assert "service notice" in mail["text_body"]
    assert "List-Unsubscribe" not in mail["headers"]

    back = await ac.post("/api/v1/email/resubscribe", json=p)
    assert back.status_code == 200 and back.json()["data"]["subscribed"] is True
    preview = await ac.post("/api/v1/platform/email/preview", json={}, headers=owner)
    assert preview.json()["data"]["recipient_count"] == 1


async def test_tampered_unsubscribe_link_is_refused(client):
    ac, _seed = client
    p = _link_params(privacy.unsubscribe_page_url("boss@beta.example.com"))
    forged = {"e": privacy.encoded_email("victim@example.com"), "t": p["t"]}
    r = await ac.post("/api/v1/email/unsubscribe", params=forged)
    assert r.status_code == 400
    bad = await ac.get("/api/v1/email/unsubscribe", params={"e": "x", "t": "y"})
    assert bad.status_code == 422


async def test_signed_in_user_turns_marketing_email_off_and_on(client):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/me/marketing-email", headers=admin)
    assert r.status_code == 200 and r.json()["data"]["subscribed"] is True
    off = await ac.patch("/api/v1/me/marketing-email", json={"subscribed": False}, headers=admin)
    assert off.status_code == 200
    assert (await ac.get("/api/v1/me/marketing-email", headers=admin)).json()["data"]["subscribed"] is False
    on = await ac.patch("/api/v1/me/marketing-email", json={"subscribed": True}, headers=admin)
    assert on.json()["data"]["subscribed"] is True


# ---- Deletion requests ----------------------------------------------------------------


async def test_personal_deletion_request_needs_password_and_is_completed_on_approval(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")

    wrong = await ac.post(
        "/api/v1/privacy/deletion-requests", json={"scope": "my_account", "password": "nope"}, headers=cashier
    )
    assert wrong.status_code == 401
    staff_company = await ac.post(
        "/api/v1/privacy/deletion-requests",
        json={"scope": "company", "password": "SecurePass123!"},
        headers=cashier,
    )
    assert staff_company.status_code == 403

    made = await ac.post(
        "/api/v1/privacy/deletion-requests",
        json={"scope": "my_account", "password": "SecurePass123!", "reason": "I left the shop"},
        headers=cashier,
    )
    assert made.status_code == 200, made.text
    req = made.json()["data"]
    assert req["status"] == "pending"
    dup = await ac.post(
        "/api/v1/privacy/deletion-requests",
        json={"scope": "my_account", "password": "SecurePass123!"},
        headers=cashier,
    )
    assert dup.status_code == 409

    listed = await ac.get("/api/v1/platform/privacy/deletion-requests?status=pending", headers=owner)
    assert listed.status_code == 200, listed.text
    assert [r["id"] for r in listed.json()["data"]] == [req["id"]]
    assert listed.json()["data"][0]["company_slug"] == "alpha"

    refuse_blank = await ac.post(
        f"/api/v1/platform/privacy/deletion-requests/{req['id']}/decide", json={"decision": "reject"}, headers=owner
    )
    assert refuse_blank.status_code == 422
    approve = await ac.post(
        f"/api/v1/platform/privacy/deletion-requests/{req['id']}/decide", json={"decision": "approve"}, headers=owner
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["data"]["status"] == "completed"

    from app import db as db_mod

    async with db_mod.SessionLocal() as db:
        gone = (
            await db.execute(select(m.User).where(m.User.email == "cashier@alpha.example.com"))
        ).scalar_one_or_none()
        assert gone is None
        actions = {
            a for (a,) in await db.execute(select(m.AuditLog.action).where(m.AuditLog.entity == "data_deletion_request"))
        }
        assert {"data_deletion_requested", "data_deletion_completed"} <= actions


async def test_company_deletion_request_is_admin_only_and_tenant_isolated(client):
    ac, seed = client
    beta_admin_id = await _add_beta_admin(seed)
    assert beta_admin_id
    alpha_admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    beta_admin = await auth_headers(ac, email="boss@beta.example.com", tenant_slug="beta")
    owner = await platform_owner_headers(ac, seed)

    made = await ac.post(
        "/api/v1/privacy/deletion-requests",
        json={"scope": "company", "password": "SecurePass123!", "reason": "Closing the business"},
        headers=beta_admin,
    )
    assert made.status_code == 200, made.text
    rid = made.json()["data"]["id"]

    # Another company cannot see or cancel it.
    assert (await ac.get("/api/v1/privacy/deletion-requests", headers=alpha_admin)).json()["data"] == []
    other = await ac.post(f"/api/v1/privacy/deletion-requests/{rid}/cancel", headers=alpha_admin)
    assert other.status_code == 404
    # A company admin cannot decide requests.
    decide = await ac.post(
        f"/api/v1/platform/privacy/deletion-requests/{rid}/decide", json={"decision": "approve"}, headers=alpha_admin
    )
    assert decide.status_code == 403

    approve = await ac.post(
        f"/api/v1/platform/privacy/deletion-requests/{rid}/decide",
        json={"decision": "approve", "note": "Export sent first"},
        headers=owner,
    )
    assert approve.status_code == 200, approve.text
    # A company request is not carried out automatically: the company stays until the owner deletes it.
    assert approve.json()["data"]["status"] == "approved"
    from app import db as db_mod

    async with db_mod.SessionLocal() as db:
        assert await db.get(m.Tenant, seed["t2"].id) is not None
    done = await ac.post(
        f"/api/v1/platform/privacy/deletion-requests/{rid}/decide", json={"decision": "complete"}, headers=owner
    )
    assert done.json()["data"]["status"] == "completed"


async def test_requester_can_cancel_a_pending_request(client):
    ac, _seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    made = await ac.post(
        "/api/v1/privacy/deletion-requests",
        json={"scope": "my_account", "password": "SecurePass123!"},
        headers=mgr,
    )
    rid = made.json()["data"]["id"]
    r = await ac.post(f"/api/v1/privacy/deletion-requests/{rid}/cancel", headers=mgr)
    assert r.status_code == 200 and r.json()["data"]["status"] == "cancelled"
    again = await ac.post(f"/api/v1/privacy/deletion-requests/{rid}/cancel", headers=mgr)
    assert again.status_code == 409
