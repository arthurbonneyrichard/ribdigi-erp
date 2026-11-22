# O2: dedicated encryption keys, rollout runbook

Status: code ready, rehearsed on a restored copy (21 Nov 2026). **Not applied to production.** Nothing here runs until the owner approves.

## What changes
Stored secrets are encrypted with keys derived from `JWT_SECRET_KEY` unless dedicated keys are set. Setting the keys and running the re-encrypt script moves every stored secret onto them, so the JWT signing secret no longer protects anything stored.

| Setting | Holds | Covers |
| --- | --- | --- |
| `SECRETS_ENCRYPTION_KEY` (new, 32+ characters, any random string) | Billing and online-shop gateway secrets, shop connectors, BioTime passwords | `billing_secrets`, `ecommerce_secrets`, `hrm_biometric` |
| `TOTP_ENCRYPTION_KEY` (Fernet key or 64 hex) | 2FA secrets, webhook signing secrets, bank-feed credentials, company SMTP passwords, Twilio tokens | `totp.py` (also used by webhooks, bank feeds, email and SMS settings) |
| `BACKUP_ENCRYPTION_KEY` | `.ribbak` backup files | `backup.py` (old backups still restore through the JWT-derived fallback) |
| `JWT_SECRET_KEY` (unchanged) | Signing sessions only, once the above are applied | |

Production check first: look at the production `.env` in Dokploy. If `TOTP_ENCRYPTION_KEY` and `BACKUP_ENCRYPTION_KEY` are already set to real values, only `SECRETS_ENCRYPTION_KEY` is new. Do not change an existing key: add the new one and let the script rewrite.

Generate (on a trusted machine, never commit, never paste into chat):
```
python -c "import secrets; print(secrets.token_urlsafe(48))"                                   # SECRETS_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"       # TOTP_ENCRYPTION_KEY (only if unset)
```
Store all keys in the password manager as well as in Dokploy. **Losing a key makes the secrets it protects unreadable.**

## Rehearsal result (restored copy, Postgres 16)
- Sample of every secret type seeded under the old setup; all read correctly (baseline).
- `--verify` before the change: failed on all 10 values, as it should (they still depended on the JWT secret).
- `--apply` with the new keys: 10 rewritten, 0 unreadable. `--verify` (JWT swapped for a random value): 10 verified.
- With a completely different `JWT_SECRET_KEY`, the app's own read paths still opened the company SMTP password, SMS token, billing gateway secret, shop gateway secret, shop connector credentials, BioTime password, webhook signing secrets, bank-feed credentials and 2FA secrets.
- A second `--apply` is harmless.
- Not exercised: sending real email/SMS, charging a real card, a live webhook delivery. After the real change, do the checks in step 6.

Repeat the rehearsal on a **real restored production backup** before approving (steps below, using `scripts/rehearse_reencrypt.py`). The rehearsal so far used a copy of local development data, which held few secrets.

## Steps (production)

### 0. Rehearse on a production restore (no production change)
1. Restore the latest production backup into a scratch database on a scratch machine or container.
2. Point `DATABASE_URL` at it, keep old keys, set `APP_ENV=development`, run `python scripts/rehearse_reencrypt.py seed` then `check` (all PASS).
3. Set the new keys; `python scripts/reencrypt_secrets.py` (dry run: note the count), `--apply`, `--verify`.
4. Set a different `JWT_SECRET_KEY`; `python scripts/rehearse_reencrypt.py check` must say ALL PASS. Also sign in to the restored copy and use Company -> Email test, an SMS test and a webhook test if the copy can reach them.

### 1. Backup (production)
1. Dokploy: take a database backup now. Open the file and check it is not near-empty (a failed dump can still upload).
2. Also run a manual dump on the server: `pg_dump -Fc` of the main database **and every desk database** to a file outside the container volume. Copy it off the server.
3. Take a company backup (`POST /backup`) for at least one active company as a second layer.
4. Save the current `.env` values (keys and JWT secret) in the password manager.

### 2. Add the keys (no restart of workers yet)
Dokploy -> backend environment: add `SECRETS_ENCRYPTION_KEY` (and `TOTP_ENCRYPTION_KEY` / `BACKUP_ENCRYPTION_KEY` only if empty). Keep `JWT_SECRET_KEY` unchanged.

### 3. Restart
Redeploy `backend`, `celery_worker`, `celery_beat` so all three load the keys. Old values still open (the app tries the new key, then the JWT-derived one), so nothing breaks yet. Confirm the startup warning about missing keys is gone and the owner console server health page shows keys set.

### 4. Dry run
```
docker compose exec backend python scripts/reencrypt_secrets.py
```
Expect `0 unreadable`. Stop and tell the developer if any value is unreadable.

### 5. Apply and verify
```
docker compose exec backend python scripts/reencrypt_secrets.py --apply
docker compose exec backend python scripts/reencrypt_secrets.py --verify
```
Both must end with `0 unreadable`. The script covers the main database and every desk database.

### 6. Verify the integrations
- Company -> email: send a test email. SMS: send a test message.
- Platform billing: gateway page loads and shows the masked secret; run the gateway test.
- Online shop: gateway/connector page loads; place a test order in test mode.
- Webhooks: send a test webhook; confirm the receiver verifies the signature.
- Bank feed (if used): run a sync.
- HR (if BioTime used): run a sync.
- Sign in with an account that has 2FA; the code must be accepted.
- Take a fresh backup and confirm it completes.

### 7. After a week of normal use
Only now is it safe to rotate `JWT_SECRET_KEY` (this signs everyone out; do it at a quiet time). Not part of this rollout.

## Rollback
Keys alone are not a rollback: after `--apply`, values are under the new keys, so removing the new keys from the settings makes them unreadable.
- **Before step 5 (keys added, nothing rewritten):** remove the added keys and redeploy. Nothing was changed in the database.
- **After step 5:** keep the new keys set (the app works), or restore the step 1 database dump and the old `.env` together. Restoring only one of them breaks the stored secrets. Anything saved after the dump is lost, so decide quickly and tell users.
- Old `.ribbak` backups keep restoring either way.

## Related, not changed here
- `POS_PASSCODE_PEPPER` is empty by default and then derived from the JWT secret. Set it once in production before any JWT rotation, or every cashier passcode would stop working.
