# ADR-276: Stage 135 Open — Tenant MVP Purchase Return CSV, SMS Settings Export & Stores Transfer CSV Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-275](ADR_275_STAGE134_FREEZE.md), [STAGE_135_PLAN.md](STAGE_135_PLAN.md)

## Context

Stage 134 closed purchasing request/order/GRN CSVs under ADR-275.
Tenant operators still cannot export **purchase returns**, **SMS settings** (secret-free), or **stores-permission inter-store transfers** — despite existing return status filters, `sms_status()` (auth token omitted), and `GET /stores/transfers?status=` (inventory twin already shipped in Stage 132).

## Decision

Open **Stage 135 — Tenant MVP Purchase Return CSV, SMS Settings Export & Stores Transfer CSV Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **R1** | Purchase return CSV: `GET /purchasing/returns/export` honoring `status=draft\|posted` + Purchasing Export button |
| **S1** | SMS settings CSV: `GET /settings/sms/export` secret-free (`account_sid_set`, never auth token / raw SID) + Company Export button |
| **T1** | Stores transfer CSV: `GET /stores/transfers/export` (stores permission; reuse stock-transfer CSV helper) + Stores status filter + Shell leaves |
| **D1 / H135x** | Fidelity cite sync + Stage 135 exit; freeze as **ADR-277** |

## Consequences

- Completes purchase-return and SMS channel export after Stage 134 purchasing pipeline and Stage 131 email settings.
- Stores transfer export is a **stores-permission twin** of inventory `/inventory/stock-transfers/export` — not a Stage 132 reopen.
- Does **not** reopen Stages 1–134; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, payment tenant lists, line dumps, or main `ci.yml` deploy.
- Document CSVs are **header-only** (no line dump).
