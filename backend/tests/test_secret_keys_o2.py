"""O2: gateway secrets can move to their own key without losing what is already saved."""

import pytest
from cryptography.fernet import InvalidToken
from fastapi import HTTPException

from app import billing_secrets, ecommerce_secrets
from app.config import settings

KEY = "k" * 40
NEW_JWT = "a-different-jwt-secret-after-rotation-000"


def test_without_a_key_existing_values_keep_working(monkeypatch):
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", "")
    token = billing_secrets.encrypt_billing_secret("sk_live_1")
    assert billing_secrets.decrypt_billing_secret(token) == "sk_live_1"


def test_new_key_opens_old_values_and_encrypts_under_itself(monkeypatch):
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", "")
    old = ecommerce_secrets.encrypt_ecommerce_secret("shop_secret")
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", KEY)
    assert ecommerce_secrets.decrypt_ecommerce_secret(old) == "shop_secret"
    new = ecommerce_secrets.encrypt_ecommerce_secret("shop_secret")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", NEW_JWT)
    assert ecommerce_secrets.decrypt_ecommerce_secret(new) == "shop_secret"
    with pytest.raises(HTTPException):
        ecommerce_secrets.decrypt_ecommerce_secret(old)


def test_rotate_moves_an_old_value_off_the_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", "")
    old = billing_secrets.encrypt_billing_secret("whsec_1")
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", KEY)
    rotated = billing_secrets._fernet().rotate(old.encode("ascii")).decode("ascii")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", NEW_JWT)
    assert billing_secrets.decrypt_billing_secret(rotated) == "whsec_1"


def test_billing_and_shop_keys_stay_separate(monkeypatch):
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", KEY)
    token = billing_secrets.encrypt_billing_secret("x")
    with pytest.raises(InvalidToken):
        ecommerce_secrets._fernet().decrypt(token.encode("ascii"))


@pytest.mark.parametrize("bad", ["short", "REPLACE_ME_SECRETS_ENCRYPTION_KEY________"])
def test_placeholder_or_short_key_is_refused(monkeypatch, bad):
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", bad)
    with pytest.raises(HTTPException):
        billing_secrets.encrypt_billing_secret("x")
