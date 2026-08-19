"""ExpenseCreate / ExpenseUpdate / AI draft reference OpenAPI honesty (BR-9.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AiDocumentExpenseCreate, ExpenseCreate, ExpenseUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expense_reference_schema():
    omit = ExpenseCreate.model_validate({"amount": 10})
    assert omit.reference is None
    ok = ExpenseCreate.model_validate({"amount": 10, "reference": "  VENDOR-INV-42  "})
    assert ok.reference == "VENDOR-INV-42"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ExpenseCreate.model_validate({"amount": 10, "reference": bad})

    patch_omit = ExpenseUpdate.model_validate({})
    assert patch_omit.reference is None
    patch_ok = ExpenseUpdate.model_validate({"reference": " REF-9 "})
    assert patch_ok.reference == "REF-9"
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"reference": "!!!"})
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"reference": "  "})

    ai_ok = AiDocumentExpenseCreate.model_validate({"amount": 5, "reference": "  OCR-1  "})
    assert ai_ok.reference == "OCR-1"
    with pytest.raises(ValidationError):
        AiDocumentExpenseCreate.model_validate({"amount": 5, "reference": "http://evil"})


def test_expense_reference_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense reference"' in page
    assert "reference.trim() || null" in page
    assert 'aria-label="Edit reference"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expense reference OpenAPI" in agents
    assert "ExpenseReferenceValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseReferenceValue" in docs
    assert "Expense reference" in docs


@pytest.mark.asyncio
async def test_expense_reference_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    assert cats.status_code == 200, cats.text
    cat_rows = cats.json().get("data") or []
    category = next((c for c in cat_rows if c.get("code") == "MISC"), cat_rows[0])
    category_id = category["id"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/expenses",
            headers=admin,
            json={
                "amount": 12.5,
                "category_id": category_id,
                "reference": bad,
                "payment_method": "cash",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={"amount": 12.5, "category_id": category_id, "payment_method": "cash"},
    )
    assert omit.status_code == 200, omit.text
    # auto EXP-YYYY-NNNN when reference omitted
    auto_ref = omit.json()["data"].get("reference") or ""
    assert auto_ref.startswith("EXP-"), auto_ref

    ok = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "amount": 5000,
            "category_id": category_id,
            "reference": f"  TIP149-{suffix}  ",
            "description": f"Tip149 desc {suffix}",
            "payment_method": "cash",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reference"] == f"TIP149-{suffix}"
    eid = ok.json()["data"]["id"]
    if ok.json()["data"].get("status") == "approved":
        pending = await ac.post(
            "/api/v1/expenses",
            headers=admin,
            json={
                "amount": 9000,
                "category_id": category_id,
                "reference": f"  TIP149P-{suffix}  ",
                "description": f"Tip149 pending {suffix}",
                "payment_method": "cash",
            },
        )
        assert pending.status_code == 200, pending.text
        eid = pending.json()["data"]["id"]
        assert pending.json()["data"]["reference"] == f"TIP149P-{suffix}"

    keep = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=admin,
        json={"description": f"Tip149 keep {suffix}"},
    )
    assert keep.status_code == 200, keep.text
    assert "TIP149" in (keep.json()["data"].get("reference") or "")

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/expenses/{eid}",
            headers=admin,
            json={"reference": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=admin,
        json={"reference": f"  TIP149R-{suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["reference"] == f"TIP149R-{suffix}"
