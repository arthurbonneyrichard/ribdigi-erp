"""Encrypt tenant storefront gateway and connector secrets.

Distinct from TOTP and subscription-billing ciphertext.
"""

from __future__ import annotations

from cryptography.fernet import InvalidToken, MultiFernet
from fastapi import HTTPException

from app.secret_keys import secret_fernet


def _fernet() -> MultiFernet:
    return secret_fernet(b"ribdigi-ecommerce-v1")


def encrypt_ecommerce_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_ecommerce_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Unable to read storefront credential") from exc


def secret_hint(plain: str | None) -> str | None:
    text = (plain or "").strip()
    if not text:
        return None
    if len(text) <= 4:
        return "••••"
    return f"••••{text[-4:]}"
