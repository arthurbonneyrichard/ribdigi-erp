"""Stage 28 D1 — documentation fidelity for Staging Certification (BR-16 / ops)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage28_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_28_FIDELITY.md")
    assert "Staging Certification" in fidelity or "PITR" in fidelity
    assert "test_pitr_drill_pack_r1.py" in fidelity
    assert "test_staging_gha_g1.py" in fidelity
    assert "test_grafana_pack_a1.py" in fidelity
    assert "test_load_cert_pack_c1.py" in fidelity
    assert "test_stage28_fidelity_d1.py" in fidelity
    assert "ADR-061" in fidelity or "ADR_061" in fidelity
    assert "H28x" in fidelity
    assert (
        "1000" in fidelity
        or "Grafana" in fidelity
        or "hosted" in fidelity.lower()
        or "execution" in fidelity.lower()
    )

    plan = _read("docs/STAGE_28_PLAN.md")
    assert "STAGE_28_FIDELITY.md" in plan
    for ws in ("R1", "G1", "A1", "C1", "D1", "H28x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    assert "ADR-062" in plan or "ADR_062" in plan
    assert "Closed" in plan or "exit met" in plan.lower()
    assert "ADR-062" in fidelity or "ADR_062" in fidelity or "exit met" in fidelity.lower()


def test_stage28_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_28_FIDELITY.md" in br
    assert "Stage 28 D1" in br or "test_stage28_fidelity_d1.py" in br
    assert "Stage 28 R1" in br or "PITR_DRILL_PACK_MVP.md" in br

    assert "#### BR-16.3 Database Restore" in br
    s163 = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("#### BR-16.4", "### BR-17", "## BR-17"):
        if stop in s163:
            s163 = s163.split(stop, 1)[0]
            break
    assert "Stage 26 W1" in s163 or "DR_WAL_PITR" in s163
    assert "Stage 28 R1" in s163 or "PITR_DRILL_PACK" in s163
    assert "Remaining" in s163 or "execution" in s163.lower()

    assert _read("docs/PITR_DRILL_PACK_MVP.md")
    assert _read("docs/STAGING_GHA_MVP.md")
    assert _read("docs/GRAFANA_PACK_MVP.md")
    assert _read("docs/LOAD_CERT_PACK_MVP.md")


def test_stage28_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 28 D1" in api or "STAGE_28_FIDELITY.md" in api
    assert "test_stage28_fidelity_d1.py" in api or "STAGE_28_FIDELITY.md" in api
    assert "test_pitr_drill_pack_r1.py" in api or "PITR_DRILL_PACK_MVP.md" in api or "Stage 28 R1" in api
    assert "STAGING_GHA_MVP.md" in api or "test_staging_gha_g1.py" in api or "Stage 28 G1" in api
    assert "GRAFANA_PACK_MVP.md" in api or "test_grafana_pack_a1.py" in api or "Stage 28 A1" in api
    assert "LOAD_CERT_PACK_MVP.md" in api or "test_load_cert_pack_c1.py" in api or "Stage 28 C1" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 28 D1" in deploy or "STAGE_28_FIDELITY.md" in deploy
    assert "STAGING_GHA_MVP.md" in deploy or "Stage 28 G1" in deploy
    assert "GRAFANA_PACK_MVP.md" in deploy or "Stage 28 A1" in deploy or "LOAD_CERT_PACK_MVP.md" in deploy

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 28 D1" in sec or "STAGE_28_FIDELITY.md" in sec
    assert "test_pitr_drill_pack_r1.py" in sec or "PITR_DRILL_PACK_MVP.md" in sec
    assert "test_staging_gha_g1.py" in sec or "STAGING_GHA_MVP.md" in sec
    assert "test_grafana_pack_a1.py" in sec or "GRAFANA_PACK_MVP.md" in sec
    assert "test_load_cert_pack_c1.py" in sec or "LOAD_CERT_PACK_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_pitr_drill_pack_r1.py" in launch
    assert "test_staging_gha_g1.py" in launch
    assert "test_grafana_pack_a1.py" in launch
    assert "test_load_cert_pack_c1.py" in launch
    assert "test_stage28_fidelity_d1.py" in launch
    assert "STAGE_28_FIDELITY.md" in launch
    assert "STAGE_28_EXIT_CRITERIA.md" in launch or "ADR-062" in launch


def test_stage28_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_28_FIDELITY.md" in pr
    assert "test_stage28_fidelity_d1.py" in pr
    assert "Stage 28 D1" in pr
    assert "STAGE_28_EXIT_CRITERIA.md" in pr or "ADR-062" in pr or "ADR_062" in pr
    assert "Stage 28 R1" in pr
    assert "Stage 28 G1" in pr
    assert "Stage 28 A1" in pr
    assert "Stage 28 C1" in pr
    assert (
        "1000" in pr
        or "PITR" in pr
        or "Grafana" in pr
        or "hosted" in pr.lower()
        or "execution" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_28_FIDELITY.md" in roadmap
    assert "Stage 28 D1" in roadmap
    assert "ADR_061_STAGE28_OPEN.md" in roadmap
    assert "STAGE_28_PLAN.md" in roadmap
    assert "STAGE_28_EXIT_CRITERIA.md" in roadmap
    assert "ADR_062_STAGE28_FREEZE.md" in roadmap
