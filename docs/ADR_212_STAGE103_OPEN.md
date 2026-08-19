# ADR-212: Stage 103 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-12  
**Supersedes (in part):** ADR-211 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 102 Tenant MVP Residual Reports & Surface Honesty Ops exit criteria are met (`docs/STAGE_102_EXIT_CRITERIA.md`) with R1–A1 / D1 / H102x Complete (ADR-211). Product owner approved opening Stage 103 after Stage 102 freeze via CONTINUE/NEXT with a distinct product outline — **Security, Backup & Company Org Ops** (orphaned security/backup/company org deep-links), not another residual-reports / tax / AI pass:

```
Security Surface Discoverability
     ↓
Backup Schedule & Restore Leaf Honesty
     ↓
Company Org & Numbering Discoverability
     ↓
Tenant MVP Security, Backup & Company Org Ops
```

Audit after Stage 102 found:

| Area | Status |
|------|--------|
| Residual report tabs / tax / AI / Activity Shell honesty | EXISTS (Stage 102 frozen) |
| Security Webhooks / API keys / sessions / passkeys / TOTP anchors + Shell leaves | MISSING — UI exists, deep-links MISSING |
| Backup Schedule vs Backup & Restore distinct hashes | PARTIAL — both Shell leaves → bare `/backup` |
| Company Branches / Document numbering / Media Shell + anchors | MISSING — UI exists; USER_MANUAL “Admin → Branches” without leaf |
| POS Hold/Resume / ADR-002 / ADR-005 / hard-delete | DEFERRED / OUT |

## Decision

1. **Stage 103 delivery track is open** per `docs/STAGE_103_PLAN.md`.
2. **Stage 1–102 freezes remain** for their respective scopes (Stage 102 under ADR-211).
3. Deliver Stage 103 **one workstream at a time** (S1 → B1 → C1 → D1 → H103x).
4. Explicitly out of this pass: paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002); User↔Store membership Complete (ADR-005); hard-delete Complete (ADR-003); impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close; reopening Stages 80–102 frozen scopes; main `ci.yml` deploy jobs. Honesty flags stay false.
5. Extend proven Shell deep-links and page hash scroll — do not invent parallel stacks.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 103 plan items without reopening Stage 1–102 feature scope.
- Stage 103 exit requires `docs/STAGE_103_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
