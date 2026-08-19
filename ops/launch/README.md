# Launch certification, cutover & evidence ledger maps

| File | Role |
|------|------|
| `checklist-map.json` | CI-proven vs operator-required vs deferred classification for `docs/LAUNCH_CHECKLIST.md` (Stage 27 L1) |
| `cutover-checklist.json` | Production cutover / rollback / secrets handoff phases mapping LAUNCH §§1–3 / §7 (Stage 29 X1) |
| `cutover-evidence.example.json` | Operator evidence schema after a real cutover (not a forged certificate) |
| `attestation-matrix.json` | Go-live attestation Remaining honesty matrix for §§1–3 / §7 + Stage 26–29 flags (Stage 30 A1) |
| `attestation-evidence.example.json` | Operator evidence schema after real go-live verification (not a forged attestation) |

Related Stage 30 L1 ledger: `ops/evidence/ledger.json` · `docs/EVIDENCE_LEDGER_MVP.md` (`test_evidence_ledger_l1.py`).

Authoritative MVP docs:

- `docs/LAUNCH_CERT_MVP.md` (`backend/tests/test_launch_cert_l1.py`)
- `docs/CUTOVER_PACK_MVP.md` (`backend/tests/test_cutover_pack_x1.py`)
- `docs/EVIDENCE_LEDGER_MVP.md` (`backend/tests/test_evidence_ledger_l1.py`)
- `docs/ATTESTATION_PACK_MVP.md` (`backend/tests/test_attestation_pack_a1.py`) — Stage 30 A1

Do **not** treat this packaging as production sign-off. Operator §§1–3 and §7 remain unchecked until a real environment is verified. Stage 29 X1 keeps `production_cutover_claimed: false` and `section_7_signed: false`. Stage 30 L1 keeps `live_runs_certified: false` and `attestation_claimed: false`. Stage 30 A1 keeps `attestation_claimed: false`, `section_7_signed: false`, and `sections_1_3_verified: false`.
