"""A malformed encryption key is named, and does not take 2FA or scheduled jobs down with it."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app import ai as ai_svc
from app import models as m
from app import server_monitor
from app import totp as totp_svc
from app.config import settings

# The shape found on live (13 Nov): 63 characters with '&' in it, not any accepted format.
BAD_KEY = "abcdefghijkl&mnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123&456789a"


def test_bad_backup_key_does_not_break_2fa(monkeypatch):
    good = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", good)
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", BAD_KEY)
    token = totp_svc.encrypt_secret("JBSWY3DPEHPK3PXP")
    assert totp_svc.decrypt_secret(token) == "JBSWY3DPEHPK3PXP"
    # Saved under the good key, still opens once the bad key is fixed.
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert totp_svc.decrypt_secret(token) == "JBSWY3DPEHPK3PXP"


def test_launch_check_names_a_malformed_key(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", BAD_KEY)
    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", "x" * 49 + "&ok")
    problems = server_monitor.key_problems()
    assert any("BACKUP_ENCRYPTION_KEY is not a valid key" in p for p in problems), problems
    # SECRETS_ENCRYPTION_KEY is hashed, so any long value works there.
    assert not any("SECRETS_ENCRYPTION_KEY is not a valid key" in p for p in problems), problems
    assert not any("TOTP_ENCRYPTION_KEY" in p for p in problems), problems


@pytest.mark.asyncio
async def test_system_jobs_can_log_ai_queries(db_session, client):
    _ac, seed = client
    row = await ai_svc.record_query(
        db_session, tenant_id=seed["t1"].id, user_id="system", endpoint="security_scan", status="ok"
    )
    await db_session.commit()
    saved = (await db_session.execute(select(m.AiQuery).where(m.AiQuery.id == row.id))).scalar_one()
    assert saved.user_id is None
