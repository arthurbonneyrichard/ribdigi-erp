"""Stage 26 D1 — documentation fidelity for Production Platform & Ops (BR-16 / NFR)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage26_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_26_FIDELITY.md")
    assert "BR-16" in fidelity or "Monitoring" in fidelity
    assert "test_ops_monitoring_m1.py" in fidelity
    assert "test_wal_pitr_w1.py" in fidelity
    assert "test_k8s_deploy_k1.py" in fidelity
    assert "test_load_capacity_c1.py" in fidelity
    assert "test_stage26_fidelity_d1.py" in fidelity
    assert "ADR-057" in fidelity or "ADR_057" in fidelity
    assert "Production Platform" in fidelity or "Ops Fidelity" in fidelity
    assert "WAL" in fidelity or "PITR" in fidelity
    assert "H26x" in fidelity
    assert "Grafana" in fidelity or "1000" in fidelity or "PagerDuty" in fidelity

    plan = _read("docs/STAGE_26_PLAN.md")
    assert "STAGE_26_FIDELITY.md" in plan
    for ws in ("M1", "W1", "K1", "C1", "D1", "H26x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    assert "ADR-058" in plan or "ADR_058" in plan
    assert "Closed" in plan or "exit met" in plan.lower()
    assert "ADR-058" in fidelity or "ADR_058" in fidelity or "exit met" in fidelity.lower()


def test_stage26_br16_and_nfr_cites():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 26 D1" in br or "STAGE_26_FIDELITY.md" in br
    assert "Stage 26 W1" in br
    assert "STAGE_26_FIDELITY.md" in br

    s162 = br.split("#### BR-16.2 Scheduled Backup")[1].split("#### BR-16.3")[0]
    assert "[x]" in s162
    assert "S3-compatible" in s162
    assert "Stage 26 W1" in s162

    s163 = br.split("#### BR-16.3 Database Restore")[1].split("---")[0]
    assert "Point-in-time recovery" in s163
    assert "[x]" in s163
    assert "Stage 26 W1" in s163 or "DR_WAL_PITR_RUNBOOK" in s163

    assert "### 5.6 Maintainability" in br
    nfr = br.split("### 5.6 Maintainability")[1].split("### ")[0]
    assert "Logging" in nfr
    assert "Monitoring" in nfr
    assert "Stage 26" in br  # D1 / M1 cite nearby or in BR-16 block


def test_stage26_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 26 D1" in api or "STAGE_26_FIDELITY.md" in api
    assert "test_stage26_fidelity_d1.py" in api or "STAGE_26_FIDELITY.md" in api
    assert "test_ops_monitoring_m1.py" in api or "OPS_MONITORING_MVP.md" in api
    assert "test_k8s_deploy_k1.py" in api or "K8S_DEPLOY_MVP.md" in api
    assert "test_load_capacity_c1.py" in api or "LOAD_CAPACITY_MVP.md" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 26 D1" in deploy or "STAGE_26_FIDELITY.md" in deploy
    assert "K8S_DEPLOY_MVP.md" in deploy
    assert "OPS_MONITORING_MVP.md" in deploy or "Stage 26 M1" in deploy
    assert "LOAD_CAPACITY_MVP.md" in deploy or "Stage 26 C1" in deploy
    assert "DR_WAL_PITR_RUNBOOK.md" in deploy or "Stage 26 W1" in deploy

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 26 D1" in sec or "STAGE_26_FIDELITY.md" in sec
    assert "test_ops_monitoring_m1.py" in sec or "OPS_MONITORING_MVP.md" in sec
    assert "test_wal_pitr_w1.py" in sec or "DR_WAL_PITR_RUNBOOK.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ops_monitoring_m1.py" in launch
    assert "test_wal_pitr_w1.py" in launch
    assert "test_k8s_deploy_k1.py" in launch
    assert "test_load_capacity_c1.py" in launch
    assert "test_stage26_fidelity_d1.py" in launch
    assert "STAGE_26_FIDELITY.md" in launch
    assert "STAGE_26_EXIT_CRITERIA.md" in launch or "ADR-058" in launch


def test_stage26_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_26_FIDELITY.md" in pr
    assert "test_stage26_fidelity_d1.py" in pr
    assert "Stage 26 D1" in pr
    assert "STAGE_26_EXIT_CRITERIA.md" in pr or "ADR-058" in pr or "ADR_058" in pr
    assert "- [x] Monitoring, metrics, logging and alerting complete." in pr
    assert "- [x] Point-in-time recovery/WAL strategy complete." in pr
    assert "- [x] Kubernetes production deployment reviewed." in pr
    assert "- [x] Load/performance tests meet documented targets." in pr
    assert "Stage 26 M1" in pr
    assert "Stage 26 W1" in pr
    assert "Stage 26 K1" in pr
    assert "Stage 26 C1" in pr
    assert "Grafana" in pr or "PagerDuty" in pr or "1000" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_26_FIDELITY.md" in roadmap
    assert "Stage 26 D1" in roadmap
    assert "ADR_057_STAGE26_OPEN.md" in roadmap
    assert "STAGE_26_PLAN.md" in roadmap
    assert "STAGE_26_EXIT_CRITERIA.md" in roadmap
    assert "ADR_058_STAGE26_FREEZE.md" in roadmap
