"""Admin and platform passwords need 12+ characters on a production server; development keeps 8."""
import pytest
from fastapi import HTTPException

from app.config import settings
from app.security import validate_password_strength

SHORT = "Abcd@123"          # 8 characters, meets the base rule
LONG = "Abcd@1234567"       # 12 characters


def test_short_password_allowed_outside_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    validate_password_strength(SHORT, role="company_admin")
    validate_password_strength(SHORT, privileged=True)


@pytest.mark.parametrize("role", ["company_admin", "super_admin", "platform_owner", "platform_support"])
def test_admin_and_platform_need_twelve_in_production(monkeypatch, role):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(HTTPException) as err:
        validate_password_strength(SHORT, role=role)
    assert err.value.status_code == 400 and "12" in err.value.detail
    validate_password_strength(LONG, role=role)


def test_privileged_flag_and_staff_rule(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(HTTPException):
        validate_password_strength(SHORT, privileged=True)
    validate_password_strength(SHORT, role="cashier")  # ordinary staff keep the 8-character rule
    with pytest.raises(HTTPException):
        validate_password_strength("sh1A!", role="cashier")
