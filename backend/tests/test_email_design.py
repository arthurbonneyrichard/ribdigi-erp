"""Email design: companies style their own emails; Ribdigi House mail has its own layout."""

from __future__ import annotations

import pytest

from app import email_design, emailer
from tests.conftest import auth_headers, platform_owner_headers


@pytest.fixture(autouse=True)
def _fresh_platform_style():
    email_design.reset_platform_cache_for_tests()
    yield
    email_design.reset_platform_cache_for_tests()


class _Tenant:
    id = "t-design"
    slug = "sunrise"
    company_name = "Sunrise Mart"
    logo_url = None
    print_branding: dict = {}


def test_company_and_house_layouts_differ():
    company = emailer.render_branded_html(body_html="<p>Hi</p>", tenant=_Tenant(), title="Invoice")
    house = emailer.render_branded_html(
        body_html="<p>Hi</p>", company_name="Ribdigi House", tenant=None, title="Verify", allow_platform_logo=True
    )
    assert "ribdigi-email-house" not in company and "background:#003d1f" in company
    assert "ribdigi-email-house" in house
    assert "linear-gradient(90deg,#003d1f,#4ab012)" in house


def test_company_style_changes_colours_header_and_button():
    tenant = _Tenant()
    tenant.print_branding = {
        "email_style": {"theme": "ocean", "header_style": "light", "button_shape": "pill", "signature": "The Sunrise team"}
    }
    body = emailer.email_button("https://example.com/x", "Open")
    out = emailer.render_branded_html(body_html=body, tenant=tenant, title="Hello")
    assert "border-top:6px solid #0b3b66" in out
    assert "background:#0b5cad" in out and "border-radius:999px" in out
    assert "The Sunrise team" in out
    assert "#2f7a0c" not in out


def test_bad_stored_values_fall_back_to_defaults():
    style = email_design.normalize({"theme": "neon", "font": "comic", "show_details": "yes"}, platform=False)
    assert style == email_design.TENANT_DEFAULT


@pytest.mark.asyncio
async def test_company_admin_saves_and_previews_email_design(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    got = await ac.get("/api/v1/settings/email-design", headers=admin)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["style"] == email_design.TENANT_DEFAULT
    assert {t["key"] for t in got.json()["data"]["options"]["themes"]} >= {"forest", "ocean"}

    bad = await ac.patch("/api/v1/settings/email-design", json={"theme": "neon"}, headers=admin)
    assert bad.status_code == 422
    junk = await ac.patch("/api/v1/settings/email-design", json={"signature": "http://spam.example"}, headers=admin)
    assert junk.status_code == 400

    saved = await ac.patch(
        "/api/v1/settings/email-design",
        json={"theme": "plum", "header_style": "minimal", "signature": "The Alpha team"},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["style"]["theme"] == "plum"

    preview = await ac.post(
        "/api/v1/settings/email-design/preview", json={"theme": "royal", "sample": "message"}, headers=admin
    )
    assert preview.status_code == 200, preview.text
    html_body = preview.json()["data"]["html"]
    assert "#5b3fd1" in html_body  # royal button, not yet saved
    assert "The Alpha team" in html_body  # saved signature kept
    assert "ribdigi-email-house" not in html_body

    again = await ac.get("/api/v1/settings/email-design", headers=admin)
    assert again.json()["data"]["style"]["theme"] == "plum"


@pytest.mark.asyncio
async def test_owner_designs_ribdigi_house_mail_and_companies_cannot(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    got = await ac.get("/api/v1/platform/email/design", headers=owner)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["layout"] == "platform"

    saved = await ac.patch(
        "/api/v1/platform/email/design",
        json={"theme": "charcoal", "tagline": "Software for growing businesses", "logo_align": "center"},
        headers=owner,
    )
    assert saved.status_code == 200, saved.text

    emailer.clear_dev_outbox()
    await emailer.send_verification_email(to="new@example.com", token="tok", company_name="Ribdigi House")
    html_body = emailer.get_dev_outbox()[-1]["html_body"]
    assert "ribdigi-email-house" in html_body
    assert "Software for growing businesses" in html_body
    assert "#1f2933" in html_body

    preview = await ac.post("/api/v1/platform/email/design/preview", json={"theme": "ocean"}, headers=owner)
    assert preview.status_code == 200, preview.text
    assert "linear-gradient(90deg,#0b3b66,#38bdf8)" in preview.json()["data"]["html"]

    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.patch("/api/v1/platform/email/design", json={"theme": "ocean"}, headers=admin)
    assert denied.status_code == 403
