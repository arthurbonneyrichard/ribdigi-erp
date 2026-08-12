# Stage 106 Plan — Tenant MVP Approval Filters, Company Profile & Notification Inbox Ops

**Status:** Closed — exit met (H106x); freeze ADR-219  
**Base:** Expense Scope & Purchase Settings Honesty + Company Profile & Departments Discoverability + Notification Inbox Leaves → Tenant MVP Approval Filters, Company Profile & Notification Inbox Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-218](ADR_218_STAGE106_OPEN.md)  
**Exit:** [STAGE_106_EXIT_CRITERIA.md](STAGE_106_EXIT_CRITERIA.md) · freeze [ADR-219](ADR_219_STAGE106_FREEZE.md)  
**Fidelity:** [STAGE_106_FIDELITY.md](STAGE_106_FIDELITY.md)  
**Prior freeze:** [ADR-217](ADR_217_STAGE105_FREEZE.md) · [STAGE_105_EXIT_CRITERIA.md](STAGE_105_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Expense Scope & Purchase Settings Honesty Pack
        +
Company Profile & Departments Discoverability Pack
        +
Notification Inbox Leaves Pack
        ↓
Tenant MVP Approval Filters, Company Profile & Notification Inbox Ops
```

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **E1** | Expense scope & purchase settings honesty | P0 | COMPLETE |
| **C1** | Company profile & departments discoverability | P0 | COMPLETE |
| **N1** | Notification inbox leaves | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H106x** | Stage 106 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation; POS Hold/Resume; full Billers CRUD; parallel Income; WYSIWYG; fiscal-period close
- Reopening Stages 80–105 frozen feature scopes; main `ci.yml` deploy jobs

## E1 acceptance criteria

- [x] Expense `store_id` / `department_id` URL sync with status; Shell Purchase Settings → `#purchase-settings` with scroll honor.
- [x] Automated proof: `backend/tests/test_stage106_expense_scope_e1.py`.

## C1 acceptance criteria

- [x] Shell + anchors for `#logo` / `#profile` / `#locale` / `#departments`.
- [x] Automated proof: `backend/tests/test_stage106_company_profile_c1.py`.

## N1 acceptance criteria

- [x] Shell Unread + group inbox leaves (`?status=unread`, `?group=stock|orders|payments|system`).
- [x] Automated proof: `backend/tests/test_stage106_notification_inbox_n1.py`.

## D1 / H106x acceptance criteria

- [x] `docs/STAGE_106_FIDELITY.md` + exit/freeze ADR-219.
- [x] Automated proof: `test_stage106_fidelity_d1.py`, `test_stage106_exit_h106x.py`.
