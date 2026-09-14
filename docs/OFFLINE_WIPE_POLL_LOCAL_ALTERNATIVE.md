# Offline wipe poll-path local alternative (FCM / PushManager blocked)

**Status labels (honest):**

| Label | Status | Meaning |
|-------|--------|---------|
| Wipe **poll-path engineering-ready** | **YES** | wipe → poll `wipe_pending` → clear IndexedDB → ack contracts + automated evidence |
| Wipe / Web Push delivery | **PARTIAL** | VAPID + automated push evidence landed; real-browser FCM subscribe still required for push-delivery Complete |
| Push-delivery Complete | **MISSING** | Staging till browser proof unchecked |
| Offline Complete | **MISSING** | Browser E2E UX + product attestation still required (`OFFLINE_COMPLETE_ATTESTATION.md`) |
| 7-day VERIFIED | **MISSING** | Physical matrix not run — see `OFFLINE_7DAY_EVIDENCE_TEMPLATE.md` |

**Not claimed:** Offline Complete · push-delivery Complete · 7-day VERIFIED · go-live ·
paid billing Complete · ADR-005 Complete · store-scoped RBAC Complete.

## Why this doc exists

Cloud Agent / locked-down desktops often cannot complete `PushManager.subscribe`
(no usable FCM endpoint — subscribe hangs or times out). That blocks **wipe-via-push**
proof only. Soft lockdown + wipe queue + **online poll** remain the source of truth.

Do **not** treat poll-path engineering-ready as Offline Complete.

## Poll path (always available)

```text
Admin  POST /api/v1/offline/devices/{id}/wipe
        → soft lockdown (revoked + envelope expired)
        → wipe_status=pending
        → push_delivery.status = disabled | skipped_unconfigured | skipped_no_subscription | …

Client  GET  /api/v1/offline/devices/{id}   (Shell every ~45s while online + on `online`)
        → wipe_pending=true

Client  clear IndexedDB (ribdigi-offline-*)
        POST /api/v1/offline/devices/{id}/wipe/ack
        → wipe_status=acked
```

Push is an optional accelerator. Completion is **always** clear + ack.

## Local / Cloud Agent alternative checklist

Use when FCM subscribe is blocked (as documented in
`/opt/cursor/artifacts/local_vapid_wipe_browser_proof_blocker.md`):

- [ ] Leave `OFFLINE_PUSH_ENABLED=false` **or** keep VAPID unset (fail-closed).
- [ ] Register + Bind browser on a staging till (envelope issued).
- [ ] Admin Remote wipe → expect `wipe_pending: true` and push status
      `disabled` / `skipped_unconfigured` / `skipped_no_subscription` (honest).
- [ ] On the till (same bound browser): wait for Shell poll (≤45s) **or** click
      Remote wipe while bound (immediate local clear+ack).
- [ ] Confirm IndexedDB offline DBs gone; device shows wipe acked.
- [ ] Capture wipe API JSON + device GET before/after into an ops evidence pack.

This checklist proves **poll-path** only. Leave wipe-via-push staging boxes
unchecked (`docs/offline_wipe_push_staging_checklist.md`).

## Automated evidence

```bash
cd backend && .venv/bin/pytest \
  tests/test_offline_wipe_poll_path_evidence.py \
  tests/test_offline_remote_wipe.py \
  tests/test_offline_wipe_push_vapid_evidence.py \
  tests/test_offline_push_delivery.py \
  -q
```

| Suite | Proves | Marks Complete? |
|-------|--------|-----------------|
| `test_offline_wipe_poll_path_evidence.py` | Poll path without push/VAPID | **No** — engineering-ready only |
| `test_offline_remote_wipe.py` | Wipe request/ack + RBAC | **No** |
| `test_offline_wipe_push_vapid_evidence.py` | Generated VAPID wipe-via-push | **No** — still PARTIAL |
| `test_offline_push_delivery.py` | Retries / 410 / delivery rows | **No** |

## Client engineering landed for FCM-blocked envs

- `PushManager.subscribe` **timeout** (`subscribe_timeout` reason) so Bind browser
  does not hang forever — `frontend/lib/offlinePush.ts`
- Shell **periodic wipe poll** (~45s) while online — `frontend/components/Shell.tsx`
- Company Bind browser surfaces timeout / fail reasons and reminds operators that
  wipe poll remains source of truth

## Related

- Push ops: `docs/OFFLINE_WEB_PUSH_VAPID_OPS.md`
- Push staging checklist: `docs/offline_wipe_push_staging_checklist.md`
- 7-day operator pack: `docs/OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md` +
  `docs/OFFLINE_7DAY_EVIDENCE_TEMPLATE.md`
- Attestation: `docs/OFFLINE_COMPLETE_ATTESTATION.md`
- Go-live roll-up: `docs/GO_LIVE_READINESS_CHECKLIST.md`
