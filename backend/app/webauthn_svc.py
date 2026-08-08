"""WebAuthn / passkey registration and authentication."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

CHALLENGE_TTL_MINUTES = 5


def rp_id() -> str:
    return (settings.WEBAUTHN_RP_ID or "localhost").strip() or "localhost"


def rp_name() -> str:
    return (settings.WEBAUTHN_RP_NAME or "RIBDIGI ERP").strip() or "RIBDIGI ERP"


def expected_origin() -> str:
    return (settings.WEBAUTHN_ORIGIN or settings.FRONTEND_URL or "http://localhost:3000").strip().rstrip(
        "/"
    )


async def count_credentials(db: AsyncSession, user_id: str) -> int:
    rows = (
        await db.execute(
            select(m.WebAuthnCredential.id).where(m.WebAuthnCredential.user_id == user_id)
        )
    ).scalars().all()
    return len(rows)


async def list_credentials(db: AsyncSession, *, tenant_id: str, user_id: str) -> list[m.WebAuthnCredential]:
    return list(
        (
            await db.execute(
                select(m.WebAuthnCredential)
                .where(
                    m.WebAuthnCredential.tenant_id == tenant_id,
                    m.WebAuthnCredential.user_id == user_id,
                )
                .order_by(m.WebAuthnCredential.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def user_has_webauthn(db: AsyncSession, user_id: str) -> bool:
    return (await count_credentials(db, user_id)) > 0


async def user_has_mfa(db: AsyncSession, user: m.User) -> bool:
    if bool(user.totp_enabled):
        return True
    return await user_has_webauthn(db, user.id)


def serialize_credential(row: m.WebAuthnCredential) -> dict:
    return {
        "id": row.id,
        "name": row.name or "Passkey",
        "device_type": row.device_type,
        "backed_up": bool(row.backed_up),
        "sign_count": int(row.sign_count or 0),
        "transports": row.transports or [],
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
    }


async def _store_challenge(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    purpose: str,
    challenge_b64: str,
) -> None:
    # Clear prior challenges for this purpose
    old = (
        await db.execute(
            select(m.WebAuthnChallenge).where(
                m.WebAuthnChallenge.user_id == user_id,
                m.WebAuthnChallenge.purpose == purpose,
            )
        )
    ).scalars().all()
    for row in old:
        await db.delete(row)
    db.add(
        m.WebAuthnChallenge(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
            challenge=challenge_b64,
            expires_at=datetime.utcnow() + timedelta(minutes=CHALLENGE_TTL_MINUTES),
        )
    )
    await db.flush()


async def _pop_challenge(
    db: AsyncSession, *, user_id: str, purpose: str
) -> bytes:
    from webauthn.helpers import base64url_to_bytes

    row = (
        await db.execute(
            select(m.WebAuthnChallenge).where(
                m.WebAuthnChallenge.user_id == user_id,
                m.WebAuthnChallenge.purpose == purpose,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail="WebAuthn challenge missing or expired — start again")
    if row.expires_at < datetime.utcnow():
        await db.delete(row)
        await db.flush()
        raise HTTPException(status_code=400, detail="WebAuthn challenge expired — start again")
    challenge = row.challenge
    await db.delete(row)
    await db.flush()
    return base64url_to_bytes(challenge)


async def registration_options(db: AsyncSession, user: m.User) -> dict:
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers import bytes_to_base64url
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
        PublicKeyCredentialDescriptor,
    )

    existing = await list_credentials(db, tenant_id=user.tenant_id, user_id=user.id)
    exclude = []
    for cred in existing:
        try:
            from webauthn.helpers import base64url_to_bytes

            exclude.append(
                PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id))
            )
        except Exception:  # noqa: BLE001
            continue

    options = generate_registration_options(
        rp_id=rp_id(),
        rp_name=rp_name(),
        user_id=user.id.encode("utf-8"),
        user_name=user.email,
        user_display_name=user.full_name or user.email,
        exclude_credentials=exclude or None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    await _store_challenge(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        purpose="register",
        challenge_b64=bytes_to_base64url(options.challenge),
    )
    return json.loads(options_to_json(options))


async def verify_registration(
    db: AsyncSession,
    user: m.User,
    *,
    credential: dict,
    name: str | None = None,
) -> m.WebAuthnCredential:
    from webauthn import verify_registration_response
    from webauthn.helpers import bytes_to_base64url

    expected_challenge = await _pop_challenge(db, user_id=user.id, purpose="register")
    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id(),
            expected_origin=expected_origin(),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Passkey registration failed: {exc}") from exc

    cred_id = bytes_to_base64url(verification.credential_id)
    existing = (
        await db.execute(
            select(m.WebAuthnCredential).where(m.WebAuthnCredential.credential_id == cred_id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="This passkey is already registered")

    row = m.WebAuthnCredential(
        tenant_id=user.tenant_id,
        user_id=user.id,
        credential_id=cred_id,
        public_key=bytes_to_base64url(verification.credential_public_key),
        sign_count=int(verification.sign_count or 0),
        transports=credential.get("response", {}).get("transports")
        or credential.get("transports"),
        device_type=str(getattr(verification, "credential_device_type", None) or "")
        or None,
        backed_up=bool(getattr(verification, "credential_backed_up", False)),
        name=(name or "").strip() or "Passkey",
    )
    db.add(row)
    await db.flush()
    return row


async def authentication_options(
    db: AsyncSession, user: m.User
) -> dict:
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
    from webauthn.helpers.structs import (
        PublicKeyCredentialDescriptor,
        UserVerificationRequirement,
    )

    creds = await list_credentials(db, tenant_id=user.tenant_id, user_id=user.id)
    if not creds:
        raise HTTPException(status_code=400, detail="No passkeys registered for this user")

    allow = []
    for cred in creds:
        try:
            allow.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id)))
        except Exception:  # noqa: BLE001
            continue
    if not allow:
        raise HTTPException(status_code=400, detail="No usable passkeys found")

    options = generate_authentication_options(
        rp_id=rp_id(),
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    await _store_challenge(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        purpose="authenticate",
        challenge_b64=bytes_to_base64url(options.challenge),
    )
    return json.loads(options_to_json(options))


async def verify_authentication(
    db: AsyncSession,
    user: m.User,
    *,
    credential: dict,
) -> m.WebAuthnCredential:
    from webauthn import verify_authentication_response
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

    expected_challenge = await _pop_challenge(db, user_id=user.id, purpose="authenticate")
    cred_id_raw = credential.get("id") or credential.get("rawId")
    if not cred_id_raw:
        raise HTTPException(status_code=400, detail="credential.id is required")
    # Client may send base64url id
    cred_id = str(cred_id_raw)
    row = (
        await db.execute(
            select(m.WebAuthnCredential).where(
                m.WebAuthnCredential.user_id == user.id,
                m.WebAuthnCredential.credential_id == cred_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=400, detail="Unknown passkey")

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id(),
            expected_origin=expected_origin(),
            credential_public_key=base64url_to_bytes(row.public_key),
            credential_current_sign_count=int(row.sign_count or 0),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"Passkey authentication failed: {exc}") from exc

    row.sign_count = int(verification.new_sign_count or row.sign_count or 0)
    row.last_used_at = datetime.utcnow()
    await db.flush()
    return row


async def delete_credential(
    db: AsyncSession, *, tenant_id: str, user_id: str, credential_id: str
) -> None:
    row = (
        await db.execute(
            select(m.WebAuthnCredential).where(
                m.WebAuthnCredential.id == credential_id,
                m.WebAuthnCredential.tenant_id == tenant_id,
                m.WebAuthnCredential.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Passkey not found")
    await db.delete(row)
    await db.flush()
