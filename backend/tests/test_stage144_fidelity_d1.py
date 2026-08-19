"""Stage 144 D1 — documentation fidelity for deliveries / FEFO / archives CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage144_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_144_FIDELITY.md")
    assert (
        "deliver" in fidelity.lower()
        or "fefo" in fidelity.lower()
        or "archive" in fidelity.lower()
    )
    for name in (
        "test_stage144_webhook_deliveries_w1.py",
        "test_stage144_fefo_settings_f1.py",
        "test_stage144_audit_archives_a1.py",
        "test_stage144_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-294" in fidelity or "ADR_294" in fidelity
    assert "H144x" in fidelity
    plan = _read("docs/STAGE_144_PLAN.md")
    assert "STAGE_144_FIDELITY.md" in plan
    for ws in ("W1", "F1", "A1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage144_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_144_FIDELITY.md" in br
    assert "Stage 144 D1" in br or "test_stage144_fidelity_d1.py" in br
    assert "Stage 144 W1" in br or "Stage 144 F1" in br or "Stage 144 A1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_144_FIDELITY.md" in fidelity_tail or "Stage 144 D1" in fidelity_tail


def test_stage144_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 144 D1" in api or "STAGE_144_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 144 D1" in deploy or "STAGE_144_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 144 D1" in sec or "STAGE_144_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage144_webhook_deliveries_w1.py" in launch
    assert "test_stage144_fefo_settings_f1.py" in launch
    assert "test_stage144_audit_archives_a1.py" in launch
    assert "test_stage144_fidelity_d1.py" in launch
    assert "STAGE_144_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "deliveries/export" in manual
        or "Deliveries" in manual
        or "FEFO" in manual
        or "settings/export" in manual
        or "archives/export" in manual
        or "Archives" in manual
    )


def test_stage144_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_144_FIDELITY.md" in pr and "test_stage144_fidelity_d1.py" in pr
    assert "Stage 144 D1" in pr and "Stage 144 W1" in pr and "Stage 144 F1" in pr and "Stage 144 A1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_144_FIDELITY.md" in roadmap and "Stage 144 D1" in roadmap
    assert "ADR_294_STAGE144_OPEN.md" in roadmap and "STAGE_144_PLAN.md" in roadmap
