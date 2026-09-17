"""GET /accounting/transfers kind Query OpenAPI + Cash & Bank filter (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CashTransferKindFilterValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_cash_transfer_kind_literal_schema():
    adapter = TypeAdapter(CashTransferKindFilterValue)
    assert adapter.validate_python("transfer") == "transfer"
    assert adapter.validate_python("  Deposit ") == "deposit"
    assert adapter.validate_python("WITHDRAWAL") == "withdrawal"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("payment")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_cash_transfer_kind_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "xferKindManageFilter" in page
    assert "managedTransfers" in page
    assert 'aria-label="Cash transfer kind filter"' in page
    assert 'value="transfer"' in page
    assert 'value="deposit"' in page
    assert 'value="withdrawal"' in page
    assert "No transfers for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Cash transfer kind Query OpenAPI" in agents
    assert "xferKindManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "xferKindManageFilter" in docs
    assert "GET /accounting/transfers" in docs
    assert "deposit" in docs and "withdrawal" in docs


@pytest.mark.asyncio
async def test_cash_transfer_kind_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/accounting/transfers?kind=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/accounting/transfers?kind=payment", headers=headers)
    assert bad.status_code == 422, bad.text

    liquid = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert liquid.status_code == 200, liquid.text
    accounts = liquid.json()["data"] or []
    assert len(accounts) >= 1
    dest = accounts[0]["id"]
    src = accounts[1]["id"] if len(accounts) > 1 else accounts[0]["id"]

    marker = "xferKindManageFilter hello-world"
    dep = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={"kind": "deposit", "to_account_id": dest, "amount": 11.5, "notes": marker},
    )
    assert dep.status_code in {200, 201}, dep.text

    if src != dest:
        xfer = await ac.post(
            "/api/v1/accounting/transfers",
            headers=headers,
            json={
                "kind": "transfer",
                "from_account_id": src,
                "to_account_id": dest,
                "amount": 3.25,
                "notes": marker,
            },
        )
        assert xfer.status_code in {200, 201}, xfer.text

    all_rows = await ac.get("/api/v1/accounting/transfers", headers=headers)
    assert all_rows.status_code == 200, all_rows.text
    data = all_rows.json()["data"] or []
    marked = [r for r in data if (r.get("notes") or "") == marker]
    assert any(r.get("kind") == "deposit" for r in marked)

    deposits = await ac.get("/api/v1/accounting/transfers?kind=deposit", headers=headers)
    assert deposits.status_code == 200, deposits.text
    dep_rows = deposits.json()["data"] or []
    assert dep_rows
    assert all(r.get("kind") == "deposit" for r in dep_rows)
    assert any((r.get("notes") or "") == marker for r in dep_rows)

    transfers_only = await ac.get("/api/v1/accounting/transfers?kind=transfer", headers=headers)
    assert transfers_only.status_code == 200, transfers_only.text
    xfer_rows = transfers_only.json()["data"] or []
    assert all(r.get("kind") == "transfer" for r in xfer_rows)
