"""Rehearse the O2 key change on a COPY of the data. Never run this against production.

  seed   writes one sample of every kind of stored secret, encrypted the way the app does today,
         into the copy (marked REHEARSAL so they are easy to find).
  check  reads every secret back through the app's own functions and compares the sample values.

Order for a rehearsal on a restored copy:
  1. Restore a production backup into a scratch database; point DATABASE_URL at it.
  2. Keep the OLD settings:  python scripts/rehearse_reencrypt.py seed
  3. Set the NEW keys (SECRETS_ENCRYPTION_KEY, TOTP_ENCRYPTION_KEY) and run
     python scripts/reencrypt_secrets.py --apply
  4. python scripts/reencrypt_secrets.py --verify      (JWT secret swapped for a random one)
  5. Give the app a different JWT_SECRET_KEY and run: python scripts/rehearse_reencrypt.py check
     It must print PASS for every row. That proves the stored secrets no longer depend on the JWT secret.
"""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app import models as m
from app.config import settings
from app.db import SessionLocal

SAMPLES = {
    "smtp": "rehearsal-smtp-password",
    "sms": "rehearsal-twilio-token",
    "billing": "sk_test_rehearsal_billing",
    "shop": "sk_test_rehearsal_shop",
    "connector": {"api_key": "rehearsal-connector-key"},
    "biotime": "rehearsal-biotime-password",
    "bank": {"access_token": "rehearsal-bank-token"},
    "webhook": "whsec_rehearsal_webhook",
}
MARK = "REHEARSAL"


async def seed() -> None:
    from app.billing_gateway_setup import GATEWAY_ID
    from app.billing_secrets import encrypt_billing_secret
    from app.ecommerce_secrets import encrypt_ecommerce_secret
    from app.hrm_biometric import _encrypt as biotime_encrypt
    from app.totp import encrypt_secret

    async with SessionLocal() as db:
        tenant = (await db.execute(select(m.Tenant).order_by(m.Tenant.created_at))).scalars().first()
        if tenant is None:
            raise SystemExit("The copy has no company to attach samples to.")
        es = dict(tenant.email_settings or {})
        es["password_enc"] = encrypt_secret(SAMPLES["smtp"])
        tenant.email_settings = es
        flag_modified(tenant, "email_settings")
        ss = dict(tenant.sms_settings or {})
        ss["auth_token_enc"] = encrypt_secret(SAMPLES["sms"])
        tenant.sms_settings = ss
        flag_modified(tenant, "sms_settings")
        gateway = await db.get(m.PlatformBillingGateway, GATEWAY_ID)  # one row per platform
        if gateway is None:
            gateway = m.PlatformBillingGateway(id=GATEWAY_ID)
            db.add(gateway)
        gateway.secret_enc = encrypt_billing_secret(SAMPLES["billing"])
        db.add(m.EcommerceGateway(tenant_id=tenant.id, provider="mock", secret_enc=encrypt_ecommerce_secret(SAMPLES["shop"])))
        db.add(m.EcommerceConnector(tenant_id=tenant.id, platform=MARK.lower(), credentials_enc=encrypt_ecommerce_secret(json.dumps(SAMPLES["connector"]))))
        db.add(m.HrmBiometricLink(tenant_id=tenant.id, kind="biotime", name=MARK, password_enc=biotime_encrypt(SAMPLES["biotime"])))
        db.add(m.WebhookEndpoint(tenant_id=tenant.id, url="https://example.invalid/rehearsal", secret_enc=encrypt_secret(SAMPLES["webhook"])))
        account = (await db.execute(select(m.Account).where(m.Account.tenant_id == tenant.id))).scalars().first()
        if account is not None:
            db.add(m.BankAccountConnection(tenant_id=tenant.id, account_id=account.id, credentials_enc=encrypt_secret(json.dumps(SAMPLES["bank"]))))
        await db.commit()
    print("Seeded one sample of each secret type.")


async def check() -> int:
    from app.billing_secrets import decrypt_billing_secret
    from app.ecommerce_secrets import decrypt_ecommerce_secret
    from app.hrm_biometric import _decrypt as biotime_decrypt
    from app.totp import decrypt_secret

    bad = 0

    def report(name: str, got, want) -> None:
        nonlocal bad
        ok = got == want
        bad += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name}")

    async with SessionLocal() as db:
        tenant = (await db.execute(select(m.Tenant).order_by(m.Tenant.created_at))).scalars().first()
        report("company SMTP password", decrypt_secret((tenant.email_settings or {}).get("password_enc", "")), SAMPLES["smtp"])
        report("company SMS auth token", decrypt_secret((tenant.sms_settings or {}).get("auth_token_enc", "")), SAMPLES["sms"])
        for row in (await db.execute(select(m.PlatformBillingGateway).where(m.PlatformBillingGateway.secret_enc.is_not(None)))).scalars():
            try:
                if decrypt_billing_secret(row.secret_enc) == SAMPLES["billing"]:
                    report("billing gateway secret (sample)", True, True)
            except Exception:
                report(f"billing gateway secret {row.id}", False, True)
        row = (await db.execute(select(m.EcommerceGateway).where(m.EcommerceGateway.secret_enc.is_not(None)))).scalars().all()
        report("shop gateway secret (sample)", any(_safe(decrypt_ecommerce_secret, r.secret_enc) == SAMPLES["shop"] for r in row), True)
        row = (await db.execute(select(m.EcommerceConnector).where(m.EcommerceConnector.credentials_enc.is_not(None)))).scalars().all()
        report("shop connector credentials (sample)", any(_safe(lambda t: json.loads(decrypt_ecommerce_secret(t)), r.credentials_enc) == SAMPLES["connector"] for r in row), True)
        row = (await db.execute(select(m.HrmBiometricLink).where(m.HrmBiometricLink.password_enc.is_not(None)))).scalars().all()
        report("BioTime password (sample)", any(_safe(biotime_decrypt, r.password_enc) == SAMPLES["biotime"] for r in row), True)
        for r in (await db.execute(select(m.WebhookEndpoint))).scalars():
            ok = _safe(decrypt_secret, r.secret_enc) is not None
            report(f"webhook signing secret {r.id[:8]}", ok, True)
        row = (await db.execute(select(m.BankAccountConnection).where(m.BankAccountConnection.credentials_enc.is_not(None)))).scalars().all()
        if row:
            report("bank feed credentials (sample)", any(_safe(lambda t: json.loads(decrypt_secret(t)), r.credentials_enc) == SAMPLES["bank"] for r in row), True)
        for u in (await db.execute(select(m.User).where(m.User.totp_secret_enc.is_not(None)))).scalars():
            report(f"2FA secret for user {u.id[:8]}", _safe(decrypt_secret, u.totp_secret_enc) is not None, True)
    print("ALL PASS" if not bad else f"{bad} FAILED")
    return 1 if bad else 0


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


if __name__ == "__main__":
    if settings.APP_ENV.lower() == "production":
        raise SystemExit("Refusing to run: this is a rehearsal tool and APP_ENV is production.")
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "seed":
        asyncio.run(seed())
    elif mode == "check":
        raise SystemExit(asyncio.run(check()))
    else:
        raise SystemExit(__doc__)
