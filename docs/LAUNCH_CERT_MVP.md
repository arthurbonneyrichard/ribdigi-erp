# Launch Certification MVP — Checklist Evidence Packaging

**Status:** Complete (MVP) — Stage 27 L1  
**Evidence:** `backend/tests/test_launch_cert_l1.py` · `/opt/cursor/artifacts/launch/stage27_l1_launch_cert.json`  
**Map:** `ops/launch/checklist-map.json`  
**Checklist:** `docs/LAUNCH_CHECKLIST.md`

This is the **MVP launch certification packaging surface**: classify `LAUNCH_CHECKLIST.md` rows as CI-proven vs operator-required vs deferred, and write durable evidence that production sign-off is **not** claimed by packaging alone. It is **not** a forged go-live certificate.

## Classification

| Class | Meaning | Checklist sections |
|-------|---------|-------------------|
| `operator_required` | Verify in the **target** environment; stay `[ ]` until ops signs | §1 Configuration & secrets; §2 Identity & security; §3 Integrations; §4 “Product create + stock-in…”; §7 Sign-off |
| `ci_proven` | Automated tests / stage evidence already back the `[x]` row | Most §4 stage fidelity/exit rows; §5 Reliability & cache (Stage 19 R1) |
| `deferred` | Post-launch ops follow-ups — never mark Complete as production sign-off | §6 Explicitly deferred |

## Automation hooks

1. Maintain `ops/launch/checklist-map.json` as the authoritative CI-vs-operator map (synced by `test_launch_cert_l1.py`).
2. Before promoting staging → production, operators walk §1–§3 and the remaining §4 smoke row in the **real** env, then fill §7.
3. CI continues to prove packaging honesty: operator rows remain unchecked; `production_signoff_claimed: false` in the evidence artifact.

## Explicitly not claimed

- Filling §7 Name/Date as if Engineering / Operations / Product signed production
- Checking §1–§3 because Stage 27 L1 packaging exists
- Treating Stage 7 L7x / Stage 27 L1 Complete as “production is live”
- Marking §6 deferred items Complete

## Production cutover harness (Stage 29 X1)

Operator cutover / rollback / secrets-handoff packaging extends this map without claiming live promote or §7:

- Pack: [CUTOVER_PACK_MVP.md](CUTOVER_PACK_MVP.md)
- Checklist: `ops/launch/cutover-checklist.json`
- Evidence schema: `ops/launch/cutover-evidence.example.json`
- Optional GHA (extends Stage 28 G1; not main `ci.yml`): `ops/k8s/deploy-production.example.yml`
- Proof: `backend/tests/test_cutover_pack_x1.py`

## Go-live attestation matrix (Stage 30 A1)

Attestation matrix packaging maps Remaining honesty flags across Stage 26–29 packs + LAUNCH §§1–3 / §7 without forging attestation or §7:

- Pack: [ATTESTATION_PACK_MVP.md](ATTESTATION_PACK_MVP.md)
- Matrix: `ops/launch/attestation-matrix.json`
- Evidence schema: `ops/launch/attestation-evidence.example.json`
- Proof: `backend/tests/test_attestation_pack_a1.py`
- Honesty: `attestation_claimed: false`, `section_7_signed: false`, `sections_1_3_verified: false`

## Sign-off

Stage 27 L1 is met when this doc + checklist map + evidence JSON exist, `test_launch_cert_l1.py` passes, and `LAUNCH_CHECKLIST.md` / roadmap cite Stage 27 L1 without fake production sign-off. Stage 29 X1 is met when the cutover pack above passes without inventing live cutover or forged §7. Stage 30 A1 is met when the attestation pack above passes without inventing attestation Complete or forged §7.

See also Stage 203 Tenant MVP Cutover remaining-gate index fidelity (`docs/CUTOVER_REMAINING_GATE_MVP.md`, ADR-412 / ADR-413).

See also Stage 204 Tenant MVP Launch Cert remaining-gate index fidelity (`docs/LAUNCH_CERT_REMAINING_GATE_MVP.md`, ADR-414 / ADR-415).
