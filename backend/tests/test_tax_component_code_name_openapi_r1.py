"""TaxComponent.code / name OpenAPI honesty (BR-12.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    TaxCalculateRequest,
    TaxComponent,
    TaxComponentCodeValue,
    TaxComponentNameValue,
    TaxCreate,
    TaxUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(TaxComponentCodeValue)
_name = TypeAdapter(TaxComponentNameValue)


def test_tax_component_code_name_schema():
    assert _code.validate_python("  cgst  ") == "cgst"
    assert _name.validate_python("  CGST leg  ") == "CGST leg"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 41):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 81):
        with pytest.raises(ValidationError):
            _name.validate_python(bad)

    omit = TaxComponent.model_validate({"rate": 9})
    assert omit.code is None
    assert omit.name is None

    ok = TaxComponent.model_validate(
        {"rate": 9, "code": "  cgst  ", "name": "  Central GST  ", "basis": "net"}
    )
    assert ok.code == "cgst"
    assert ok.name == "Central GST"

    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": 9, "code": ""})
    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": 9, "code": "!!!"})
    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": 9, "name": "http://evil"})
    with pytest.raises(ValidationError):
        TaxComponent.model_validate({"rate": 9, "name": "  "})

    created = TaxCreate.model_validate(
        {
            "name": "GST Split",
            "rate": 18,
            "components": [
                {"code": "  cgst  ", "name": "  CGST  ", "rate": 9},
                {"rate": 9},
            ],
        }
    )
    assert created.components is not None
    assert created.components[0].code == "cgst"
    assert created.components[0].name == "CGST"
    assert created.components[1].code is None

    with pytest.raises(ValidationError):
        TaxCreate.model_validate(
            {
                "name": "Bad",
                "rate": 18,
                "components": [{"rate": 9, "code": "!!!"}],
            }
        )
    with pytest.raises(ValidationError):
        TaxUpdate.model_validate({"components": [{"rate": 1, "name": ""}]})
    with pytest.raises(ValidationError):
        TaxCalculateRequest.model_validate(
            {"amount": 100, "components": [{"rate": 5, "code": "http://x"}]}
        )


def test_tax_component_code_name_ui_and_docs():
    page = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax rate components JSON"' in page
    assert "next.code = code || null" in page
    assert "next.name = label || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tax component code/name OpenAPI" in agents
    assert "TaxComponentCodeValue" in agents
    assert "TaxComponentNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TaxComponentCodeValue" in docs
    assert "TaxComponentNameValue" in docs
    assert "Tax rate components JSON" in docs


@pytest.mark.asyncio
async def test_tax_component_code_name_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:6]
    name = f"Comp Code Honest {suffix}"

    for bad in ("", "!!!", "http://evil"):
        blank_code = await ac.post(
            "/api/v1/tax/rates",
            headers=headers,
            json={
                "name": f"{name}-c",
                "rate": 18,
                "tax_type": "gst",
                "components": [{"code": bad, "rate": 9, "basis": "net"}],
            },
        )
        assert blank_code.status_code == 422, (bad, blank_code.text)

        blank_name = await ac.post(
            "/api/v1/tax/rates",
            headers=headers,
            json={
                "name": f"{name}-n",
                "rate": 18,
                "tax_type": "gst",
                "components": [{"name": bad, "rate": 9, "basis": "net"}],
            },
        )
        assert blank_name.status_code == 422, (bad, blank_name.text)

    omit = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": f"{name}-omit",
            "rate": 9,
            "tax_type": "gst",
            "components": [{"rate": 9, "basis": "net"}],
        },
    )
    assert omit.status_code == 200, omit.text
    omit_comps = omit.json()["data"]["components"]
    assert omit_comps and omit_comps[0]["code"]

    ok = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": f"{name}-ok",
            "rate": 18,
            "tax_type": "gst",
            "components": [
                {"code": "  cgst  ", "name": "  Central GST  ", "rate": 9, "basis": "net"},
                {"code": "sgst", "rate": 9, "basis": "net"},
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    comps = ok.json()["data"]["components"]
    assert comps[0]["code"] == "cgst"
    assert comps[0]["name"] == "Central GST"
    assert comps[1]["code"] == "sgst"

    rid = ok.json()["data"]["id"]
    bad_patch = await ac.patch(
        f"/api/v1/tax/rates/{rid}",
        headers=headers,
        json={"components": [{"rate": 5, "code": "!!!"}]},
    )
    assert bad_patch.status_code == 422, bad_patch.text

    good_patch = await ac.patch(
        f"/api/v1/tax/rates/{rid}",
        headers=headers,
        json={
            "components": [
                {"code": "  vat1  ", "name": "  VAT leg  ", "rate": 10, "basis": "net"}
            ]
        },
    )
    assert good_patch.status_code == 200, good_patch.text
    patched = good_patch.json()["data"]["components"]
    assert patched[0]["code"] == "vat1"
    assert patched[0]["name"] == "VAT leg"
