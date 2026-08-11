# Compliance Readiness MVP — Control Theme Mapping (Not Certification Complete)

**Status:** Complete (MVP) — Stage 33 C1  
**Evidence:** `backend/tests/test_compliance_readiness_c1.py` · `/opt/cursor/artifacts/launch/stage33_c1_compliance_readiness.json`  
**Register:** `ops/mvp/compliance-readiness-register.json`  
**Related:** [SECURITY_GUIDE.md](SECURITY_GUIDE.md) · [RESIDUAL_RISK_MVP.md](RESIDUAL_RISK_MVP.md) · [OPERATOR_REMAINING_MVP.md](OPERATOR_REMAINING_MVP.md) · [MVP_GATE_MATRIX_MVP.md](MVP_GATE_MATRIX_MVP.md) · [STAGE_33_PLAN.md](STAGE_33_PLAN.md)

This is the **MVP compliance readiness packaging surface**: a mapping of control themes (access, audit, TLS, vulnerability, incident, backup/DR, monitoring, change management, data protection, attestation, residual risk) onto existing Stage 18–33 evidence packs. It extends Stage 33 K1 and SECURITY_GUIDE §14 — it does **not** claim SOC 2 or ISO 27001 certification Complete.

## Classification

| Status | Meaning |
|--------|---------|
| `mapped` | Control theme indexed to Complete (MVP) packaging surfaces |
| `partial` | Packaging exists; live operator / hosted SaaS Remaining |
| `deferred` | Consciously Remaining for live go-live / attestation / purchased certs |

Every control keeps `certified: false`. Top-level `soc2_complete_claimed: false` / `iso27001_complete_claimed: false` / `certification_complete_claimed: false`.

## Register scope

1. Access control / RBAC / tenancy themes → SECURITY_GUIDE + ADR-001 + gate matrix.
2. Audit logging / retention themes → ADR-007 + gate matrix.
3. Encryption / TLS themes → TLS ingress pack (live ACME Remaining).
4. Vulnerability management → security scan + pen-test packs (vendor cert Remaining).
5. Incident response → incident pack (hosted PagerDuty Remaining).
6. Backup / DR → PITR / DR runbooks (live drills Remaining).
7. Monitoring → ops monitoring / Grafana packs (hosted SaaS Remaining).
8. Change management → main `ci.yml` deploy-free honesty (Stage 18 C1).
9. Data protection / GDPR themes → SECURITY_GUIDE §14.
10. Go-live attestation → attestation pack Remaining.
11. Residual risk → Stage 33 K1 register (`risks_closed_claimed: false`).

## Automation hooks

1. Maintain `ops/mvp/compliance-readiness-register.json` (synced by `test_compliance_readiness_c1.py`).
2. Align honesty with Remaining / residual risk / SECURITY_GUIDE certification roadmap (Post-MVP).
3. CI proves packaging honesty only — never invents SOC 2 / ISO certification Complete.

## Explicitly not claimed

- SOC 2 Type I or Type II certification Complete because Stage 33 C1 packaging exists
- ISO 27001 certification Complete from packaging
- Purchased vendor pen-test certificate Complete
- Live go-live / §7 / attestation Complete
- Hosted Grafana / PagerDuty / SIEM SaaS Complete
- Re-packaging Stage 26–32 packs as new Complete

## Sign-off

Stage 33 C1 is met when this doc + register JSON + evidence JSON exist, `test_compliance_readiness_c1.py` passes, and SECURITY_GUIDE / PRODUCTION_READINESS / launch / roadmap cite Stage 33 C1 without inventing SOC 2 / ISO certification Complete.
