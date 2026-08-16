"""GET /accounting/cheques direction + status Query OpenAPI Literals (BR-10.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.cheques import DIRECTIONS, STATUSES
from app.schemas import ChequeDirectionValue, ChequeStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_cheque_list_literal_covers_valid():
    dlit = ChequeDirectionValue.__args__[0]
    slit = ChequeStatusValue.__args__[0]
    assert set(dlit.__args__) == set(DIRECTIONS)
    assert set(slit.__args__) == set(STATUSES)


def test_cheque_list_literal_schema():
    direction = TypeAdapter(ChequeDirectionValue)
    assert direction.validate_python("received") == "received"
    assert direction.validate_python("  Issued ") == "issued"
    with pytest.raises(ValidationError):
        direction.validate_python("")
    with pytest.raises(ValidationError):
        direction.validate_python("inbound")

    status = TypeAdapter(ChequeStatusValue)
    assert status.validate_python("Pending") == "pending"
    assert status.validate_python("  CLEARED ") == "cleared"
    with pytest.raises(ValidationError):
        status.validate_python("")
    with pytest.raises(ValidationError):
        status.validate_python("   ")
    with pytest.raises(ValidationError):
        status.validate_python("open")


def test_cheque_list_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'value="received"' in page
    assert 'value="issued"' in page
    assert 'value="pending"' in page
    assert 'value="deposited"' in page
    assert 'value="cleared"' in page
    assert 'value="bounced"' in page
    assert 'value="cancelled"' in page
    assert "Cheque direction filter" in page
    assert "Cheque status filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Cheque list query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/accounting/cheques" in docs
    assert "direction" in docs and "422" in docs


@pytest.mark.asyncio
async def test_cheque_list_query_blank_invalid_422_and_ok(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank_dir = await ac.get("/api/v1/accounting/cheques?direction=", headers=headers)
    assert blank_dir.status_code == 422, blank_dir.text

    bad_dir = await ac.get("/api/v1/accounting/cheques?direction=inbound", headers=headers)
    assert bad_dir.status_code == 422, bad_dir.text

    blank_st = await ac.get("/api/v1/accounting/cheques?status=", headers=headers)
    assert blank_st.status_code == 422, blank_st.text

    bad_st = await ac.get("/api/v1/accounting/cheques?status=open", headers=headers)
    assert bad_st.status_code == 422, bad_st.text

    ok = await ac.get(
        "/api/v1/accounting/cheques?direction=Received&status=Pending",
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert isinstance(ok.json()["data"], list)

    omit = await ac.get("/api/v1/accounting/cheques", headers=headers)
    assert omit.status_code == 200, omit.text
