"""Stage 106 D1 — documentation fidelity for Approval Filters, Company Profile & Notification Inbox Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage106_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_106_FIDELITY.md")
    assert "Expense" in fidelity or "Company" in fidelity or "Notification" in fidelity
    for name in (
        "test_stage106_expense_scope_e1.py",
        "test_stage106_company_profile_c1.py",
        "test_stage106_notification_inbox_n1.py",
        "test_stage106_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-218" in fidelity or "ADR_218" in fidelity
    assert "H106x" in fidelity
    plan = _read("docs/STAGE_106_PLAN.md")
    assert "STAGE_106_FIDELITY.md" in plan
    for ws in ("E1", "C1", "N1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage106_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_106_FIDELITY.md" in br
    assert "Stage 106 D1" in br or "test_stage106_fidelity_d1.py" in br
    assert "Stage 106 E1" in br or "Stage 106 C1" in br or "Stage 106 N1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_106_FIDELITY.md" in fidelity_tail or "Stage 106 D1" in fidelity_tail


def test_stage106_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 106 D1" in api or "STAGE_106_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 106 D1" in deploy or "STAGE_106_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 106 D1" in sec or "STAGE_106_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage106_expense_scope_e1.py" in launch
    assert "test_stage106_company_profile_c1.py" in launch
    assert "test_stage106_notification_inbox_n1.py" in launch
    assert "test_stage106_fidelity_d1.py" in launch
    assert "STAGE_106_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Departments" in manual
        or "Unread" in manual
        or "Purchase Settings" in manual
        or "Company logo" in manual
        or "Notifications" in manual
    )


def test_stage106_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_106_FIDELITY.md" in pr and "test_stage106_fidelity_d1.py" in pr
    assert "Stage 106 D1" in pr and "Stage 106 E1" in pr and "Stage 106 C1" in pr and "Stage 106 N1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_106_FIDELITY.md" in roadmap and "Stage 106 D1" in roadmap
    assert "ADR_218_STAGE106_OPEN.md" in roadmap and "STAGE_106_PLAN.md" in roadmap
