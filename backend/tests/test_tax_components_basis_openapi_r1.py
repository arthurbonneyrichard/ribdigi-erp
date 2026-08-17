"""Tax compound components basis OpenAPI honesty (BR-12.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import TaxCalculateRequest, TaxComponent, TaxCreate, TaxUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tax_component_schema():
    ok = TaxComponent.model_validate({"rate": 9, "code": "cgst"})
    assert ok.basis == "net"
    assert ok.code == "cgst"

    compound = TaxComponent.model_validate({"rate": 5, "basis": " Compound ", "name": "Cess"})
    assert compound.basis == "compound"

    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": 9, "basis": ""})
    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": 9, "basis": "gross"})
    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": 9, "basis": "net", "extra": 1})
    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": -1})

    created = TaxCreate.model_validate(
        {
            "name": "GST",
            "rate": 18,
            "components": [{"code": "cgst", "rate": 9}, {"code": "sgst", "rate": 9, "basis": "net"}],
        }
    )
    assert created.components is not None
    assert created.components[0].basis == "net"

    with pytest.raises(ValidationError):
        TaxCreate.model_validate(
            {
                "name": "Bad",
                "rate": 18,
                "components": [{"rate": 9, "basis": ""}],
            }
        )
    with pytest.raises(ValidationError):
        TaxUpdate.model_validate({"components": [{"rate": 1, "basis": "foo"}]})
    with pytest.raises(ValidationError):
        TaxCalculateRequest.model_validate(
            {"amount": 100, "components": [{"rate": 5, "unknown": True}]}
        )


def test_tax_component_ui_and_docs():
    page = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax rate components JSON"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tax components basis OpenAPI" in agents
    assert "TaxComponent" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TaxComponent" in docs
    assert "Tax rate components JSON" in docs


@pytest.mark.asyncio
async def test_tax_components_blank_invalid_basis_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    name = f"Compound Honest {uuid4().hex[:6]}"

    blank = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": name,
            "rate": 18,
            "tax_type": "gst",
            "components": [{"code": "cgst", "rate": 9, "basis": ""}],
        },
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": name,
            "rate": 18,
            "tax_type": "gst",
            "components": [{"code": "cgst", "rate": 9, "basis": "gross"}],
        },
    )
    assert bad.status_code == 422, bad.text

    extra = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": name,
            "rate": 18,
            "tax_type": "gst",
            "components": [{"code": "cgst", "rate": 9, "basis": "net", "foo": 1}],
        },
    )
    assert extra.status_code == 422, extra.text

    ok = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": name,
            "rate": 18,
            "tax_type": "gst",
            "components": [
                {"code": "cgst", "name": "CGST", "rate": 9},
                {"code": "sgst", "name": "SGST", "rate": 9, "basis": "net"},
            ],
            "is_active": True,
            "is_default": False,
        },
    )
    assert ok.status_code == 200, ok.text
    comps = ok.json()["data"].get("components") or []
    assert len(comps) == 2
    assert comps[0]["basis"] == "net"
    rid = ok.json()["data"]["id"]

    calc = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={
            "amount": 100,
            "components": [
                {"code": "cgst", "rate": 9, "basis": "net"},
                {"code": "cess", "rate": 5, "basis": "compound"},
            ],
        },
    )
    assert calc.status_code == 200, calc.text
    assert calc.json()["data"]["tax"] > 0

    deactivate = await ac.patch(
        f"/api/v1/tax/rates/{rid}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivate.status_code == 200, deactivate.text


@pytest.mark.asyncio
async def test_tax_calculate_components_invalid_basis_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={
            "amount": 100,
            "components": [{"rate": 10, "basis": "gross"}],
        },
    )
    assert resp.status_code == 422, resp.text
