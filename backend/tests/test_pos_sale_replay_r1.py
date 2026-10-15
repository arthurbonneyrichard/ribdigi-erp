"""Lost-response replay of a POS sale or quote must not create a second document.

The in-memory test database is used. These tests do not open ribdigi_erp.
"""

from __future__ import annotations

import asyncio

import pyotp
import pytest
from sqlalchemy import func, select

from app import models as m
from tests.conftest import auth_headers
from tests.test_offline_pos_grants import (
    _authorize,
    _cashier,
    _count_sales,
    _open_shift,
    _sale,
    _store_with_stock,
    _super,
)


async def _cashier_headers(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _open(ac, headers, admin) -> str:
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=admin,
                json={"actual_cash": 0},
            )
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 0},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()["data"].get("session_id") or opened.json()["data"]["id"]


def _body(session_id: str, product_id: str, crid: str, **extra) -> dict:
    body = {
        "session_id": session_id,
        "client_request_id": crid,
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 10}],
    }
    body.update(extra)
    return body


async def _effects(db_session, sale_id: str) -> dict:
    payments = (
        await db_session.execute(
            select(func.count(m.PosPayment.id)).where(m.PosPayment.sale_id == sale_id)
        )
    ).scalar()
    stock = (
        await db_session.execute(
            select(func.count(m.StockMovement.id)).where(
                m.StockMovement.reference_type == "pos_sale",
                m.StockMovement.reference_id == sale_id,
            )
        )
    ).scalar()
    journals = (
        await db_session.execute(
            select(func.count(m.JournalEntry.id)).where(
                m.JournalEntry.source_type == "pos_sale",
                m.JournalEntry.source_id == sale_id,
            )
        )
    ).scalar()
    return {"payments": int(payments or 0), "stock": int(stock or 0), "journals": int(journals or 0)}


@pytest.mark.asyncio
async def test_lost_response_replay_posts_one_sale(client, db_session):
    ac, seed = client
    headers = await _cashier_headers(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    await db_session.commit()
    session_id = await _open(ac, headers, admin)
    crid = "cr-replay-lost-0001"
    body = _body(session_id, product.id, crid)
    first = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert first.status_code == 200, first.text
    sale_id = first.json()["data"]["id"]
    assert first.json()["data"].get("idempotent_replay") is not True

    second = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == sale_id
    assert second.json()["data"]["idempotent_replay"] is True

    count = (
        await db_session.execute(
            select(func.count(m.Transaction.id)).where(m.Transaction.client_request_id == crid)
        )
    ).scalar()
    assert int(count or 0) == 1
    effects = await _effects(db_session, sale_id)
    assert effects == {"payments": 1, "stock": 1, "journals": 1}


@pytest.mark.asyncio
async def test_reused_sale_id_with_different_contents_is_rejected(client, db_session):
    ac, seed = client
    headers = await _cashier_headers(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    await db_session.commit()
    session_id = await _open(ac, headers, admin)
    crid = "cr-replay-diff-0001"
    body = _body(session_id, product.id, crid)
    first = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert first.status_code == 200, first.text
    sale_id = first.json()["data"]["id"]
    changed = _body(session_id, product.id, crid)
    changed["items"] = [{"product_id": product.id, "quantity": 2, "unit_price": 10}]
    rejected = await ac.post("/api/v1/pos/sales", headers=headers, json=changed)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "CLIENT_REQUEST_REUSED"
    count = (
        await db_session.execute(
            select(func.count(m.Transaction.id)).where(m.Transaction.client_request_id == crid)
        )
    ).scalar()
    assert int(count or 0) == 1
    assert (await _effects(db_session, sale_id))["stock"] == 1


@pytest.mark.asyncio
async def test_concurrent_identical_retries_leave_one_sale(client, db_session, monkeypatch):
    """The unique-constraint path still compares contents when the first read misses."""
    import app.api as api_mod

    ac, seed = client
    headers = await _cashier_headers(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    await db_session.commit()
    session_id = await _open(ac, headers, admin)
    crid = "cr-replay-race-0001"
    body = _body(session_id, product.id, crid)
    first = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert first.status_code == 200, first.text
    sale_id = first.json()["data"]["id"]

    calls = {"n": 0}
    real = api_mod._find_existing_pos_sale

    async def miss_once(db, tenant_id, client_request_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real(db, tenant_id, client_request_id)

    monkeypatch.setattr(api_mod, "_find_existing_pos_sale", miss_once)
    replay = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["id"] == sale_id
    assert replay.json()["data"]["idempotent_replay"] is True
    assert calls["n"] >= 2

    calls["n"] = 0

    async def miss_once_again(db, tenant_id, client_request_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real(db, tenant_id, client_request_id)

    monkeypatch.setattr(api_mod, "_find_existing_pos_sale", miss_once_again)
    changed = _body(session_id, product.id, crid, payment_method="card")
    rejected = await ac.post("/api/v1/pos/sales", headers=headers, json=changed)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "CLIENT_REQUEST_REUSED"
    count = (
        await db_session.execute(
            select(func.count(m.Transaction.id)).where(m.Transaction.client_request_id == crid)
        )
    ).scalar()
    assert int(count or 0) == 1
    effects = await _effects(db_session, sale_id)
    assert effects == {"payments": 1, "stock": 1, "journals": 1}


@pytest.mark.asyncio
async def test_parallel_identical_posts_leave_one_sale(client, db_session):
    ac, seed = client
    headers = await _cashier_headers(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    await db_session.commit()
    session_id = await _open(ac, headers, admin)
    crid = "cr-replay-parallel01"
    body = _body(session_id, product.id, crid)
    created = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert created.status_code == 200, created.text
    sale_id = created.json()["data"]["id"]
    # Two retries at once, after the sale is committed. Overlapping inserts share
    # this fixture's one SQLite connection; that lost-insert race is covered by
    # test_concurrent_identical_retries_leave_one_sale.
    first, second = await asyncio.gather(
        ac.post("/api/v1/pos/sales", headers=headers, json=body),
        ac.post("/api/v1/pos/sales", headers=headers, json=body),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["idempotent_replay"] is True
    assert second.json()["data"]["idempotent_replay"] is True
    assert first.json()["data"]["id"] == second.json()["data"]["id"] == sale_id
    count = (
        await db_session.execute(
            select(func.count(m.Transaction.id)).where(m.Transaction.client_request_id == crid)
        )
    ).scalar()
    assert int(count or 0) == 1
    effects = await _effects(db_session, first.json()["data"]["id"])
    assert effects == {"payments": 1, "stock": 1, "journals": 1}


@pytest.mark.asyncio
async def test_offline_sale_replay_and_quote_mismatch(client, db_session, monkeypatch):
    import app.api as api_mod

    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10, code="RPLY1")
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    grant = await _authorize(ac, cashier, "dev-replay-0001", store_id)
    crid = "cr-offline-replay01"
    body = _sale(session_id, crid, "dev-replay-0001", grant["grant_id"], seed["p1"].id)
    first = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
    assert first.status_code == 200, first.text
    sale_id = first.json()["data"]["id"]
    replay = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["idempotent_replay"] is True
    changed = _sale(session_id, crid, "dev-replay-0001", grant["grant_id"], seed["p1"].id, qty=2)
    rejected = await ac.post("/api/v1/pos/sales", headers=cashier, json=changed)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "CLIENT_REQUEST_REUSED"
    assert await _count_sales(db_session, crid) == 1
    assert (await _effects(db_session, sale_id))["stock"] == 1

    quote_body = {
        "customer_id": seed["party1"].id,
        "client_request_id": "cr-quote-replay-01",
        "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 10}],
    }
    created = await ac.post("/api/v1/sales/quotations", headers=admin, json=quote_body)
    assert created.status_code == 200, created.text
    quote_id = created.json()["data"]["id"]
    again = await ac.post("/api/v1/sales/quotations", headers=admin, json=quote_body)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["id"] == quote_id
    assert again.json()["data"]["idempotent_replay"] is True
    mismatched = {
        "customer_id": seed["party1"].id,
        "client_request_id": "cr-quote-replay-01",
        "items": [{"product_id": seed["p1"].id, "quantity": 4, "unit_price": 10}],
    }
    quote_rejected = await ac.post("/api/v1/sales/quotations", headers=admin, json=mismatched)
    assert quote_rejected.status_code == 409, quote_rejected.text
    assert quote_rejected.json()["detail"]["code"] == "CLIENT_REQUEST_REUSED"
    quote_count = (
        await db_session.execute(
            select(func.count(m.SalesQuotation.id)).where(
                m.SalesQuotation.client_request_id == "cr-quote-replay-01"
            )
        )
    ).scalar()
    assert int(quote_count or 0) == 1

    calls = {"n": 0}
    real = api_mod._find_existing_quote

    async def miss_once(db, tenant_id, client_request_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real(db, tenant_id, client_request_id)

    monkeypatch.setattr(api_mod, "_find_existing_quote", miss_once)
    raced = await ac.post("/api/v1/sales/quotations", headers=admin, json=quote_body)
    assert raced.status_code == 200, raced.text
    assert raced.json()["data"]["id"] == quote_id
    quote_count = (
        await db_session.execute(
            select(func.count(m.SalesQuotation.id)).where(
                m.SalesQuotation.client_request_id == "cr-quote-replay-01"
            )
        )
    ).scalar()
    assert int(quote_count or 0) == 1
