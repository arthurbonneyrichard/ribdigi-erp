"""TaxCreate / TaxUpdate.name OpenAPI honesty (BR-12.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TaxCreate, TaxUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tax_rate_name_schema():
    ok = TaxCreate.model_validate({"name": "  Standard VAT  ", "rate": 15})
    assert ok.name == "Standard VAT"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            TaxCreate.model_validate({"name": bad, "rate": 15})

    patch_omit = TaxUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = TaxUpdate.model_validate({"name": " Renamed Rate "})
    assert patch_ok.name == "Renamed Rate"
    with pytest.raises(ValidationError):
        TaxUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        TaxUpdate.model_validate({"name": "  "})


def test_tax_rate_name_ui_and_docs():
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax rate name"' in tax
    assert "name.trim()" in tax
    assert 'aria-label="Add tax rate"' in tax
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tax rate name OpenAPI" in agents
    assert "TaxRateNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TaxRateNameValue" in docs
    assert "Tax rate name" in docs


@pytest.mark.asyncio
async def test_tax_rate_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/tax/rates",
            headers=headers,
            json={"name": bad, "rate": 12.5},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": f"  Tip135 Rate {suffix}  ", "rate": 12.5, "tax_type": "vat"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip135 Rate {suffix}"
    rate_id = ok.json()["data"]["id"]

    omit = await ac.patch(
        f"/api/v1/tax/rates/{rate_id}",
        headers=headers,
        json={"rate": 13.0},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["name"] == f"Tip135 Rate {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/tax/rates/{rate_id}",
            headers=headers,
            json={"name": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/tax/rates/{rate_id}",
        headers=headers,
        json={"name": f"  Tip135 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == f"Tip135 Renamed {suffix}"
