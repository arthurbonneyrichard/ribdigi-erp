"""Stage 22 T1: Tax configuration fidelity (BR-12.1 remaining ACs)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_tax_types_pricing_modes_and_compound(client):
    """BR-12.1: tax types, inclusive/exclusive pricing, compound tax-on-tax."""
    ac, seed = client
    headers = await _super(ac, seed)

    # --- Tax types (VAT, GST, Sales Tax) ---
    types_payload = [
        {"name": "T1 VAT Standard", "rate": 15, "tax_type": "vat", "pricing_mode": "exclusive"},
        {"name": "T1 GST", "rate": 18, "tax_type": "gst", "pricing_mode": "exclusive"},
        {
            "name": "T1 Sales Tax Inclusive",
            "rate": 10,
            "tax_type": "sales_tax",
            "pricing_mode": "inclusive",
        },
    ]
    created_ids: dict[str, str] = {}
    for body in types_payload:
        resp = await ac.post("/api/v1/tax/rates", headers=headers, json=body)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["tax_type"] == body["tax_type"]
        assert data["pricing_mode"] == body["pricing_mode"]
        assert float(data["rate"]) == pytest.approx(body["rate"])
        created_ids[body["tax_type"]] = data["id"]

    listed = await ac.get("/api/v1/tax/rates", headers=headers)
    assert listed.status_code == 200, listed.text
    by_type = {r["tax_type"] for r in listed.json()["data"]}
    assert {"vat", "gst", "sales_tax"} <= by_type

    # --- Inclusive / exclusive pricing via calculate ---
    excl = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={"amount": 100, "rate": 15, "pricing_mode": "exclusive"},
    )
    assert excl.status_code == 200, excl.text
    edata = excl.json()["data"]
    assert edata["pricing_mode"] == "exclusive"
    assert float(edata["net"]) == pytest.approx(100)
    assert float(edata["tax"]) == pytest.approx(15)
    assert float(edata["gross"]) == pytest.approx(115)

    incl = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={"amount": 115, "rate": 15, "pricing_mode": "inclusive"},
    )
    assert incl.status_code == 200, incl.text
    idata = incl.json()["data"]
    assert idata["pricing_mode"] == "inclusive"
    assert float(idata["gross"]) == pytest.approx(115)
    assert float(idata["tax"]) == pytest.approx(15)
    assert float(idata["net"]) == pytest.approx(100)

    # Rate-linked calculate uses stored pricing_mode
    via_rate = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={"amount": 110, "tax_rate_id": created_ids["sales_tax"]},
    )
    assert via_rate.status_code == 200, via_rate.text
    assert via_rate.json()["data"]["pricing_mode"] == "inclusive"
    assert float(via_rate.json()["data"]["gross"]) == pytest.approx(110)

    # Patch pricing mode
    patched = await ac.patch(
        f"/api/v1/tax/rates/{created_ids['gst']}",
        headers=headers,
        json={"pricing_mode": "inclusive"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["pricing_mode"] == "inclusive"

    # --- Compound tax (tax on tax) ---
    compound = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "T1 Compound Cascade",
            "rate": 0,
            "tax_type": "gst",
            "pricing_mode": "exclusive",
            "components": [
                {"code": "base", "name": "Base VAT", "rate": 10, "basis": "net"},
                {"code": "surcharge", "name": "Surcharge", "rate": 5, "basis": "compound"},
            ],
        },
    )
    assert compound.status_code == 200, compound.text
    cdata = compound.json()["data"]
    compound_id = cdata["id"]
    assert cdata["components"]
    assert len(cdata["components"]) == 2
    assert float(cdata["rate"]) == pytest.approx(10)  # effective from net legs

    calc_comp = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={"amount": 100, "tax_rate_id": compound_id},
    )
    assert calc_comp.status_code == 200, calc_comp.text
    detail = calc_comp.json()["data"]
    assert float(detail["net"]) == pytest.approx(100)
    assert float(detail["tax"]) == pytest.approx(15.5)  # 10 + 5% of 110
    assert float(detail["gross"]) == pytest.approx(115.5)
    comps = detail["components"]
    assert len(comps) == 2
    assert float(comps[0]["amount"]) == pytest.approx(10)
    assert float(comps[1]["amount"]) == pytest.approx(5.5)


def test_br_12_1_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s121 = br.split("#### BR-12.1 Tax Configuration")[1].split("#### BR-12.2")[0]
    assert "[x] Add tax types" in s121
    assert "[x] Configure tax rates" in s121
    assert "[x] Set tax applicability (inclusive/exclusive pricing)" in s121
    assert "[x] Product-category-specific tax rules" in s121
    assert "[x] Compound tax" in s121
    assert "Stage 22 T1" in s121
    assert "test_tax_config_fidelity_t1.py" in s121
    assert "Stage 14 T1" in s121 or "Stage 10 T1" in s121

    plan = (ROOT / "docs" / "STAGE_22_PLAN.md").read_text(encoding="utf-8")
    t1_line = [ln for ln in plan.splitlines() if "| **T1**" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_tax_config_fidelity_t1.py" in plan
