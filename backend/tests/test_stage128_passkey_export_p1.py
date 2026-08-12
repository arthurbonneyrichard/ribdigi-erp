"""Stage 128 P1 — passkey inventory CSV (no public_key / credential_id)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_passkeys_export_excludes_secrets(client, db_session):
    ac, seed = client
    headers = await auth_headers(
        ac, email="mgr@alpha.example.com", tenant_slug="alpha"
    )

    db_session.add(
        m.WebAuthnCredential(
            tenant_id=seed["t1"].id,
            user_id=seed["mgr1"].id,
            credential_id="cred-stage128-secret-id",
            public_key="PUBLIC_KEY_MUST_NOT_EXPORT",
            sign_count=3,
            transports=["internal"],
            device_type="platform",
            backed_up=True,
            name="Stage128 Passkey",
        )
    )
    await db_session.commit()

    exported = await ac.get("/api/v1/auth/webauthn/credentials/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "name" in header and "sign_count" in header
    lower = (header + "\n" + exported.text).lower()
    assert "public_key" not in lower
    assert "credential_id" not in lower
    assert "PUBLIC_KEY_MUST_NOT_EXPORT" not in exported.text
    assert "cred-stage128-secret-id" not in exported.text
    assert "Stage128 Passkey" in exported.text


def test_security_passkey_export_p1():
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Stage 128" in page
    assert "/auth/webauthn/credentials/export" in page
    assert "Export passkeys CSV" in page
