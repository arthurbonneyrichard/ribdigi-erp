# Tenant MVP Cashier Quickstart MVP — Stage 172 Q1

**Status:** Complete (MVP packaging) — Stage 172 Q1  
**Evidence:** `backend/tests/test_stage172_quickstart_q1.py`  
**Register:** `ops/mvp/cashier-quickstart.json`  
**Related:** [CASHIER_BIND_CATALOG_MVP.md](CASHIER_BIND_CATALOG_MVP.md) · [CASHIER_POS_DAYONE_MVP.md](CASHIER_POS_DAYONE_MVP.md) · [FAQ_OFFLINE_POS_MVP.md](FAQ_OFFLINE_POS_MVP.md) · [KNOWLEDGE_BASE_MVP.md](KNOWLEDGE_BASE_MVP.md) · [STAGE_172_PLAN.md](STAGE_172_PLAN.md)

Ordered day-one cashier quickstart hub for Tenant MVP POS. Indexes bind/catalog and Hold/flush/accept-client checklists. Distinct from Stage 171 FAQ/KB (reference Q&A). Does **not** claim Offline Complete, live training, or go-live.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `live_training_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Day-one order

1. Sign in with tenant context; open POS for the correct store.
2. Complete **B1** — bind browser device + refresh offline catalog (while ONLINE).
3. Complete **O1** — practice Hold/soft-reserve, know sync flush, know accept-client rules.
4. For symptoms / FAQ, use Stage 171 knowledge base packs.
5. Leave Offline Complete / live training as Remaining.

## Explicitly not claimed

- Offline Complete product acceptance
- Live classroom / certification training Complete
- Fabricated “cashier certified” Completes
- Go-live Complete

## Stage 173 S1 amendment

Recurring open-of-day (not day-one onboarding): [STORE_OPEN_CHECKLIST_MVP.md](STORE_OPEN_CHECKLIST_MVP.md) (`ops/mvp/store-open-checklist.json`, `test_stage173_storeopen_s1.py`).
