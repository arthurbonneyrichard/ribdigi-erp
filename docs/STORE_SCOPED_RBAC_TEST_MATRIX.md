# Store-scoped RBAC — living test matrix

**Status:** matrix suite **landed** (indexed automated evidence)  
**Store-scoped RBAC Complete:** **Complete** (flag default OFF) — see `docs/STORE_SCOPED_RBAC_COMPLETE_REMAINING.md`  
**Product ALLOWs:** **Accepted** — [`STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md`](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md)  
**CI target:** `cd backend && PYTHONPATH=. pytest -q tests/test_store_scope_rbac_matrix.py`  
**Marker:** `store_scope` (also included in CI marker pass with security/isolation)

## Purpose

Single indexed living matrix that documents and enforces the store-scope
acceptance spine without growing one-off scripts:

| Class | What it proves |
|-------|----------------|
| `cross_store_deny` | store_manager cannot read/write foreign or null-store commerce rows |
| `manager_union` | Flag ON: `manager_id` ∪ active memberships; foreign excluded |
| `cashier_fail_closed` | Flag ON: empty membership → empty visibility + POS denied; foreign POS denied |
| `membership_on_soak` | ADR-005 + store-scoped honesty Complete; flag default OFF |
| `intentional_allow` | Product-accepted: logo binary GET; caller-scoped `/auth/sessions`; `/notifications/settings` |
| `breadth_index` | Deep modules exist (`test_store_scope_ops_hardening.py`, soak, scaffold, …) |

Machine index: `ops/mvp/store-scope-rbac-matrix.json`  
Living suite: `backend/tests/test_store_scope_rbac_matrix.py` (pytest marker `store_scope`)

## CI

Main `.github/workflows/ci.yml` includes `store_scope` in the marker pass and
an explicit matrix file step (preferred focused target — avoids full-suite
collection cost when iterating):

```bash
cd backend && PYTHONPATH=. pytest -q tests/test_store_scope_rbac_matrix.py
cd backend && PYTHONPATH=. pytest -q -m "security or isolation or store_scope"
```

## Honesty

- `store_scoped_rbac_complete_claimed` = **true** in matrix JSON and API honesty payloads
- ADR-005 membership **is Complete** (flag default OFF intentional)
- Complete criteria: residual dump NONE + product-accepted ALLOWs + this matrix + automated/local soak
- Staging enable of `STORE_MEMBERSHIP_SCOPE_ENABLED` remains ops cutover (does not reopen Complete)
- Do **not** claim Offline / 7-day / go-live / paid billing / overall RBAC Completes from this suite

## Related

- Remaining Complete criteria: [`STORE_SCOPED_RBAC_COMPLETE_REMAINING.md`](STORE_SCOPED_RBAC_COMPLETE_REMAINING.md)
- Intentional ALLOWs: [`STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md`](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md)
- Local soak evidence: [`STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md`](STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md)
- Market-ready pack: [`MARKET_READY_LAUNCH.md`](MARKET_READY_LAUNCH.md)
- ADR-005 soak ops: [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md)
- Soak evidence template: [`ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md`](ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md)
- Go-live §3C: [`GO_LIVE_READINESS_CHECKLIST.md`](GO_LIVE_READINESS_CHECKLIST.md)
- Deep continuum: `backend/tests/test_store_scope_ops_hardening.py`
