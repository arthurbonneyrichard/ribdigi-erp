# SBOM / Dependency Disclosure MVP — Supply-Chain Honesty Packaging

**Status:** Complete (MVP) — Stage 40 S1  
**Evidence:** `backend/tests/test_sbom_disclosure_s1.py` · `/opt/cursor/artifacts/launch/stage40_s1_sbom_disclosure.json`  
**Register:** `ops/mvp/sbom-disclosure.json`  
**Related:** [SECURITY_GUIDE.md](SECURITY_GUIDE.md) · [SECURITY_SCAN_MVP.md](SECURITY_SCAN_MVP.md) · [VULN_DISCLOSURE_MVP.md](VULN_DISCLOSURE_MVP.md) · [PENTEST_PACK_MVP.md](PENTEST_PACK_MVP.md) · [STATUS_UPTIME_MVP.md](STATUS_UPTIME_MVP.md) · [STAGE_40_PLAN.md](STAGE_40_PLAN.md) · [ADR_085_STAGE40_OPEN.md](ADR_085_STAGE40_OPEN.md)

This is the **MVP SBOM / dependency disclosure honesty packaging surface**: a customer/procurement-facing supply-chain boundary consolidating SECURITY_GUIDE §12.4 SBOM / Snyk-or-Dependabot / FOSSA / Cosign aspirational themes with Stage 27 security-scan and Stage 38 vulnerability-disclosure packs. It does **not** claim a live SBOM generation pipeline Complete, Cosign-signed releases Complete, paid Snyk/Dependabot/FOSSA SaaS Complete, or that every release already ships a published SBOM.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Supply-chain step indexed to Complete (MVP) product / packaging surfaces |
| `remaining` | Live SBOM pipeline / signing / SaaS scanners still required |

Every step keeps `done: false`. Top-level `sbom_pipeline_live: false` / `cosign_signing_claimed: false` / `snyk_saas_claimed: false` / `fossa_claimed: false` / `dependabot_live: false`.

## Register scope

1. SECURITY_GUIDE §12.4 SBOM theme honesty boundary.
2. Backend dependency manifest packaging (`backend/requirements.txt`).
3. Frontend dependency manifest packaging (`frontend/package.json`).
4. Stage 27 security-scan baseline adjacency.
5. Stage 38 vulnerability disclosure adjacency.
6. Stage 29 pen-test pack adjacency (dependency / vuln theme).
7. Cosign / image-signing Remaining honesty (SECURITY_GUIDE §12.2).
8. License compliance (FOSSA) Remaining honesty.
9. Live SBOM generation pipeline Remaining.
10. Paid Dependabot / Snyk continuous scanning Remaining.

## Automation hooks

1. Maintain `ops/mvp/sbom-disclosure.json` (synced by `test_sbom_disclosure_s1.py`).
2. Align honesty with SECURITY_GUIDE / security-scan / vuln-disclosure Remaining flags.
3. CI proves packaging honesty only — never forges live SBOM or Cosign signing Complete.

## Explicitly not claimed

- Live SBOM generation for every release Complete because Stage 40 S1 packaging exists
- Cosign image signing / verification Complete
- Paid Snyk / Dependabot / FOSSA SaaS Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 27–38 security / disclosure packs as new runtime Complete

## Sign-off

Stage 40 S1 is met when this doc + register JSON + evidence JSON exist, `test_sbom_disclosure_s1.py` passes, and LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / plan cite Stage 40 S1 without inventing live SBOM pipeline Complete.
