"""Stage 115 D1 — documentation fidelity for Notification History Honesty & Residual Filter Discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage115_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_115_FIDELITY.md")
    assert "History" in fidelity or "Notification" in fidelity or "Purchase" in fidelity
    for name in (
        "test_stage115_notification_history_n1.py",
        "test_stage115_purchase_invoice_p1.py",
        "test_stage115_draft_orders_platform_roles_o1.py",
        "test_stage115_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-236" in fidelity or "ADR_236" in fidelity
    assert "H115x" in fidelity
    plan = _read("docs/STAGE_115_PLAN.md")
    assert "STAGE_115_FIDELITY.md" in plan
    for ws in ("N1", "P1", "O1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage115_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_115_FIDELITY.md" in br
    assert "Stage 115 D1" in br or "test_stage115_fidelity_d1.py" in br
    assert "Stage 115 N1" in br or "Stage 115 P1" in br or "Stage 115 O1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_115_FIDELITY.md" in fidelity_tail or "Stage 115 D1" in fidelity_tail


def test_stage115_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 115 D1" in api or "STAGE_115_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 115 D1" in deploy or "STAGE_115_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 115 D1" in sec or "STAGE_115_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage115_notification_history_n1.py" in launch
    assert "test_stage115_purchase_invoice_p1.py" in launch
    assert "test_stage115_draft_orders_platform_roles_o1.py" in launch
    assert "test_stage115_fidelity_d1.py" in launch
    assert "STAGE_115_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Notification History" in manual
        or "Unpaid Purchases" in manual
        or "Draft Orders" in manual
        or "Platform Admins" in manual
    )


def test_stage115_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_115_FIDELITY.md" in pr and "test_stage115_fidelity_d1.py" in pr
    assert "Stage 115 D1" in pr and "Stage 115 N1" in pr and "Stage 115 P1" in pr and "Stage 115 O1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_115_FIDELITY.md" in roadmap and "Stage 115 D1" in roadmap
    assert "ADR_236_STAGE115_OPEN.md" in roadmap and "STAGE_115_PLAN.md" in roadmap
