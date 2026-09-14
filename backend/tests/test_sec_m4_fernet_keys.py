"""SEC-M4 — production requires dedicated TOTP/backup Fernet keys (fail closed)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.config import Settings
from app.totp import encrypt_secret, decrypt_secret
from app import backup as backup_mod

pytestmark = pytest.mark.security

_VALID_FERNET = Fernet.generate_key().decode()
_VALID_FERNET_B = Fernet.generate_key().decode()


def _prod_kwargs(**overrides):
    base = dict(
        APP_ENV="production",
        JWT_SECRET_KEY="x" * 32,
        DEBUG=False,
        CORS_ORIGINS="https://app.example.com",
        RATE_LIMIT_ENABLED=True,
        EMAIL_ENABLED=False,
        SMS_ENABLED=False,
        TOTP_ENCRYPTION_KEY=_VALID_FERNET,
        BACKUP_ENCRYPTION_KEY=_VALID_FERNET_B,
    )
    base.update(overrides)
    return base


def test_sec_m4_production_accepts_dedicated_fernet_keys():
    cfg = Settings(**_prod_kwargs())
    assert cfg.TOTP_ENCRYPTION_KEY == _VALID_FERNET
    assert cfg.BACKUP_ENCRYPTION_KEY == _VALID_FERNET_B


def test_sec_m4_production_rejects_missing_totp_key():
    with pytest.raises(Exception) as exc:
        Settings(**_prod_kwargs(TOTP_ENCRYPTION_KEY=""))
    assert "TOTP_ENCRYPTION_KEY" in str(exc.value)


def test_sec_m4_production_rejects_missing_backup_key():
    with pytest.raises(Exception) as exc:
        Settings(**_prod_kwargs(BACKUP_ENCRYPTION_KEY=""))
    assert "BACKUP_ENCRYPTION_KEY" in str(exc.value)


def test_sec_m4_production_rejects_invalid_fernet_key():
    with pytest.raises(Exception) as exc:
        Settings(**_prod_kwargs(TOTP_ENCRYPTION_KEY="not-a-fernet-key"))
    assert "TOTP_ENCRYPTION_KEY" in str(exc.value) or "Fernet" in str(exc.value)


def test_sec_m4_totp_runtime_fail_closed_in_production(monkeypatch):
    monkeypatch.setattr("app.totp.settings.APP_ENV", "production")
    monkeypatch.setattr("app.totp.settings.TOTP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.totp.settings.BACKUP_ENCRYPTION_KEY", "")
    with pytest.raises(HTTPException) as exc:
        encrypt_secret("SECRETBASE32TEST====")
    assert exc.value.status_code == 500
    assert "required in production" in str(exc.value.detail).lower() or "TOTP" in str(
        exc.value.detail
    )


def test_sec_m4_backup_runtime_fail_closed_in_production(monkeypatch):
    monkeypatch.setattr("app.backup.settings.APP_ENV", "production")
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    with pytest.raises(HTTPException) as exc:
        backup_mod._fernet()
    assert exc.value.status_code == 500
    assert "BACKUP_ENCRYPTION_KEY" in str(exc.value.detail)


def test_sec_m4_totp_uses_dedicated_key_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.totp.settings.APP_ENV", "production")
    monkeypatch.setattr("app.totp.settings.TOTP_ENCRYPTION_KEY", key)
    monkeypatch.setattr("app.totp.settings.BACKUP_ENCRYPTION_KEY", "")
    secret = "JBSWY3DPEHPK3PXP"
    enc = encrypt_secret(secret)
    assert enc != secret
    assert decrypt_secret(enc) == secret


def test_sec_m4_dev_jwt_fallback_still_allowed(monkeypatch):
    monkeypatch.setattr("app.totp.settings.APP_ENV", "development")
    monkeypatch.setattr("app.totp.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    monkeypatch.setattr("app.totp.settings.TOTP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.totp.settings.BACKUP_ENCRYPTION_KEY", "")
    secret = "JBSWY3DPEHPK3PXP"
    assert decrypt_secret(encrypt_secret(secret)) == secret


def test_sec_m4_production_env_example_documents_keys():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    text = (root / ".env.production.example").read_text(encoding="utf-8")
    assert "TOTP_ENCRYPTION_KEY=" in text
    assert "BACKUP_ENCRYPTION_KEY=" in text
    assert "SEC-M4" in text
    assert "Fernet.generate_key" in text or "generate_key" in text


def test_sec_m4_helm_documents_required_secret_keys():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    values = (root / "helm" / "ribdigi" / "values.yaml").read_text(encoding="utf-8")
    assert "TOTP_ENCRYPTION_KEY" in values
    assert "BACKUP_ENCRYPTION_KEY" in values
    secrets = (root / "helm" / "ribdigi" / "templates" / "secrets.example.yaml").read_text(
        encoding="utf-8"
    )
    assert "TOTP_ENCRYPTION_KEY:" in secrets
    assert "BACKUP_ENCRYPTION_KEY:" in secrets
