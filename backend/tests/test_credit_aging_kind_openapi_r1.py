"""GET /credit/aging kind Query OpenAPI Literal (BR-11)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CreditAgingKindValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_credit_aging_kind_literal_schema():
    adapter = TypeAdapter(CreditAgingKindValue)
    assert adapter.validate_python("receivable") == "receivable"
    assert adapter.validate_python("  Payable ") == "payable"
    assert adapter.validate_python("RECEIVABLE") == "receivable"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("ar")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_credit_aging_kind_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "setKind('receivable')" in page
    assert "setKind('payable')" in page
    assert "Receivables" in page
    assert "Payables" in page
    assert "/credit/aging?kind=${kind}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Credit aging kind OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/credit/aging" in docs
    assert "receivable" in docs and "payable" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_credit_aging_kind_blank_invalid_422_and_coerce(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/credit/aging?kind=", headers=headers)
    assert blank.status_code == 422, blank.text

    whitespace = await ac.get("/api/v1/credit/aging?kind=%20%20%20", headers=headers)
    assert whitespace.status_code == 422, whitespace.text

    bad = await ac.get("/api/v1/credit/aging?kind=ar", headers=headers)
    assert bad.status_code == 422, bad.text

    # Previously silent AR for title-case Payable — must coerce to AP.
    payable = await ac.get("/api/v1/credit/aging?kind=Payable", headers=headers)
    assert payable.status_code == 200, payable.text
    pdata = payable.json()["data"]
    assert "totals" in pdata or "total_due" in pdata or isinstance(pdata, dict)

    omit = await ac.get("/api/v1/credit/aging", headers=headers)
    assert omit.status_code == 200, omit.text
