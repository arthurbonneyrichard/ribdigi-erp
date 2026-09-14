"""SEC-M3 — gate unauthenticated POST /tenants self-service signup."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.rate_limit import rate_limiter

pytestmark = pytest.mark.security

ROOT = Path(__file__).resolve().parents[2]


def test_sec_m3_default_disables_public_signup():
    cfg = Settings(APP_ENV="development")
    assert cfg.ALLOW_PUBLIC_TENANT_SIGNUP is False


def test_sec_m3_post_tenants_denied_when_flag_false(monkeypatch):
    rate_limiter.reset_for_tests()
    monkeypatch.setattr("app.api.settings.ALLOW_PUBLIC_TENANT_SIGNUP", False)
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_ENABLED", False)
    client = TestClient(app)
    response = client.post(
        "/api/v1/tenants",
        json={
            "company_name": "Blocked Co",
            "slug": "blocked-sec-m3",
            "industry": "retail",
            "currency": "GHS",
            "admin_email": "admin@blocked-sec-m3.example.com",
            "admin_password": "SecurePass123!",
            "admin_full_name": "Blocked Admin",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "PUBLIC_TENANT_SIGNUP_DISABLED"


def test_sec_m3_production_env_example_disables_signup():
    text = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "ALLOW_PUBLIC_TENANT_SIGNUP=false" in text
    assert "SEC-M3" in text


def test_sec_m3_dev_env_example_enables_signup_for_local():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ALLOW_PUBLIC_TENANT_SIGNUP=true" in text
