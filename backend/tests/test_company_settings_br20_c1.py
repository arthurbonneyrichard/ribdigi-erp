"""Stage 19 C1: Company/settings BR-20 fidelity sync."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes"


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_company_legal_contact_tax_and_logo(client, tmp_path, monkeypatch):
    """BR-20.1: legal/address/contact/tax ID + logo upload."""
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, _seed = client
    headers = await _admin(ac)

    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "legal_name": "Alpha Retail Limited",
            "address": "12 Independence Ave, Accra",
            "phone": "+233201111111",
            "email": "ops@alpha.example.com",
            "contact_person_name": "Ada Admin",
            "contact_person_email": "ada@alpha.example.com",
            "contact_person_phone": "+233202222222",
            "tax_registration_number": "C0001234567",
            "tax_jurisdiction": "GH",
        },
    )
    assert profile.status_code == 200, profile.text
    data = profile.json()["data"]
    assert data["legal_name"] == "Alpha Retail Limited"
    assert data["address"] == "12 Independence Ave, Accra"
    assert data["phone"] == "+233201111111"
    assert data["email"] == "ops@alpha.example.com"
    assert data["contact_person_name"] == "Ada Admin"
    assert data["tax_registration_number"] == "C0001234567"

    up = await ac.post(
        "/api/v1/tenants/me/logo",
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["data"]["has_logo"] is True

    got = await ac.get("/api/v1/tenants/me/logo", headers=headers)
    assert got.status_code == 200
    assert got.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_formatting_date_number_time(client):
    """BR-20.2: regional date / number / time formats."""
    ac, _seed = client
    headers = await _admin(ac)

    for date_fmt in ("DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"):
        r = await ac.patch(
            "/api/v1/tenants/me",
            headers=headers,
            json={"date_format": date_fmt},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["date_format"] == date_fmt

    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "date_format": "YYYY-MM-DD",
            "number_format": "1.234,56",
            "time_format": "12h",
        },
    )
    assert profile.status_code == 200, profile.text
    data = profile.json()["data"]
    assert data["date_format"] == "YYYY-MM-DD"
    assert data["number_format"] == "1.234,56"
    assert data["time_format"] == "12h"

    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"date_format": "YY/MM/DD"},
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_smtp_settings_tls_and_test_email(client, monkeypatch):
    """BR-20.3: SMTP host/port/user/password, TLS, from, test send."""
    from app import emailer

    sent: list[tuple] = []

    def fake_smtp_send(msg, smtp_config=None):
        sent.append((msg, smtp_config))

    monkeypatch.setattr(emailer, "_smtp_send_sync", fake_smtp_send)
    monkeypatch.setattr(emailer.settings, "EMAIL_ENABLED", True)

    ac, _seed = client
    headers = await _admin(ac)

    saved = await ac.patch(
        "/api/v1/settings/email",
        headers=headers,
        json={
            "smtp_enabled": True,
            "smtp_host": "smtp.c1.example.com",
            "smtp_port": 587,
            "smtp_username": "mailer-c1",
            "smtp_password": "SmtpSecret1!",
            "smtp_from_email": "noreply@alpha.example.com",
            "smtp_from_name": "Alpha C1",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["source"] == "tenant"
    assert data["host"] == "smtp.c1.example.com"
    assert data["from_email"] == "noreply@alpha.example.com"
    assert data["from_name"] == "Alpha C1"
    assert data["has_password"] is True
    assert "smtp_password" not in data
    assert "password" not in data or data.get("password") in (None, "")
    assert data["use_tls"] is True
    assert data["use_ssl"] is False

    status = await ac.get("/api/v1/settings/email", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["data"]["tenant_override_enabled"] is True

    test = await ac.post(
        "/api/v1/settings/email/test",
        headers=headers,
        json={"to": "admin@alpha.example.com"},
    )
    assert test.status_code == 200, test.text
    body = test.json()["data"]
    assert body.get("sent") is True
    assert body.get("mode") == "smtp"
    assert sent, "SMTP transport should be invoked for tenant override test email"


@pytest.mark.asyncio
async def test_numbering_and_print_templates(client):
    """BR-20.4: document numbering + invoice/receipt templates + header/footer."""
    ac, _seed = client
    headers = await _admin(ac)

    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "document_numbering": {
                "sales_invoice": {"prefix": "INV", "include_year": True, "pad": 4, "next_number": 1},
                "purchase_order": {"prefix": "PO", "include_year": True, "pad": 4, "next_number": 10},
                "goods_receipt": {"prefix": "GRN", "include_year": True, "pad": 4, "next_number": 5},
                "sales_quotation": {"prefix": "QT", "include_year": True, "pad": 4, "next_number": 3},
            },
            "invoice_print_template": "a4",
            "receipt_print_template": "thermal_80",
            "document_header": "Alpha Retail — GST registered",
            "document_footer": "Thank you for your business",
        },
    )
    assert profile.status_code == 200, profile.text
    data = profile.json()["data"]
    numbering = data["document_numbering"]
    assert numbering["sales_invoice"]["prefix"] == "INV"
    assert numbering["purchase_order"]["prefix"] == "PO"
    assert numbering["goods_receipt"]["prefix"] == "GRN"
    assert numbering["sales_quotation"]["prefix"] == "QT"
    preview = data["document_numbering_preview"]
    assert "INV-" in preview["sales_invoice"]
    assert "PO-" in preview["purchase_order"]
    assert "GRN-" in preview["goods_receipt"]
    assert "QT-" in preview["sales_quotation"]
    assert data["invoice_print_template"] == "a4"
    assert data["receipt_print_template"] == "thermal_80"
    assert data["document_header"] == "Alpha Retail — GST registered"
    assert data["document_footer"] == "Thank you for your business"

    bad_receipt = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"receipt_print_template": "a4"},
    )
    assert bad_receipt.status_code == 400


def test_br_20_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s201 = br.split("#### BR-20.1 Company Information")[1].split("#### BR-20.2")[0]
    assert "[x] Edit legal name, address, contact, tax ID" in s201
    assert "[x] Upload company logo" in s201
    assert "Stage 19 C1" in s201

    s202 = br.split("#### BR-20.2 Formatting")[1].split("#### BR-20.3")[0]
    assert "[x] Date format selection" in s202
    assert "[x] Number format" in s202
    assert "[x] Time format" in s202
    assert "Stage 19 C1" in s202

    s203 = br.split("#### BR-20.3 Email Settings")[1].split("#### BR-20.4")[0]
    assert "[x] SMTP host, port, username, password" in s203
    assert "[x] TLS/SSL encryption" in s203
    assert "[x] Test email functionality" in s203
    assert "[x] Default sender name and email" in s203
    assert "Stage 19 C1" in s203

    s204 = br.split("#### BR-20.4 Numbering & Templates")[1].split("### 4.21")[0]
    assert "[x] Configure invoice numbering prefix and series" in s204
    assert "[x] Configure PO, GRN, quotation numbering" in s204
    assert "[x] Receipt template selection and customization" in s204
    assert "[x] Invoice template selection and customization" in s204
    assert "[x] Header/footer customization with company branding" in s204
    assert "Stage 19 C1" in s204
    assert "WYSIWYG" in s204 or "deferred" in s204.lower() or "designer" in s204.lower()

    plan = (ROOT / "docs" / "STAGE_19_PLAN.md").read_text(encoding="utf-8")
    c1_line = [ln for ln in plan.splitlines() if "| **C1**" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_company_settings_br20_c1.py" in plan
