"""Setting the encryption keys in production must not lock anything out.

2FA secrets (and the SMTP / SMS / webhook / bank-feed secrets that share their key) and backups
saved before a key was set must still open after it is set; new values use the new key."""

from __future__ import annotations

from cryptography.fernet import Fernet

from app import backup, server_monitor, totp
from app.config import settings


def test_totp_family_opens_old_values_after_keys_are_set(monkeypatch):
    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", "")
    before = totp.encrypt_secret("smtp-password")  # JWT-derived key

    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with_backup_key = totp.encrypt_secret("sms-token")  # old fallback order: backup key
    assert totp.decrypt_secret(before) == "smtp-password"

    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    after = totp.encrypt_secret("webhook-secret")
    assert totp.decrypt_secret(before) == "smtp-password"
    assert totp.decrypt_secret(with_backup_key) == "sms-token"
    assert totp.decrypt_secret(after) == "webhook-secret"
    # New values are under the TOTP key alone.
    assert Fernet(settings.TOTP_ENCRYPTION_KEY.encode()).decrypt(after.encode()) == b"webhook-secret"


def test_backups_made_before_the_key_still_restore(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", "")
    old = backup._fernet().encrypt(b"backup made before the key")
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert backup._fernet().decrypt(old) == b"backup made before the key"
    new = backup._fernet().encrypt(b"new backup")
    assert Fernet(settings.BACKUP_ENCRYPTION_KEY.encode()).decrypt(new) == b"new backup"


def test_launch_check_names_what_is_wrong_with_the_keys(monkeypatch):
    a, b, c = (Fernet.generate_key().decode() for _ in range(3))
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", a)
    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", "REPLACE_ME_TOTP_ENCRYPTION_KEY___________")
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", a)
    problems = server_monitor.key_problems()
    assert "TOTP_ENCRYPTION_KEY is not set" in problems
    assert any("same value" in p for p in problems)
    assert "Fernet.generate_key" in server_monitor.keys_fix_text()

    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", b)
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", c)
    assert server_monitor.key_problems() == []


def test_metrics_check(monkeypatch):
    monkeypatch.setattr(settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    assert "METRICS_TOKEN" in server_monitor.metrics_problem()
    monkeypatch.setattr(settings, "METRICS_TOKEN", "short")
    assert "shorter" in server_monitor.metrics_problem()
    monkeypatch.setattr(settings, "METRICS_TOKEN", "x" * 40)
    assert server_monitor.metrics_problem() is None
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    monkeypatch.setattr(settings, "METRICS_ENABLED", False)
    assert server_monitor.metrics_problem() is None
