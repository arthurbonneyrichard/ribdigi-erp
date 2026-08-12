"""Stage 153 D1 — documentation fidelity for tenant dashboard / party history CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage153_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_153_FIDELITY.md")
    assert (
        "dashboard" in fidelity.lower()
        or "customer" in fidelity.lower()
        or "supplier" in fidelity.lower()
    )
    for name in (
        "test_stage153_tenant_dashboard_b1.py",
        "test_stage153_customer_history_c1.py",
        "test_stage153_supplier_history_s1.py",
        "test_stage153_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-312" in fidelity or "ADR_312" in fidelity
    assert "H153x" in fidelity
    plan = _read("docs/STAGE_153_PLAN.md")
    assert "STAGE_153_FIDELITY.md" in plan
    for ws in ("B1", "C1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage153_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_153_FIDELITY.md" in br
    assert "Stage 153 D1" in br or "test_stage153_fidelity_d1.py" in br
    assert "Stage 153 B1" in br or "Stage 153 C1" in br or "Stage 153 S1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_153_FIDELITY.md" in fidelity_tail or "Stage 153 D1" in fidelity_tail


def test_stage153_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 153 D1" in api or "STAGE_153_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 153 D1" in deploy or "STAGE_153_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 153 D1" in sec or "STAGE_153_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage153_tenant_dashboard_b1.py" in launch
    assert "test_stage153_customer_history_c1.py" in launch
    assert "test_stage153_supplier_history_s1.py" in launch
    assert "test_stage153_fidelity_d1.py" in launch
    assert "STAGE_153_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "dashboard/export" in manual
        or "Dashboard Aggregates" in manual
        or "history/export" in manual
        or "Customer History" in manual
        or "Supplier History" in manual
    )


def test_stage153_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_153_FIDELITY.md" in pr and "test_stage153_fidelity_d1.py" in pr
    assert "Stage 153 D1" in pr and "Stage 153 B1" in pr and "Stage 153 C1" in pr and "Stage 153 S1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_153_FIDELITY.md" in roadmap and "Stage 153 D1" in roadmap
    assert "ADR_312_STAGE153_OPEN.md" in roadmap and "STAGE_153_PLAN.md" in roadmap
