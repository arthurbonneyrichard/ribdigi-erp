# Language/i18n Blocker Matrix MVP — Stage 184 B1

**Status:** Complete (MVP packaging) — Stage 184 B1  
**Evidence:** `backend/tests/test_stage184_blockers_b1.py`  
**Register:** `ops/mvp/i18n-blockers.json`  
**Related:** [I18N_REMAINING_GATE_MVP.md](I18N_REMAINING_GATE_MVP.md) · [ADR_006_LANGUAGE_I18N.md](ADR_006_LANGUAGE_I18N.md) · [DEFERRED_ADR_REGISTER_MVP.md](DEFERRED_ADR_REGISTER_MVP.md) · [STAGE_184_PLAN.md](STAGE_184_PLAN.md)

Honest matrix of i18n blockers. All listed gates remain Remaining / false / deferred.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `i18n_packs_claimed` | **false** |
| `multi_language_claimed` | **false** |
| `non_english_switcher_claimed` | **false** |
| `english_as_i18n_complete_claimed` | **false** |
| `go_live_claimed` | **false** |

## Blocker matrix

| Gate | Status | Notes |
|------|--------|-------|
| ADR-006 non-English packs | Deferred / post-MVP | English only in MVP |
| Multi-language UI switching | Remaining / false | `preferred_language` only `en` |
| Incomplete / fake translation packs | Banned | Must not ship dishonest packs |
| English scaffold as i18n Complete | Non-claim | `frontend/lib/i18n.ts` ≠ packs Complete |
| `i18n_packs_claimed` | **false** | Explicit non-claim |

## Explicitly not claimed

- i18n packs Complete because MVP packaging exists
- Multi-language Completes from this matrix
- English-only Completes as multi-language Complete
