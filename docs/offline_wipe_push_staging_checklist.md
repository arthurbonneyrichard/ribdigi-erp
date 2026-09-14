# Offline wipe-via-push staging evidence checklist (operator)

**Status:** Remote wipe + Web Push delivery remain **PARTIAL**. Automated
evidence lives in `backend/tests/test_offline_wipe_push_vapid_evidence.py`.
This checklist is the **operator** real-browser / staging proof step.

**Cannot mark Complete** from automation alone. Physical/browser ops evidence
is required before any push-delivery Complete claim — and even then Offline
Complete / 7-day VERIFIED remain separate gates.

**Not claimed:** Offline Complete · push-delivery Complete · 7-day VERIFIED ·
go-live · paid billing Complete · ADR-005 Complete · store-scoped RBAC Complete.

Operator roll-up: [`GO_LIVE_READINESS_CHECKLIST.md`](GO_LIVE_READINESS_CHECKLIST.md).

## Automated evidence (already landed)

| Check | Coverage |
|-------|----------|
| Fail-closed prod template + empty VAPID keeps push off | `test_evidence_fail_closed_defaults_ops_enable` |
| Generated VAPID keys → honesty helpers stay PARTIAL | `test_evidence_honesty_helpers_never_claim_complete` |
| `GET /offline/push/vapid-public-key` with generated keys | `test_evidence_vapid_public_endpoint_with_generated_keys` |
| Subscribe device → wipe → push payload + VAPID claims | `test_evidence_subscribe_wipe_asserts_payload_and_vapid_claims` |
| HTTP 410 revokes subscription; wipe stays pending | `test_evidence_410_revokes_subscription_wipe_stays_pending` |
| Mock `pywebpush.webpush` default sender path | `test_evidence_mock_pywebpush_backend_default_sender` |
| Delivered push ≠ wipe complete (ack still required) | `test_evidence_wipe_ack_after_delivered_push` |
| SW + client honesty contracts | `test_evidence_sw_and_client_contracts_for_payload` |
| Ops + this checklist present | `test_evidence_staging_checklist_and_ops_docs_present` |

Related delivery unit coverage: `backend/tests/test_offline_push_delivery.py`,
`backend/tests/test_offline_remote_wipe.py`.

Run:

```bash
cd backend && .venv/bin/pytest \
  tests/test_offline_wipe_push_vapid_evidence.py \
  tests/test_offline_push_delivery.py \
  tests/test_offline_remote_wipe.py \
  -q
```

## Operator staging / real-browser proof (required for push Complete)

Do **not** run these on production tills with live queue data. Use a staging
tenant and a disposable browser profile.

1. Generate VAPID keys per `docs/OFFLINE_WEB_PUSH_VAPID_OPS.md` (secret manager;
   never commit private keys).
2. Staging env: set `OFFLINE_PUSH_VAPID_PUBLIC_KEY`,
   `OFFLINE_PUSH_VAPID_PRIVATE_KEY`, `OFFLINE_PUSH_VAPID_SUBJECT=mailto:…`,
   then `OFFLINE_PUSH_ENABLED=true`. Restart API workers.
3. Confirm `GET /api/v1/offline/push/vapid-public-key` returns
   `configured: true`, `enabled: true`, and a public key (no private material).
   Honesty flags `push_delivery_complete_claimed` / `offline_complete_claimed`
   must remain **false**.
4. On a staging till browser: Company → Offline devices → register/bind device →
   **Bind browser** (PushManager subscribe + `PUT .../push-subscription`).
5. From an admin session: `POST /api/v1/offline/devices/{id}/wipe`.
   Expect wipe response `wipe_pending: true` and
   `push_delivery.status: delivered` (or honest skip/fail). Soft lockdown
   applies; queue wipe remains pending until client ack.
6. Browser proof: service worker receives `push` with `type`/`action`
   `remote_wipe`; client clears IndexedDB offline DBs; `POST .../wipe/ack`
   succeeds; device shows wipe acked / not pending.
7. Optional 410 path: revoke subscription at the push service (or use a stale
   endpoint) → wipe returns `subscription_revoked: true`; UI prompts rebind;
   wipe stays pending via online poll until rebind + clear + ack.
8. Fail-closed rollback: set `OFFLINE_PUSH_ENABLED=false` (or clear VAPID keys)
   and restart — wipe still queues; push status is `disabled` /
   `skipped_unconfigured`; poll path remains source of truth.
9. Capture screenshots / HAR / wipe API JSON into an ops evidence pack.
   **Still does not** by itself mark Offline Complete or 7-day VERIFIED.

## Honesty

- Automated VAPID wipe-via-push evidence keeps delivery **PARTIAL**.
- Real-browser staging proof is a prerequisite for any future push-delivery
  Complete claim — **not** for Offline Complete (IndexedDB endurance, 7-day
  matrix, owner-alert push channel, attestation remain separate).
- Leaving `OFFLINE_PUSH_ENABLED=false` in production examples is intentional
  until ops completes this checklist with evidence.
- Design / ops: `docs/OFFLINE_WEB_PUSH_VAPID_OPS.md`
