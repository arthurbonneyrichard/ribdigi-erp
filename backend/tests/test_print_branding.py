"""Print branding: header/footer, logo embed, template defaults (BR-20.4)."""

from __future__ import annotations

import io

import pyotp
import pytest
from PIL import Image

from app.invoice_print import render_invoice_thermal_text, to_invoice_a4_pdf
from app.print_branding import build_text_pdf, load_logo_jpeg, print_branding_settings
from tests.conftest import auth_headers


def test_build_text_pdf_embeds_jpeg_logo():
    img = Image.new("RGB", (40, 20), color=(20, 80, 160))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg = buf.getvalue()
    pdf = build_text_pdf(
        [("Hello Brand", 14), ("Line two", 10)],
        page_width=200,
        page_height=300,
        margin=20,
        mono=False,
        logo=(jpeg, 40, 20),
        logo_max_pt=40,
    )
    assert pdf.startswith(b"%PDF")
    assert b"/Im1" in pdf
    assert b"/DCTDecode" in pdf
    assert jpeg[:10] in pdf


def test_thermal_text_uses_custom_header_footer():
    text = render_invoice_thermal_text(
        {
            "company_name": "Acme",
            "print_header": "Quality first",
            "print_footer": "Visit again soon",
            "invoice_number": "INV-1",
            "status": "posted",
            "items": [],
            "subtotal": 0,
            "tax": 0,
            "total": 0,
            "paid_amount": 0,
            "balance_due": 0,
        }
    )
    assert "Quality first" in text
    assert "Visit again soon" in text


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_print_settings_and_invoice_branding(client, db_session, seeded, tmp_path, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    monkeypatch.setattr("app.config.settings.MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setattr("app.storage.settings.MEDIA_DIR", str(tmp_path / "media"))

    patched = await ac.patch(
        "/api/v1/settings/print",
        headers=admin,
        json={
            "header_text": "Fresh daily",
            "footer_text": "Pay within 14 days",
            "default_invoice_template": "thermal",
            "default_receipt_paper": "58mm",
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()["data"]
    assert body["header_text"] == "Fresh daily"
    assert body["footer_text"] == "Pay within 14 days"
    assert body["default_invoice_template"] == "thermal"
    assert body["default_receipt_paper"] == "58mm"

    # Upload a tiny logo
    img = Image.new("RGB", (32, 16), color=(200, 40, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    logo = await ac.post(
        "/api/v1/tenants/me/logo",
        headers=admin,
        files={"file": ("logo.png", buf.getvalue(), "image/png")},
    )
    assert logo.status_code == 200, logo.text

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 12}],
        },
    )
    iid = created.json()["data"]["id"]
    await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)

    # Default template from settings → thermal
    printed = await ac.get(f"/api/v1/sales/invoices/{iid}/print?format=json", headers=admin)
    assert printed.status_code == 200, printed.text
    data = printed.json()["data"]
    assert data["template"] == "thermal"
    assert data["paper"] == "58mm"
    assert data["print_header"] == "Fresh daily"
    assert data["print_footer"] == "Pay within 14 days"
    assert data["has_logo"] is True
    assert "Fresh daily" in data["text"]
    assert "Pay within 14 days" in data["text"]
    assert "logo_key" not in data

    a4 = await ac.get(f"/api/v1/sales/invoices/{iid}/print?template=a4&format=pdf", headers=admin)
    assert a4.status_code == 200
    assert a4.content.startswith(b"%PDF")
    assert b"/Im1" in a4.content
    assert b"/DCTDecode" in a4.content
