# Deferred ADR Register MVP — ADR-001–006 Honesty Index

**Status:** Complete (MVP) — Stage 31 R1  
**Evidence:** `backend/tests/test_deferred_adr_register_r1.py` · `/opt/cursor/artifacts/launch/stage31_r1_deferred_adr_register.json`  
**Register:** `ops/mvp/deferred-adr-register.json`  
**Related:** [MVP_GATE_MATRIX_MVP.md](MVP_GATE_MATRIX_MVP.md) · `docs/ADR_001_TENANCY.md` … `docs/ADR_006_LANGUAGE_I18N.md` · `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`

This is the **MVP deferred ADR register packaging surface**: an index of ADR-001–006 with MVP acceptance honesty and post-MVP Remaining. It is **not** an implementation of paid billing, schema-per-tenant, i18n packs, user↔store membership, or hard-delete archival.

## Classification

| Field | Meaning |
|-------|---------|
| `mvp_status` | How the ADR is Accepted for Commercial MVP packaging |
| `post_mvp` | Work that remains deferred after MVP |
| `implemented_as_complete: false` | Register must not claim the deferred scope shipped |

## Register scope

| ADR | MVP decision | Post-MVP Remaining |
|-----|--------------|-------------------|
| ADR-001 | Shared-schema + `tenant_id` | Schema-per-tenant migration |
| ADR-002 | `plan_code` metadata; `billing_deferred` | Paid billing provider |
| ADR-003 | Soft-delete / deactivate only | Hard delete + archival |
| ADR-004 | Menu visibility = module permission | Fine-grained submenu flags |
| ADR-005 | Store via `manager_id` + session `store_id` | User↔store membership |
| ADR-006 | English UI + i18n scaffold | Non-English language packs |

## Automation hooks

1. Maintain `ops/mvp/deferred-adr-register.json` (synced by `test_deferred_adr_register_r1.py`).
2. Top-level honesty: `deferred_implemented_claimed: false`, `billing_complete_claimed: false`, `schema_per_tenant_claimed: false`, `i18n_packs_claimed: false`.
3. CI proves packaging honesty only — never invents deferred ADR Complete.

## Explicitly not claimed

- Paid billing / checkout / payment success
- Schema-per-tenant as shipped Complete
- Non-English UI packs Complete
- User↔store membership / hard-delete archival Complete
- Treating Stage 31 R1 packaging as implementation of ADR post-MVP scopes

## Sign-off

Stage 31 R1 is met when this doc + register JSON + evidence JSON exist, `test_deferred_adr_register_r1.py` passes, and SECURITY_GUIDE / BUSINESS_REQUIREMENTS / launch / roadmap cite Stage 31 R1 without inventing deferred ADR Complete.
