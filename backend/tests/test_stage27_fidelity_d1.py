"""Stage 27 D1 — documentation fidelity for Commercial MVP Release (BR-16 / ops)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage27_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_27_FIDELITY.md")
    assert "Commercial MVP" in fidelity or "Release Fidelity" in fidelity
    assert "test_backup_offsite_b1.py" in fidelity
    assert "test_pgbouncer_p1.py" in fidelity
    assert "test_security_scan_s1.py" in fidelity
    assert "test_launch_cert_l1.py" in fidelity
    assert "test_stage27_fidelity_d1.py" in fidelity
    assert "ADR-059" in fidelity or "ADR_059" in fidelity
    assert "H27x" in fidelity
    assert "pen test" in fidelity.lower() or "ZAP" in fidelity or "sign-off" in fidelity.lower()

    plan = _read("docs/STAGE_27_PLAN.md")
    assert "STAGE_27_FIDELITY.md" in plan
    for ws in ("B1", "P1", "S1", "L1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    assert "H27x" in plan and "PENDING" in plan
    assert "ADR-059" in plan or "ADR_059" in plan
    assert "D1 complete" in plan or "H27x next" in plan


def test_stage27_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 27 D1" in br or "STAGE_27_FIDELITY.md" in br
    assert "Stage 27 B1" in br
    assert "STAGE_27_FIDELITY.md" in br

    s162 = br.split("#### BR-16.2 Scheduled Backup")[1].split("#### BR-16.3")[0]
    assert "[x]" in s162
    assert "Stage 27 B1" in s162
    assert "BACKUP_OFFSITE_UPLOAD_ENABLED" in s162 or "test_backup_offsite_b1.py" in s162

    assert _read("docs/PGBOUNCER_MVP.md")
    assert _read("docs/SECURITY_SCAN_MVP.md")
    assert _read("docs/LAUNCH_CERT_MVP.md")


def test_stage27_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 27 D1" in api or "STAGE_27_FIDELITY.md" in api
    assert "test_stage27_fidelity_d1.py" in api or "STAGE_27_FIDELITY.md" in api
    assert "test_backup_offsite_b1.py" in api or "BACKUP_OFFSITE" in api or "Stage 27 B1" in api
    assert "PGBOUNCER_MVP.md" in api or "test_pgbouncer_p1.py" in api or "Stage 27 P1" in api
    assert "SECURITY_SCAN_MVP.md" in api or "test_security_scan_s1.py" in api or "Stage 27 S1" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 27 D1" in deploy or "STAGE_27_FIDELITY.md" in deploy
    assert "PGBOUNCER_MVP.md" in deploy or "Stage 27 P1" in deploy

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 27 D1" in sec or "STAGE_27_FIDELITY.md" in sec
    assert "test_security_scan_s1.py" in sec or "SECURITY_SCAN_MVP.md" in sec
    assert "test_launch_cert_l1.py" in sec or "LAUNCH_CERT_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_backup_offsite_b1.py" in launch
    assert "test_pgbouncer_p1.py" in launch
    assert "test_security_scan_s1.py" in launch
    assert "test_launch_cert_l1.py" in launch
    assert "test_stage27_fidelity_d1.py" in launch
    assert "STAGE_27_FIDELITY.md" in launch


def test_stage27_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_27_FIDELITY.md" in pr
    assert "test_stage27_fidelity_d1.py" in pr
    assert "Stage 27 D1" in pr
    assert "Stage 27 B1" in pr
    assert "Stage 27 P1" in pr
    assert "Stage 27 S1" in pr
    assert "Stage 27 L1" in pr
    assert "pen test" in pr.lower() or "ZAP" in pr or "1000" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_27_FIDELITY.md" in roadmap
    assert "Stage 27 D1" in roadmap
    assert "ADR_059_STAGE27_OPEN.md" in roadmap
    assert "STAGE_27_PLAN.md" in roadmap
