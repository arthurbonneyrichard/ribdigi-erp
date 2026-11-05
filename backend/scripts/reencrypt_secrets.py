"""Rewrite stored gateway secrets under SECRETS_ENCRYPTION_KEY.

Run once after setting the key. Values already under the new key are rewritten harmlessly.
Keep JWT_SECRET_KEY unchanged until this has been applied, or older values cannot be opened.

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

from app import models as m
from app.billing_secrets import _fernet as billing_fernet
from app.db import SessionLocal
from app.ecommerce_secrets import _fernet as ecommerce_fernet
from app.secret_keys import dedicated_key

TARGETS = (
    (m.PlatformBillingGateway, ("secret_enc", "webhook_secret_enc"), billing_fernet),
    (m.EcommerceGateway, ("secret_enc", "webhook_secret_enc"), ecommerce_fernet),
    (m.EcommerceConnector, ("credentials_enc",), ecommerce_fernet),
)


async def main(apply: bool) -> int:
    if not dedicated_key():
        print("SECRETS_ENCRYPTION_KEY is not set; nothing to do.")
        return 1
    rewritten = unreadable = 0
    async with SessionLocal() as db:
        for model, columns, fernet in TARGETS:
            cipher = fernet()
            for row in (await db.execute(select(model))).scalars():
                for column in columns:
                    token = getattr(row, column)
                    if not token:
                        continue
                    try:
                        setattr(row, column, cipher.rotate(token.encode("ascii")).decode("ascii"))
                        rewritten += 1
                    except (InvalidToken, ValueError):
                        unreadable += 1
                        print(f"Cannot open {model.__name__}.{column} on row {row.id}; left as it is.")
        if apply:
            await db.commit()
        else:
            await db.rollback()
    print(f"{'Rewrote' if apply else 'Would rewrite'} {rewritten} value(s); {unreadable} unreadable.")
    return 1 if unreadable else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--apply" in sys.argv)))
