# AR/AP Accounting Surface MVP — Stage 232 S1/R1/U1

**Status:** Complete (MVP packaging) — Stage 232  
**Evidence:** `backend/tests/test_stage232_shell_s1.py`, `test_stage232_routes_r1.py`, `test_stage232_ui_u1.py`  
**Register:** `ops/mvp/ar-ap-accounting-surface.json`  
**Related:** [STAGE_232_PLAN.md](STAGE_232_PLAN.md) · Credit UI `/credit?kind=receivable|payable` · Stage 22 BR-10.4/10.5 · Stage 98 O1

Accounting-facing discoverability for **Accounts Receivable** and **Accounts Payable**. Extends the existing Credit engine — **does not claim a new AR/AP engine Complete.**

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `new_ar_ap_engine_claimed` | **false** |
| `go_live_claimed` | **false** |
| `open_banking_claimed` | **false** |

## Surface map

| Surface | Target |
|---------|--------|
| Shell **Accounts Receivable** | `/accounting/receivables` → `/credit?kind=receivable` |
| Shell **Accounts Payable** | `/accounting/payables` → `/credit?kind=payable` |
| Stage 98 Outstanding Receivables / Payables | retained (`/credit?kind=`) |
| Accounting page cross-links | AR/AP cards → same routes |

## Explicitly not claimed

- New parallel AR/AP ledger or aging calculator
- Open Banking adapters
- Go-live Completes
