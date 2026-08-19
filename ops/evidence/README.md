# Operator evidence ledger (Stage 30 L1)

| File | Role |
|------|------|
| `ledger.json` | Index of Stage 26–29 durable artifact paths + honesty flags |

Authoritative MVP doc: `docs/EVIDENCE_LEDGER_MVP.md` (`backend/tests/test_evidence_ledger_l1.py`).

Do **not** treat this ledger as a go-live certificate. Honesty flags stay `false` until operators record real runs outside CI. Packaging evidence: `/opt/cursor/artifacts/launch/stage30_l1_evidence_ledger.json`.
