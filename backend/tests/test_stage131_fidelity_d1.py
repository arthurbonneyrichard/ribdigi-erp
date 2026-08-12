"""Stage 131 D1 — documentation fidelity for Journals, Bank Statements & Email Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage131_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_131_FIDELITY.md")
    assert (
        "journal" in fidelity.lower()
        or "bank" in fidelity.lower()
        or "email" in fidelity.lower()
    )
    for name in (
        "test_stage131_journals_export_j1.py",
        "test_stage131_bank_statements_b1.py",
        "test_stage131_email_settings_export_e1.py",
        "test_stage131_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-268" in fidelity or "ADR_268" in fidelity
    assert "H131x" in fidelity
    plan = _read("docs/STAGE_131_PLAN.md")
    assert "STAGE_131_FIDELITY.md" in plan
    for ws in ("J1", "B1", "E1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage131_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_131_FIDELITY.md" in br
    assert "Stage 131 D1" in br or "test_stage131_fidelity_d1.py" in br
    assert "Stage 131 J1" in br or "Stage 131 B1" in br or "Stage 131 E1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_131_FIDELITY.md" in fidelity_tail or "Stage 131 D1" in fidelity_tail


def test_stage131_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 131 D1" in api or "STAGE_131_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 131 D1" in deploy or "STAGE_131_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 131 D1" in sec or "STAGE_131_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage131_journals_export_j1.py" in launch
    assert "test_stage131_bank_statements_b1.py" in launch
    assert "test_stage131_email_settings_export_e1.py" in launch
    assert "test_stage131_fidelity_d1.py" in launch
    assert "STAGE_131_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Journal" in manual
        or "journal-entries/export" in manual
        or "Bank Statement" in manual
        or "bank-statements/export" in manual
        or "Email Settings" in manual
        or "settings/email/export" in manual
    )


def test_stage131_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_131_FIDELITY.md" in pr and "test_stage131_fidelity_d1.py" in pr
    assert "Stage 131 D1" in pr and "Stage 131 J1" in pr and "Stage 131 B1" in pr and "Stage 131 E1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_131_FIDELITY.md" in roadmap and "Stage 131 D1" in roadmap
    assert "ADR_268_STAGE131_OPEN.md" in roadmap and "STAGE_131_PLAN.md" in roadmap
