"""Encrypt subscription gateway secrets. Distinct from TOTP ciphertext."""

from __future__ import annotations

from cryptography.fernet import InvalidToken, MultiFernet
from fastapi import HTTPException

from app.secret_keys import secret_fernet


def _fernet() -> MultiFernet:
    return secret_fernet(b"ribdigi-billing-v1")


def encrypt_billing_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_billing_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Unable to read billing credential") from exc
