"""Encryption keys for stored gateway and connector secrets.

These used to be derived from JWT_SECRET_KEY alone. Set SECRETS_ENCRYPTION_KEY to give them
their own key: new values use it, and values saved earlier still open through the old key
until scripts/reencrypt_secrets.py rewrites them.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, MultiFernet
from fastapi import HTTPException

from app.config import settings

MIN_KEY_LENGTH = 32


def _fernet_for(purpose: bytes, material: bytes) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(purpose + material).digest()))


def dedicated_key() -> str:
    key = (settings.SECRETS_ENCRYPTION_KEY or "").strip()
    if key and (len(key) < MIN_KEY_LENGTH or key.startswith("REPLACE_ME")):
        raise HTTPException(status_code=500, detail="SECRETS_ENCRYPTION_KEY must be a real key of 32 characters or more")
    return key


def secret_fernet(purpose: bytes) -> MultiFernet:
    """Encrypts with the first key; opens anything saved under either key."""
    legacy = _fernet_for(purpose, settings.JWT_SECRET_KEY.encode())
    key = dedicated_key()
    return MultiFernet([_fernet_for(purpose, key.encode()), legacy] if key else [legacy])
