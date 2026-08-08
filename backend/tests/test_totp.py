import pyotp

from app.totp import (
    encrypt_secret,
    decrypt_secret,
    generate_backup_codes,
    hash_backup_code,
    verify_totp,
    create_challenge_token,
    decode_challenge_token,
    role_requires_2fa,
    path_allowed_during_enrollment,
)


def test_secret_encrypt_roundtrip(monkeypatch):
    monkeypatch.setattr("app.totp.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    monkeypatch.setattr("app.totp.settings.TOTP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.totp.settings.BACKUP_ENCRYPTION_KEY", "")
    secret = pyotp.random_base32()
    enc = encrypt_secret(secret)
    assert enc != secret
    assert decrypt_secret(enc) == secret


def test_verify_totp_window(monkeypatch):
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, code) is True
    assert verify_totp(secret, "000000") is False
    assert verify_totp(secret, "abcdef") is False


def test_backup_code_hash_normalized():
    a = hash_backup_code("abcd-ef12")
    b = hash_backup_code("ABCD EF12")
    assert a == b
    assert len(generate_backup_codes(5)) == 5


def test_challenge_token_roundtrip(monkeypatch):
    monkeypatch.setattr("app.totp.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    token = create_challenge_token(user_id="u1", tenant_id="t1", role="company_admin")
    data = decode_challenge_token(token)
    assert data["sub"] == "u1"
    assert data["tenant_id"] == "t1"
    assert data["type"] == "mfa_challenge"


def test_enforced_roles_and_enrollment_paths(monkeypatch):
    monkeypatch.setattr("app.totp.settings.TOTP_ENFORCED_ROLES", "company_admin,super_admin")
    assert role_requires_2fa("company_admin") is True
    assert role_requires_2fa("cashier") is False
    assert path_allowed_during_enrollment("/api/v1/auth/2fa/setup") is True
    assert path_allowed_during_enrollment("/api/v1/auth/webauthn/register/options") is True
    assert path_allowed_during_enrollment("/api/v1/me") is True
    assert path_allowed_during_enrollment("/api/v1/products") is False
