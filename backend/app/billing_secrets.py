"""Encrypt subscription gateway secrets. Distinct from TOTP ciphertext."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.config import settings


def _fernet() -> Fernet:
    material = hashlib.sha256(b"ribdigi-billing-v1" + settings.JWT_SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def encrypt_billing_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_billing_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Unable to read billing credential") from exc
