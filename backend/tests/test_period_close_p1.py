"""Period close / books lock (BR-10.2)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_close_blocks_post_and_unpost_then_reopen(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    status = await ac.get("/api/v1/accounting/period", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["data"]["books_closed_through"] is None

    yesterday = datetime.utcnow().date() - timedelta(days=1)
    yesterday_s = yesterday.isoformat()

    # Journal dated yesterday while books still open
    prior = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Prior day entry",
            "entry_date": yesterday_s,
            "lines": [
                {"account_code": "6000", "debit": 7, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 7},
            ],
        },
    )
    assert prior.status_code == 200, prior.text
    prior_id = prior.json()["data"]["id"]

    close = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": yesterday_s},
    )
    assert close.status_code == 200, close.text
    assert close.json()["data"]["books_closed_through"] == yesterday_s

    # Backdated post into closed period → 400
    blocked = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Closed period entry",
            "entry_date": yesterday_s,
            "lines": [
                {"account_code": "6000", "debit": 10, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 10},
            ],
        },
    )
    assert blocked.status_code == 400
    assert "closed" in blocked.json()["detail"].lower()

    # Open-period post (today) still works
    open_post = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Open period entry",
            "lines": [
                {"account_code": "6000", "debit": 11, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 11},
            ],
        },
    )
    assert open_post.status_code == 200, open_post.text
    open_id = open_post.json()["data"]["id"]
    assert open_post.json()["data"]["can_unpost"] is True

    unpost_closed = await ac.post(
        f"/api/v1/accounting/journal-entries/{prior_id}/unpost", headers=headers
    )
    assert unpost_closed.status_code == 400
    assert "closed" in unpost_closed.json()["detail"].lower()

    listed = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert listed.status_code == 200
    row = next(j for j in listed.json()["data"] if j["id"] == prior_id)
    assert row["can_unpost"] is False

    # Cannot close into the future
    future = (datetime.utcnow().date() + timedelta(days=3)).isoformat()
    bad_future = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": future},
    )
    assert bad_future.status_code == 400

    # Cannot close earlier without reopen
    earlier = (datetime.utcnow().date() - timedelta(days=10)).isoformat()
    bad_earlier = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": earlier},
    )
    assert bad_earlier.status_code == 400

    reopen = await ac.post(
        "/api/v1/accounting/period/reopen",
        headers=headers,
        json={"through_date": None},
    )
    assert reopen.status_code == 200, reopen.text
    assert reopen.json()["data"]["books_closed_through"] is None

    unpost_ok = await ac.post(
        f"/api/v1/accounting/journal-entries/{prior_id}/unpost", headers=headers
    )
    assert unpost_ok.status_code == 200, unpost_ok.text

    unpost_open = await ac.post(
        f"/api/v1/accounting/journal-entries/{open_id}/unpost", headers=headers
    )
    assert unpost_open.status_code == 200, unpost_open.text


@pytest.mark.asyncio
async def test_period_requires_accounting_permission(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/accounting/period", headers=headers)
    assert r.status_code == 403
    c = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": datetime.utcnow().date().isoformat()},
    )
    assert c.status_code == 403
