# Post-MVP Backlog MVP — Deferred ADR + Operator Remaining Index

**Status:** Complete (MVP) — Stage 32 B1  
**Evidence:** `backend/tests/test_post_mvp_backlog_b1.py` · `/opt/cursor/artifacts/launch/stage32_b1_post_mvp_backlog.json`  
**Backlog:** `ops/mvp/post-mvp-backlog.json`  
**Related:** [DEFERRED_ADR_REGISTER_MVP.md](DEFERRED_ADR_REGISTER_MVP.md) · [OPERATOR_REMAINING_MVP.md](OPERATOR_REMAINING_MVP.md) · [RELEASE_NOTES_MVP.md](RELEASE_NOTES_MVP.md) · [MVP_DECLARATION_MVP.md](MVP_DECLARATION_MVP.md) · [STAGE_32_PLAN.md](STAGE_32_PLAN.md)

This is the **MVP post-MVP backlog packaging surface**: an index of deferred ADR-001–006 scopes, operator Remaining items, and selected product deferred themes as backlog. It extends Stage 31 R1 / O1 honesty — it does **not** implement billing, schema-per-tenant, i18n packs, store membership, hard-delete, or forge live go-live.

## Classification

| Category | Meaning |
|----------|---------|
| `deferred_adr` | ADR-001–006 post-MVP Remaining scopes |
| `operator_remaining` | Live drills / attestation / hosted SaaS / purchased pen-test |
| `product_deferred` | Open Banking / tax e-file / external LLM themes deferred from Stage plans |

Every item keeps `status: backlog` and `implemented_as_complete: false`.

## Backlog scope

1. Index ADR-001–006 from `ops/mvp/deferred-adr-register.json`.
2. Index operator Remaining themes from `ops/mvp/operator-remaining-register.json` (go-live/§7, live drills, hosted SaaS, vendor pen-test).
3. Index selected product deferred themes (Open Banking, tax e-file, external AI).
4. Keep top-level `deferred_implemented_claimed: false` / `billing_complete_claimed: false` / `go_live_claimed: false`.

## Automation hooks

1. Maintain `ops/mvp/post-mvp-backlog.json` (synced by `test_post_mvp_backlog_b1.py`).
2. Align ADR and Remaining honesty with Stage 31 R1 / O1 registers.
3. CI proves packaging honesty only — never invents backlog Complete.

## Explicitly not claimed

- Paid billing / schema-per-tenant / i18n / store membership / hard-delete Complete
- Live go-live / §7 / attestation Complete
- Open Banking / tax e-file / external LLM Complete
- Treating Stage 32 B1 packaging as implementation of backlog scopes

## Sign-off

Stage 32 B1 is met when this doc + backlog JSON + evidence JSON exist, `test_post_mvp_backlog_b1.py` passes, and SECURITY_GUIDE / BUSINESS_REQUIREMENTS / launch / roadmap cite Stage 32 B1 without inventing deferred Complete.
