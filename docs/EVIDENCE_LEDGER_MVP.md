# Evidence Ledger MVP — Operator Artifact Index Packaging

**Status:** Complete (MVP) — Stage 30 L1  
**Evidence:** `backend/tests/test_evidence_ledger_l1.py` · `/opt/cursor/artifacts/launch/stage30_l1_evidence_ledger.json`  
**Ledger map:** `ops/evidence/ledger.json`  
**Related:** Stage 26–29 pack docs · `ops/launch/` · `docs/CUTOVER_PACK_MVP.md` · `docs/LAUNCH_CERT_MVP.md`

This is the **MVP operator evidence ledger packaging surface**: a single index of Stage 26–29 durable artifact paths and honesty flags. It is **not** a claim that live operator runs (PITR, 1000-VU, ZAP, soak, ACME, cutover) already succeeded, and does **not** re-ship those packs as new Complete.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Fill live evidence only after a real run; keep honesty flags false until then |
| `ci_proven` | Packaging tests that write Stage 26–29 pack evidence JSONs + this ledger honesty |
| `deferred` | Treating the ledger as a go-live certificate; forging live-run flags |

## Ledger scope (summary)

Indexes packaging evidence for:

- Stage 26 — monitoring / WAL / K8s / load capacity
- Stage 27 — offsite upload / PgBouncer / security scan / launch cert
- Stage 28 — PITR drill / staging GHA / Grafana / 1000-VU cert
- Stage 29 — pen-test / soak / TLS / cutover

Each entry records `artifact`, `pack_doc`, `test`, and `honesty` flags that remain `false` for live execution claims.

## Automation hooks

1. Maintain `ops/evidence/ledger.json` (synced by `test_evidence_ledger_l1.py`).
2. CI proves packaging honesty only: `live_runs_certified: false`, `attestation_claimed: false`.
3. Operators attach real run artifacts outside CI; do not flip honesty flags in-repo without ops change-log evidence.

## Explicitly not claimed

- Green live PITR / 1000-VU / GHA apply / ZAP / soak / ACME / cutover from CI
- Re-packaging Stage 26–29 packs as new Complete
- Forged LAUNCH §7 or go-live attestation
- Treating Stage 30 L1 Complete as “production is live”

## Go-live attestation matrix (Stage 30 A1)

Operators walk Remaining honesty flags via [ATTESTATION_PACK_MVP.md](ATTESTATION_PACK_MVP.md) + `ops/launch/attestation-matrix.json` (`test_attestation_pack_a1.py`). Packaging keeps `attestation_claimed: false` and does not forge §7.

## Sign-off

Stage 30 L1 is met when this doc + ledger JSON + evidence JSON exist, `test_evidence_ledger_l1.py` passes, and PRODUCTION_READINESS / launch / roadmap cite Stage 30 L1 without inventing live-run success. Stage 30 A1 extends this ledger into an attestation matrix without claiming go-live Complete.

See also Stage 212 Tenant MVP Evidence Ledger remaining-gate index fidelity (`docs/EVIDENCE_LEDGER_REMAINING_GATE_MVP.md`, ADR-430 / ADR-431) — packaging non-claim as live evidence-ledger Complete.
