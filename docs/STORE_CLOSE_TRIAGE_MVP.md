# Store-Close Conflict Triage + Catalog Age + Backup Pointer MVP — Stage 174 T1

**Status:** Complete (MVP packaging) — Stage 174 T1  
**Evidence:** `backend/tests/test_stage174_triage_t1.py`  
**Register:** `ops/mvp/store-close-triage.json`  
**Related:** [STORE_CLOSE_CHECKLIST_MVP.md](STORE_CLOSE_CHECKLIST_MVP.md) · [OFFLINE_SYNC_ESCALATION_MVP.md](OFFLINE_SYNC_ESCALATION_MVP.md) · [BACKUP_RESTORE_DRILL_HONESTY_MVP.md](BACKUP_RESTORE_DRILL_HONESTY_MVP.md) · [STAGE_174_PLAN.md](STAGE_174_PLAN.md)

End-of-day conflict triage, offline catalog age note, and backup drill honesty pointer. Live DR Completes stay false.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `live_dr_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist

### Conflict triage

1. Settings → Offline sync: list open conflicts with summary.
2. **Accept client** only when the original op was never applied; block double-post if already applied.
3. Escalate stuck conflicts via `OFFLINE_SYNC_ESCALATION_MVP.md`.

### Offline catalog age

1. Note catalog cache age vs **4 hour** TTL.
2. Prefer refresh while ONLINE before close if cashiers will reopen offline soon.
3. Stock remains non-authoritative offline.

### Backup drill pointer

1. Point operators to `BACKUP_RESTORE_DRILL_HONESTY_MVP.md` for scheduled drills.
2. Do **not** mark live backup/restore or PITR Complete from this closeout step.

## Explicitly not claimed

- Offline Complete product claim
- Live DR / PITR Completes
- Fabricated conflict-free close Completes
