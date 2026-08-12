"""TOTP two-factor authentication with encrypted secrets and backup codes."""

from __future__ import annotations

import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

ENFORCED_ROLES = frozenset(
    {
        "company_admin",
        "super_admin",
        "platform_owner",
        "platform_admin",
    }
)
BACKUP_CODE_COUNT = 10
CHALLENGE_TTL_MINUTES = 5
ISSUER = "RIBDIGI ERP"


def _fernet() -> Fernet:
    raw = (settings.TOTP_ENCRYPTION_KEY or settings.BACKUP_ENCRYPTION_KEY or "").strip()
    if raw:
        try:
            return Fernet(raw.encode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Invalid TOTP encryption key: {exc}") from exc
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ribdigi-totp-v1",
        iterations=120_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.JWT_SECRET_KEY.encode("utf-8")))
    return Fernet(key)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception) as exc:
        raise HTTPException(status_code=500, detail="Unable to decrypt TOTP secret") from exc


def hash_backup_code(code: str) -> str:
    normalized = (code or "").replace(" ", "").replace("-", "").upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def role_requires_2fa(role: str) -> bool:
    configured = {x.strip() for x in settings.TOTP_ENFORCED_ROLES.split(",") if x.strip()}
    return role in (configured or ENFORCED_ROLES)


def otpauth_uri(*, secret: str, email: str, tenant_slug: str | None = None) -> str:
    label = f"{email}"
    if tenant_slug:
        label = f"{tenant_slug}:{email}"
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=ISSUER)


def qr_png_base64(otpauth_url: str) -> str:
    img = qrcode.make(otpauth_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def verify_totp(secret: str, code: str) -> bool:
    cleaned = (code or "").replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != 6:
        return False
    return pyotp.TOTP(secret).verify(cleaned, valid_window=1)


def create_challenge_token(*, user_id: str, tenant_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "mfa_challenge",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=CHALLENGE_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_challenge_token(token: str) -> dict:
    try:
        data = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired 2FA challenge") from exc
    if data.get("type") not in {"totp_challenge", "mfa_challenge"}:
        raise HTTPException(status_code=401, detail="Invalid 2FA challenge token")
    if not data.get("sub") or not data.get("tenant_id"):
        raise HTTPException(status_code=401, detail="Invalid 2FA challenge claims")
    return data


async def replace_backup_codes(db: AsyncSession, user: m.User) -> list[str]:
    existing = (
        await db.execute(
            select(m.TwoFactorBackupCode).where(
                m.TwoFactorBackupCode.user_id == user.id,
                m.TwoFactorBackupCode.tenant_id == user.tenant_id,
            )
        )
    ).scalars().all()
    for row in existing:
        await db.delete(row)
    codes = generate_backup_codes()
    for code in codes:
        db.add(
            m.TwoFactorBackupCode(
                tenant_id=user.tenant_id,
                user_id=user.id,
                code_hash=hash_backup_code(code),
            )
        )
    await db.flush()
    return codes


async def consume_backup_code(db: AsyncSession, user: m.User, code: str) -> bool:
    digest = hash_backup_code(code)
    row = (
        await db.execute(
            select(m.TwoFactorBackupCode).where(
                m.TwoFactorBackupCode.user_id == user.id,
                m.TwoFactorBackupCode.tenant_id == user.tenant_id,
                m.TwoFactorBackupCode.code_hash == digest,
                m.TwoFactorBackupCode.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not row:
        return False
    row.used_at = datetime.utcnow()
    await db.flush()
    return True


async def verify_user_second_factor(db: AsyncSession, user: m.User, code: str) -> bool:
    if not user.totp_enabled or not user.totp_secret_enc:
        return False
    secret = decrypt_secret(user.totp_secret_enc)
    if verify_totp(secret, code):
        return True
    return await consume_backup_code(db, user, code)


async def start_setup(db: AsyncSession, user: m.User, tenant: m.Tenant | None) -> dict:
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    secret = pyotp.random_base32()
    user.totp_pending_secret_enc = encrypt_secret(secret)
    await db.flush()
    uri = otpauth_uri(secret=secret, email=user.email, tenant_slug=tenant.slug if tenant else None)
    return {
        "secret": secret,
        "otpauth_url": uri,
        "qr_png_base64": qr_png_base64(uri),
        "issuer": ISSUER,
    }


async def confirm_setup(db: AsyncSession, user: m.User, code: str) -> list[str]:
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    if not user.totp_pending_secret_enc:
        raise HTTPException(status_code=400, detail="Start 2FA setup first")
    secret = decrypt_secret(user.totp_pending_secret_enc)
    if not verify_totp(secret, code):
        raise HTTPException(status_code=400, detail="Invalid authenticator code")
    user.totp_secret_enc = user.totp_pending_secret_enc
    user.totp_pending_secret_enc = None
    user.totp_enabled = True
    user.totp_confirmed_at = datetime.utcnow()
    codes = await replace_backup_codes(db, user)
    await db.flush()
    return codes


async def disable_2fa(db: AsyncSession, user: m.User) -> None:
    user.totp_enabled = False
    user.totp_secret_enc = None
    user.totp_pending_secret_enc = None
    user.totp_confirmed_at = None
    existing = (
        await db.execute(
            select(m.TwoFactorBackupCode).where(
                m.TwoFactorBackupCode.user_id == user.id,
                m.TwoFactorBackupCode.tenant_id == user.tenant_id,
            )
        )
    ).scalars().all()
    for row in existing:
        await db.delete(row)
    await db.flush()


def status_payload(user: m.User) -> dict:
    return {
        "enabled": bool(user.totp_enabled),
        "confirmed_at": user.totp_confirmed_at,
        "role_requires_2fa": role_requires_2fa(user.role),
        "must_enroll_2fa": role_requires_2fa(user.role) and not bool(user.totp_enabled),
        "pending_setup": bool(user.totp_pending_secret_enc) and not bool(user.totp_enabled),
    }


# Paths allowed while admin must enroll 2FA
ENROLLMENT_ALLOWED_SUFFIXES = (
    "/me",
    "/auth/me",
    "/auth/logout",
    "/auth/sessions",
    "/auth/2fa/status",
    "/auth/2fa/setup",
    "/auth/2fa/confirm",
    "/auth/2fa/disable",
    "/auth/2fa/backup-codes",
    "/auth/webauthn/register/options",
    "/auth/webauthn/register/verify",
    "/auth/webauthn/credentials",
    "/settings/email",
    "/health",
)


def path_allowed_during_enrollment(path: str) -> bool:
    for suffix in ENROLLMENT_ALLOWED_SUFFIXES:
        if path.endswith(suffix) or f"{suffix}/" in path:
            return True
    # session revoke by id
    if "/auth/sessions/" in path:
        return True
    if "/auth/webauthn/credentials/" in path:
        return True
    return False
