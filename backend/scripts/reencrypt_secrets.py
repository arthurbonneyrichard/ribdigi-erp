"""Rewrite every stored secret under the encryption keys now set.

Run once after setting SECRETS_ENCRYPTION_KEY and/or TOTP_ENCRYPTION_KEY (values saved before
still open with the old key, so nothing breaks in between). Values already under the new key
are rewritten harmlessly. Keep JWT_SECRET_KEY unchanged until this has been applied, or values
saved under the JWT-derived key cannot be opened.

Covers, in the main database and every desk database:
- SECRETS_ENCRYPTION_KEY: billing and online-shop gateway secrets, shop connectors, BioTime passwords.
- TOTP_ENCRYPTION_KEY: 2FA secrets, webhook signing secrets, bank-feed credentials, company SMTP
  passwords and Twilio tokens.

Backup files are not rewritten: old backups keep restoring with the old key.

Dry run by default. Pass --apply to write.

Usage:
  docker compose exec backend python scripts/reencrypt_secrets.py
  docker compose exec backend python scripts/reencrypt_secrets.py --apply
"""

from __future__ import annotations

import asyncio
import sys

from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app import models as m
from app.config import settings
from app.billing_secrets import _fernet as billing_fernet
from app.db import SessionLocal, on_desk
from app.desks import desk_urls
from app.ecommerce_secrets import _fernet as ecommerce_fernet
from app.hrm_biometric import _fernet as biotime_fernet
from app.totp import _fernet as totp_fernet

COLUMNS = (
    (m.PlatformBillingGateway, ("secret_enc", "webhook_secret_enc"), billing_fernet),
    (m.EcommerceGateway, ("secret_enc", "webhook_secret_enc"), ecommerce_fernet),
    (m.EcommerceConnector, ("credentials_enc",), ecommerce_fernet),
    (m.HrmBiometricLink, ("password_enc",), biotime_fernet),
    (m.User, ("totp_secret_enc", "totp_pending_secret_enc"), totp_fernet),
    (m.WebhookEndpoint, ("secret_enc",), totp_fernet),
    (m.BankAccountConnection, ("credentials_enc",), totp_fernet),
)
# Secrets kept inside a JSON settings column on the company.
JSON_FIELDS = (
    (m.Tenant, "email_settings", "password_enc", totp_fernet),
    (m.Tenant, "sms_settings", "auth_token_enc", totp_fernet),
)


def _rotate(cipher, token: str) -> str:
    return cipher.rotate(token.encode("ascii")).decode("ascii")


async def _one_database(label: str) -> tuple[int, int]:
    rewritten = unreadable = 0
    async with SessionLocal() as db:
        for model, columns, fernet in COLUMNS:
            cipher = fernet()
            try:
                rows = (await db.execute(select(model))).scalars().all()
            except Exception as exc:  # table not in this desk database
                await db.rollback()
                print(f"[{label}] skipped {model.__tablename__}: {type(exc).__name__}")
                continue
            for row in rows:
                for column in columns:
                    token = getattr(row, column)
                    if not token:
                        continue
                    try:
                        setattr(row, column, _rotate(cipher, token))
                        rewritten += 1
                    except (InvalidToken, ValueError):
                        unreadable += 1
                        print(f"[{label}] cannot open {model.__name__}.{column} on row {row.id}; left as it is.")
        for model, column, key, fernet in JSON_FIELDS:
            cipher = fernet()
            for row in (await db.execute(select(model))).scalars():
                data = dict(getattr(row, column) or {})
                token = data.get(key)
                if not token:
                    continue
                try:
                    data[key] = _rotate(cipher, token)
                    setattr(row, column, data)
                    flag_modified(row, column)
                    rewritten += 1
                except (InvalidToken, ValueError):
                    unreadable += 1
                    print(f"[{label}] cannot open {model.__name__}.{column}.{key} on row {row.id}; left as it is.")
        if APPLY:
            await db.commit()
        else:
            await db.rollback()
    return rewritten, unreadable


async def main() -> int:
    total_ok = total_bad = 0
    seen: set[str] = {settings.DATABASE_URL}
    desks: list[tuple[str | None, str]] = [(None, "main")]
    for desk, url in desk_urls().items():
        if url not in seen:
            seen.add(url)
            desks.append((desk, desk))
    for desk, label in desks:
        with on_desk(desk):
            ok, bad = await _one_database(label)
        print(f"[{label}] {'rewrote' if APPLY else 'would rewrite'} {ok} value(s); {bad} unreadable.")
        total_ok += ok
        total_bad += bad
    print(f"Total: {'rewrote' if APPLY else 'would rewrite'} {total_ok}; {total_bad} unreadable.")
    return 1 if total_bad else 0


APPLY = "--apply" in sys.argv

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
