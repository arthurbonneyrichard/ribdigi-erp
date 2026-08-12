"""Stage 127 D1 — documentation fidelity for API-Key Status, FX & Schedules Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage127_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_127_FIDELITY.md")
    assert "API" in fidelity or "FX" in fidelity or "schedule" in fidelity.lower()
    for name in (
        "test_stage127_api_key_status_k1.py",
        "test_stage127_fx_rates_export_f1.py",
        "test_stage127_report_schedules_s1.py",
        "test_stage127_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-260" in fidelity or "ADR_260" in fidelity
    assert "H127x" in fidelity
    plan = _read("docs/STAGE_127_PLAN.md")
    assert "STAGE_127_FIDELITY.md" in plan
    for ws in ("K1", "F1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage127_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_127_FIDELITY.md" in br
    assert "Stage 127 D1" in br or "test_stage127_fidelity_d1.py" in br
    assert "Stage 127 K1" in br or "Stage 127 F1" in br or "Stage 127 S1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_127_FIDELITY.md" in fidelity_tail or "Stage 127 D1" in fidelity_tail


def test_stage127_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 127 D1" in api or "STAGE_127_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 127 D1" in deploy or "STAGE_127_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 127 D1" in sec or "STAGE_127_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage127_api_key_status_k1.py" in launch
    assert "test_stage127_fx_rates_export_f1.py" in launch
    assert "test_stage127_report_schedules_s1.py" in launch
    assert "test_stage127_fidelity_d1.py" in launch
    assert "STAGE_127_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "API Key Status" in manual
        or "api-keys/export" in manual
        or "exchange-rates/export" in manual
        or "schedules/export" in manual
        or "FX rates" in manual
    )


def test_stage127_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_127_FIDELITY.md" in pr and "test_stage127_fidelity_d1.py" in pr
    assert "Stage 127 D1" in pr and "Stage 127 K1" in pr and "Stage 127 F1" in pr and "Stage 127 S1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_127_FIDELITY.md" in roadmap and "Stage 127 D1" in roadmap
    assert "ADR_260_STAGE127_OPEN.md" in roadmap and "STAGE_127_PLAN.md" in roadmap
