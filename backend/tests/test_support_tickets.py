"""Tenant-isolated support tickets, owner desk, and notification outbox."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models as m
from app.emailer import EmailResult
from app.main import app
from app.rbac import permissions_for_role
from app.security import hash_password
from app.support_tickets import allocate_reference, deliver_pending_support_emails
from tests.conftest import auth_headers

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
TXT = b"Printer jammed on lane 2.\n"


async def _user(email: str, role: str, tenant_id: str) -> None:
    factory = app.state.session_factory
    async with factory() as db:
        db.add(
            m.User(
                tenant_id=tenant_id,
                email=email,
                full_name=email.split("@")[0],
                password_hash=hash_password("SecurePass123!"),
                role=role,
                email_verified=True,
                permissions=permissions_for_role(role),
                totp_enabled=False,
                is_active=True,
            )
        )
        await db.commit()


async def _login(ac, email: str, slug: str = "alpha") -> dict:
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _outbox() -> list[dict]:
    factory = app.state.session_factory
    async with factory() as db:
        rows = (await db.execute(select(m.SupportEmailOutbox))).scalars().all()
        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "recipient_email": row.recipient_email,
                "status": row.status,
                "attempts": row.attempts,
            }
            for row in rows
        ]


async def _deliver() -> None:
    factory = app.state.session_factory
    async with factory() as db:
        await deliver_pending_support_emails(db)
        await db.commit()


@pytest.mark.asyncio
async def test_tenant_isolation_visibility_and_owner_gate(client):
    ac, seed = client
    cashier = await _login(ac, "cashier@alpha.example.com")
    other = await _login(ac, "cashier@beta.example.com", "beta")
    admin = await _login(ac, "admin@alpha.example.com")
    manager = await _login(ac, "mgr@alpha.example.com")
    await _user("finance@alpha.example.com", "platform_finance", seed["t1"].id)
    await _user("desk@alpha.example.com", "platform_support", seed["t1"].id)
    finance = await _login(ac, "finance@alpha.example.com")
    desk = await _login(ac, "desk@alpha.example.com")

    created = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "POS drawer stuck",
            "description": "The cash drawer stays closed after a cash sale.",
            "category": "pos_sales",
            "priority": "high",
        },
    )
    assert created.status_code == 200, created.text
    ticket = created.json()["data"]["ticket"]
    assert ticket["reference"].startswith(f"RIB-{datetime.utcnow().year}-")
    assert "storage_key" not in created.text

    hidden = await ac.get(f"/api/v1/support/tickets/{ticket['id']}", headers=other)
    assert hidden.status_code == 404, hidden.text
    by_ref = await ac.get(
        f"/api/v1/support/tickets/by-reference/{ticket['reference']}", headers=other
    )
    assert by_ref.status_code == 404, by_ref.text
    reply = await ac.post(
        f"/api/v1/support/tickets/{ticket['id']}/replies",
        headers=other,
        json={"body": "I should not see this."},
    )
    assert reply.status_code == 404, reply.text

    own_list = await ac.get("/api/v1/support/tickets", headers=manager)
    assert own_list.status_code == 200
    assert all(row["id"] != ticket["id"] for row in own_list.json()["data"]["items"])

    admin_get = await ac.get(f"/api/v1/support/tickets/{ticket['id']}", headers=admin)
    assert admin_get.status_code == 200, admin_get.text

    blocked = await ac.get("/api/v1/support/desk/tickets", headers=finance)
    assert blocked.status_code == 403, blocked.text
    blocked_note = await ac.post(
        f"/api/v1/support/desk/tickets/{ticket['id']}/notes",
        headers=finance,
        json={"body": "secret staff note"},
    )
    assert blocked_note.status_code == 403, blocked_note.text

    managed = await ac.patch(
        f"/api/v1/support/desk/tickets/{ticket['id']}",
        headers=desk,
        json={"priority": "urgent", "status": "in_progress"},
    )
    assert managed.status_code == 200, managed.text
    assert managed.json()["data"]["ticket"]["priority"] == "urgent"
    assert managed.json()["data"]["ticket"]["status"] == "in_progress"

    poison = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Nope",
            "description": "Should reject extra tenant.",
            "category": "bug_other",
            "tenant_id": seed["t2"].id,
        },
    )
    assert poison.status_code == 422, poison.text


@pytest.mark.asyncio
async def test_company_ticket_lists_stay_inside_one_tenant(client):
    ac, seed = client
    alpha = await _login(ac, "cashier@alpha.example.com")
    beta = await _login(ac, "cashier@beta.example.com", "beta")
    admin = await _login(ac, "admin@alpha.example.com")
    await _user("queue@alpha.example.com", "platform_support", seed["t1"].id)
    desk = await _login(ac, "queue@alpha.example.com")

    alpha_ticket = await ac.post(
        "/api/v1/support/tickets",
        headers=alpha,
        json={
            "subject": "Alpha receipt printer",
            "description": "The alpha store receipt printer will not print.",
            "category": "pos_sales",
        },
    )
    assert alpha_ticket.status_code == 200, alpha_ticket.text
    alpha_id = alpha_ticket.json()["data"]["ticket"]["id"]
    beta_ticket = await ac.post(
        "/api/v1/support/tickets",
        headers=beta,
        json={
            "subject": "Beta till frozen",
            "description": "The beta company till screen does not move.",
            "category": "pos_sales",
        },
    )
    assert beta_ticket.status_code == 200, beta_ticket.text
    beta_id = beta_ticket.json()["data"]["ticket"]["id"]

    alpha_list = await ac.get("/api/v1/support/tickets", headers=admin)
    assert alpha_list.status_code == 200, alpha_list.text
    alpha_ids = {row["id"] for row in alpha_list.json()["data"]["items"]}
    assert alpha_id in alpha_ids
    assert beta_id not in alpha_ids

    beta_list = await ac.get("/api/v1/support/tickets", headers=beta)
    assert beta_list.status_code == 200, beta_list.text
    beta_ids = {row["id"] for row in beta_list.json()["data"]["items"]}
    assert beta_id in beta_ids
    assert alpha_id not in beta_ids

    cross = await ac.get(f"/api/v1/support/tickets/{beta_id}", headers=admin)
    assert cross.status_code == 404, cross.text
    denied = await ac.get("/api/v1/support/desk/tickets", headers=admin)
    assert denied.status_code == 403, denied.text

    desk_list = await ac.get("/api/v1/support/desk/tickets", headers=desk)
    assert desk_list.status_code == 200, desk_list.text
    by_id = {row["id"]: row for row in desk_list.json()["data"]["items"]}
    assert by_id[alpha_id]["tenant"]["slug"] == "alpha"
    assert by_id[beta_id]["tenant"]["slug"] == "beta"

    summary = await ac.get("/api/v1/platform/reports/summary", headers=desk)
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["open_support_tickets"] >= 2
    tenant_summary = await ac.get("/api/v1/platform/reports/summary", headers=admin)
    assert tenant_summary.status_code == 403, tenant_summary.text


@pytest.mark.asyncio
async def test_internal_notes_hidden_and_not_emailed(client, monkeypatch):
    ac, seed = client
    calls: list[dict] = []

    async def fake_send(**kwargs):
        calls.append(kwargs)
        return EmailResult(sent=True, mode="console", recipients=[kwargs.get("to", "")])

    monkeypatch.setattr("app.emailer.send_email", fake_send)
    await _user("desk@alpha.example.com", "platform_support", seed["t1"].id)
    cashier = await _login(ac, "cashier@alpha.example.com")
    admin = await _login(ac, "admin@alpha.example.com")
    desk = await _login(ac, "desk@alpha.example.com")
    created = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Login loop",
            "description": "Account and login page returns to itself.",
            "category": "account_login",
        },
    )
    assert created.status_code == 200, created.text
    ticket_id = created.json()["data"]["ticket"]["id"]
    before = len(await _outbox())
    noted = await ac.post(
        f"/api/v1/support/desk/tickets/{ticket_id}/notes",
        headers=desk,
        json={"body": "Internal: check the session cookie only."},
    )
    assert noted.status_code == 200, noted.text
    assert any(row["visibility"] == "internal" for row in noted.json()["data"]["messages"])
    assert len(await _outbox()) == before
    assert calls == []

    tenant_view = await ac.get(f"/api/v1/support/tickets/{ticket_id}", headers=cashier)
    assert tenant_view.status_code == 200
    assert all(row["visibility"] == "public" for row in tenant_view.json()["data"]["messages"])
    assert "session cookie" not in tenant_view.text
    admin_view = await ac.get(f"/api/v1/support/tickets/{ticket_id}", headers=admin)
    assert "session cookie" not in admin_view.text


@pytest.mark.asyncio
async def test_status_transitions_reopen_and_staff_reply(client, monkeypatch):
    ac, seed = client

    async def fake_send(**kwargs):
        return EmailResult(sent=True, mode="console", recipients=[kwargs.get("to", "")])

    monkeypatch.setattr("app.emailer.send_email", fake_send)
    await _user("desk@alpha.example.com", "platform_support", seed["t1"].id)
    cashier = await _login(ac, "cashier@alpha.example.com")
    desk = await _login(ac, "desk@alpha.example.com")
    created = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Barcode will not print",
            "description": "Printing, barcode, and receipt layout is blank.",
            "category": "printing_barcode_receipt",
        },
    )
    ticket_id = created.json()["data"]["ticket"]["id"]

    resolved = await ac.patch(
        f"/api/v1/support/desk/tickets/{ticket_id}",
        headers=desk,
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200, resolved.text
    staff_reply = await ac.post(
        f"/api/v1/support/desk/tickets/{ticket_id}/replies",
        headers=desk,
        json={"body": "We shipped a layout fix."},
    )
    assert staff_reply.status_code == 200, staff_reply.text
    assert staff_reply.json()["data"]["ticket"]["status"] == "resolved"

    reopened = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/replies",
        headers=cashier,
        json={"body": "It is still blank on the second printer."},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["data"]["ticket"]["status"] == "in_progress"

    closed = await ac.patch(
        f"/api/v1/support/desk/tickets/{ticket_id}",
        headers=desk,
        json={"status": "closed"},
    )
    assert closed.status_code == 200, closed.text
    illegal = await ac.patch(
        f"/api/v1/support/desk/tickets/{ticket_id}",
        headers=desk,
        json={"status": "resolved"},
    )
    assert illegal.status_code == 409, illegal.text
    tenant_on_closed = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/replies",
        headers=cashier,
        json={"body": "Please reopen."},
    )
    assert tenant_on_closed.status_code == 409, tenant_on_closed.text
    staff_reopen = await ac.post(
        f"/api/v1/support/desk/tickets/{ticket_id}/reopen", headers=desk
    )
    assert staff_reopen.status_code == 200, staff_reopen.text
    assert staff_reopen.json()["data"]["ticket"]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_attachments_validated_and_scoped(client):
    ac, seed = client
    cashier = await _login(ac, "cashier@alpha.example.com")
    other = await _login(ac, "cashier@beta.example.com", "beta")
    created = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Stock photo",
            "description": "Inventory count photo attached.",
            "category": "inventory_stock",
        },
    )
    ticket_id = created.json()["data"]["ticket"]["id"]
    bad = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/attachments",
        headers=cashier,
        files={"file": ("photo.png", b"not a png", "image/png")},
    )
    assert bad.status_code == 422, bad.text
    exe = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/attachments",
        headers=cashier,
        files={"file": ("run.exe", b"MZ" + b"\x00" * 8, "application/octet-stream")},
    )
    assert exe.status_code == 422, exe.text
    good = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/attachments",
        headers=cashier,
        files={"file": ("count.png", PNG, "text/plain")},
    )
    assert good.status_code == 200, good.text
    assert "storage_key" not in good.text
    attachment_id = good.json()["data"]["id"]
    stolen = await ac.get(
        f"/api/v1/support/tickets/{ticket_id}/attachments/{attachment_id}",
        headers=other,
    )
    assert stolen.status_code == 404, stolen.text
    downloaded = await ac.get(
        f"/api/v1/support/tickets/{ticket_id}/attachments/{attachment_id}",
        headers=cashier,
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content.startswith(b"\x89PNG")
    assert "nosniff" in downloaded.headers.get("x-content-type-options", "")
    pdf = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/attachments",
        headers=cashier,
        files={"file": ("note.pdf", PDF, "application/octet-stream")},
    )
    assert pdf.status_code == 200, pdf.text
    text = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/attachments",
        headers=cashier,
        files={"file": ("note.txt", TXT, "application/octet-stream")},
    )
    assert text.status_code == 200, text.text
    script = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "<script>alert(1)</script>",
            "description": "unsafe",
            "category": "bug_other",
        },
    )
    assert script.status_code == 422, script.text


@pytest.mark.asyncio
async def test_recipients_and_notification_matrix(client, monkeypatch):
    ac, seed = client
    calls: list[str] = []

    async def fake_send(**kwargs):
        calls.append(kwargs["to"])
        return EmailResult(sent=True, mode="console", recipients=[kwargs["to"]])

    monkeypatch.setattr("app.emailer.send_email", fake_send)
    await _user("owner@alpha.example.com", "platform_admin", seed["t1"].id)
    await _user("desk@alpha.example.com", "platform_support", seed["t1"].id)
    owner = await _login(ac, "owner@alpha.example.com")
    desk = await _login(ac, "desk@alpha.example.com")
    cashier = await _login(ac, "cashier@alpha.example.com")

    denied = await ac.get("/api/v1/support/desk/recipients", headers=desk)
    assert denied.status_code == 403, denied.text

    listed = await ac.get("/api/v1/support/desk/recipients", headers=owner)
    assert listed.status_code == 200, listed.text
    emails = [row["email"] for row in listed.json()["data"]["recipients"]]
    assert emails == ["support@ribdigihouse.com"]
    assert "password" not in listed.text.lower() or "does not" in listed.text.lower()
    default_id = listed.json()["data"]["recipients"][0]["id"]

    invalid = await ac.post(
        "/api/v1/support/desk/recipients",
        headers=owner,
        json={"email": "not-an-email"},
    )
    assert invalid.status_code == 422, invalid.text
    duplicate = await ac.post(
        "/api/v1/support/desk/recipients",
        headers=owner,
        json={"email": " Support@RibdigiHouse.com "},
    )
    assert duplicate.status_code == 422, duplicate.text
    added = await ac.post(
        "/api/v1/support/desk/recipients",
        headers=owner,
        json={"email": " Night@RibdigiHouse.com "},
    )
    assert added.status_code == 200, added.text
    night_id = added.json()["data"]["id"]
    assert added.json()["data"]["email"] == "night@ribdigihouse.com"

    edited = await ac.patch(
        f"/api/v1/support/desk/recipients/{night_id}",
        headers=owner,
        json={"email": "ops@ribdigihouse.com"},
    )
    assert edited.status_code == 200, edited.text
    last_off = await ac.patch(
        f"/api/v1/support/desk/recipients/{default_id}",
        headers=owner,
        json={"is_active": False},
    )
    assert last_off.status_code == 200, last_off.text
    cannot_drop = await ac.delete(
        f"/api/v1/support/desk/recipients/{night_id}", headers=owner
    )
    assert cannot_drop.status_code == 422, cannot_drop.text
    await ac.patch(
        f"/api/v1/support/desk/recipients/{default_id}",
        headers=owner,
        json={"is_active": True},
    )
    deactivated = await ac.patch(
        f"/api/v1/support/desk/recipients/{night_id}",
        headers=owner,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text

    calls.clear()
    created = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Supplier bill mismatch",
            "description": "Purchases and suppliers total does not match the GRN.",
            "category": "purchases_suppliers",
        },
    )
    assert created.status_code == 200, created.text
    ticket_id = created.json()["data"]["ticket"]["id"]
    queued = await _outbox()
    created_rows = [row for row in queued if row["event_type"] == "tenant_created"]
    assert {row["recipient_email"] for row in created_rows} == {"support@ribdigihouse.com"}
    assert all(row["status"] == "pending" for row in created_rows)
    assert calls == []
    await _deliver()
    assert calls == ["support@ribdigihouse.com"]
    sent_rows = [row for row in await _outbox() if row["event_type"] == "tenant_created"]
    assert all(row["status"] == "sent" for row in sent_rows)
    await _deliver()
    assert calls == ["support@ribdigihouse.com"]

    calls.clear()
    replied = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/replies",
        headers=cashier,
        json={"body": "Here is the supplier invoice number SI-44."},
    )
    assert replied.status_code == 200, replied.text
    reply_rows = [row for row in await _outbox() if row["event_type"] == "tenant_replied"]
    assert {row["recipient_email"] for row in reply_rows} == {"support@ribdigihouse.com"}

    resolved = await ac.patch(
        f"/api/v1/support/desk/tickets/{ticket_id}",
        headers=desk,
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200, resolved.text
    reopened = await ac.post(
        f"/api/v1/support/tickets/{ticket_id}/replies",
        headers=cashier,
        json={"body": "The mismatch is back after refresh."},
    )
    assert reopened.status_code == 200, reopened.text
    assert any(row["event_type"] == "tenant_reopened" for row in await _outbox())

    calls.clear()
    public = await ac.post(
        f"/api/v1/support/desk/tickets/{ticket_id}/replies",
        headers=desk,
        json={"body": "Please resend the supplier bill."},
    )
    assert public.status_code == 200, public.text
    public_rows = [row for row in await _outbox() if row["event_type"] == "public_reply"]
    public_emails = {row["recipient_email"] for row in public_rows}
    assert "cashier@alpha.example.com" in public_emails
    assert "admin@alpha.example.com" in public_emails
    assert "support@ribdigihouse.com" not in public_emails
    assert all(row["status"] == "pending" for row in public_rows)

    failed_calls: list[str] = []

    async def fail_send(**kwargs):
        failed_calls.append(kwargs["to"])
        return EmailResult(sent=False, mode="disabled", error="smtp unavailable", recipients=[kwargs["to"]])

    monkeypatch.setattr("app.emailer.send_email", fail_send)
    await _deliver()
    failed = [row for row in await _outbox() if row["event_type"] == "public_reply"]
    assert failed
    assert all(row["status"] == "failed" for row in failed)
    visible = await ac.get("/api/v1/support/desk/deliveries?status=failed", headers=desk)
    assert visible.status_code == 200, visible.text
    assert any(row["status"] == "failed" for row in visible.json()["data"]["items"])

    async def ok_send(**kwargs):
        calls.append(kwargs["to"])
        return EmailResult(sent=True, mode="smtp", recipients=[kwargs["to"]])

    monkeypatch.setattr("app.emailer.send_email", ok_send)
    before_attempts = failed[0]["attempts"]
    retried = await ac.post(
        f"/api/v1/support/desk/deliveries/{failed[0]['id']}/retry", headers=desk
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["data"]["resent"] is True
    again = await ac.post(
        f"/api/v1/support/desk/deliveries/{failed[0]['id']}/retry", headers=desk
    )
    assert again.status_code == 200, again.text
    assert again.json()["data"]["resent"] is False
    refreshed = [row for row in await _outbox() if row["id"] == failed[0]["id"]][0]
    assert refreshed["status"] == "sent"
    assert refreshed["attempts"] == before_attempts + 1

    removed = await ac.delete(f"/api/v1/support/desk/recipients/{night_id}", headers=owner)
    assert removed.status_code == 200, removed.text


@pytest.mark.asyncio
async def test_starter_hides_purchasing_category(client):
    ac, seed = client
    factory = app.state.session_factory
    async with factory() as db:
        tenant = await db.get(m.Tenant, seed["t1"].id)
        tenant.package_code = "starter"
        await db.commit()
    cashier = await _login(ac, "cashier@alpha.example.com")
    meta = await ac.get("/api/v1/support/categories", headers=cashier)
    assert meta.status_code == 200, meta.text
    codes = {row["code"] for row in meta.json()["data"]["categories"]}
    assert "purchases_suppliers" not in codes
    assert "account_login" in codes
    assert "bug_other" in codes
    rejected = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Hidden category",
            "description": "Purchasing should be unavailable on starter.",
            "category": "purchases_suppliers",
        },
    )
    assert rejected.status_code == 422, rejected.text


@pytest.mark.asyncio
async def test_ticket_categories_follow_industry_desk(client):
    ac, seed = client
    cashier = await _login(ac, "cashier@alpha.example.com")
    await _user("desk-ind@alpha.example.com", "platform_support", seed["t1"].id)
    desk = await _login(ac, "desk-ind@alpha.example.com")
    factory = app.state.session_factory

    async def labels_for(industry: str) -> dict[str, str]:
        async with factory() as db:
            tenant = await db.get(m.Tenant, seed["t1"].id)
            tenant.industry = industry
            await db.commit()
        meta = await ac.get("/api/v1/support/categories", headers=cashier)
        assert meta.status_code == 200, meta.text
        return {row["code"]: row["label"] for row in meta.json()["data"]["categories"]}

    retail = await labels_for("retail")
    assert retail.get("pos_sales") == "POS and sales"
    hotel = await labels_for("hotel")
    assert hotel.get("pos_sales") == "Shop till"
    assert hotel.get("inventory_stock") == "Supplies"
    assert hotel.get("finance_reports") == "Folios, cashiering, and reports"
    hotel_meta = await ac.get("/api/v1/support/categories", headers=cashier)
    hotel_help = {row["code"]: row.get("help") or "" for row in hotel_meta.json()["data"]["categories"]}
    assert "Guest folio" in hotel_help["pos_sales"]
    assert "Till sales" not in hotel_help["pos_sales"]
    assert hotel_meta.json()["data"]["industry"] == "hotel"
    restaurant = await labels_for("restaurant")
    assert restaurant.get("pos_sales") == "Till, orders and bills"
    assert restaurant.get("inventory_stock") == "Ingredients, menu and recipes"
    assert restaurant.get("purchases_suppliers") == "Supplier orders and market runs"
    pharmacy = await labels_for("pharmacy")
    assert pharmacy.get("pos_sales") == "POS and sales"
    for removed in ("wholesale", "fmcg", "hospital"):
        hidden = await labels_for(removed)
        assert "pos_sales" not in hidden
        assert "account_login" in hidden
        assert "bug_other" in hidden
    opened = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Sign-in stays on the login page",
            "description": "The company cannot get past the sign-in screen.",
            "category": "account_login",
        },
    )
    assert opened.status_code == 200, opened.text
    ticket_id = opened.json()["data"]["ticket"]["id"]
    rejected = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Removed desk should stay hidden",
            "description": "Wholesale, FMCG, and hospital are not operating desks.",
            "category": "pos_sales",
        },
    )
    assert rejected.status_code == 422, rejected.text
    moved = await ac.patch(
        f"/api/v1/support/desk/tickets/{ticket_id}",
        headers=desk,
        json={"category": "pos_sales"},
    )
    assert moved.status_code == 422, moved.text


@pytest.mark.asyncio
async def test_desk_filters_industry_and_company_categories(client):
    ac, seed = client
    wholesale_user = await _login(ac, "cashier@alpha.example.com")
    pharmacy_user = await _login(ac, "cashier@beta.example.com", "beta")
    await _user("desk-filter@alpha.example.com", "platform_support", seed["t1"].id)
    desk = await _login(ac, "desk-filter@alpha.example.com")
    factory = app.state.session_factory
    async with factory() as db:
        alpha = await db.get(m.Tenant, seed["t1"].id)
        beta = await db.get(m.Tenant, seed["t2"].id)
        alpha.industry = "retail"
        beta.industry = "pharmacy"
        await db.commit()
    wholesale = await ac.post(
        "/api/v1/support/tickets",
        headers=wholesale_user,
        json={
            "subject": "Quote stuck in draft",
            "description": "The wholesale order cannot be confirmed.",
            "category": "pos_sales",
        },
    )
    assert wholesale.status_code == 200, wholesale.text
    wholesale_id = wholesale.json()["data"]["ticket"]["id"]
    pharmacy = await ac.post(
        "/api/v1/support/tickets",
        headers=pharmacy_user,
        json={
            "subject": "Dispense screen blank",
            "description": "The pharmacy till does not list the prescription.",
            "category": "pos_sales",
        },
    )
    assert pharmacy.status_code == 200, pharmacy.text
    listed = await ac.get("/api/v1/support/desk/tickets?industry=retail", headers=desk)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]["items"]
    assert {row["id"] for row in rows} == {wholesale_id}
    assert rows[0]["category_label"] == "POS and sales"
    assert rows[0]["tenant"]["industry"] == "retail"
    unknown = await ac.get("/api/v1/support/desk/tickets?industry=not-an-industry", headers=desk)
    assert unknown.status_code == 422, unknown.text
    detail = await ac.get(f"/api/v1/support/desk/tickets/{wholesale_id}", headers=desk)
    assert detail.status_code == 200, detail.text
    body = detail.json()["data"]
    labels = {row["code"]: row["label"] for row in body["allowed_categories"]}
    assert labels["pos_sales"] == "POS and sales"
    assert "account_login" in labels
    assert body["ticket"]["category_label"] == "POS and sales"


@pytest.mark.asyncio
async def test_concurrent_references_are_unique(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'refs.db'}"
    engine = create_async_engine(url, connect_args={"timeout": 30})
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def one() -> str:
        async with factory() as db:
            ref = await allocate_reference(db)
            await db.commit()
            return ref

    refs = await asyncio.gather(*[one() for _ in range(8)])
    assert len(set(refs)) == 8
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_is_rate_limited(client, monkeypatch):
    ac, _seed = client
    cashier = await _login(ac, "cashier@alpha.example.com")

    async def deny(*_args, **_kwargs):
        return False, 5, 0

    monkeypatch.setattr("app.support_tickets.settings.RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("app.rate_limit.rate_limiter.allow", deny)
    limited = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "Too many tickets",
            "description": "This create should be limited.",
            "category": "bug_other",
        },
    )
    assert limited.status_code == 429, limited.text
