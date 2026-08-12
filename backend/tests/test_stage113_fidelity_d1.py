"""Stage 113 D1 — documentation fidelity for Notification Read, Cheque Exceptions & Fulfillment Status Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage113_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_113_FIDELITY.md")
    assert "Notification" in fidelity or "Cheque" in fidelity or "Fulfillment" in fidelity
    for name in (
        "test_stage113_notification_read_n1.py",
        "test_stage113_cheque_exceptions_c1.py",
        "test_stage113_fulfillment_status_s1.py",
        "test_stage113_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-232" in fidelity or "ADR_232" in fidelity
    assert "H113x" in fidelity
    plan = _read("docs/STAGE_113_PLAN.md")
    assert "STAGE_113_FIDELITY.md" in plan
    for ws in ("N1", "C1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage113_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_113_FIDELITY.md" in br
    assert "Stage 113 D1" in br or "test_stage113_fidelity_d1.py" in br
    assert "Stage 113 N1" in br or "Stage 113 C1" in br or "Stage 113 S1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_113_FIDELITY.md" in fidelity_tail or "Stage 113 D1" in fidelity_tail


def test_stage113_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 113 D1" in api or "STAGE_113_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 113 D1" in deploy or "STAGE_113_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 113 D1" in sec or "STAGE_113_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage113_notification_read_n1.py" in launch
    assert "test_stage113_cheque_exceptions_c1.py" in launch
    assert "test_stage113_fulfillment_status_s1.py" in launch
    assert "test_stage113_fidelity_d1.py" in launch
    assert "STAGE_113_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Read Notifications" in manual
        or "Bounced Cheques" in manual
        or "Shipped Orders" in manual
        or "Paid Invoices" in manual
        or "In-transit Transfers" in manual
    )


def test_stage113_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_113_FIDELITY.md" in pr and "test_stage113_fidelity_d1.py" in pr
    assert "Stage 113 D1" in pr and "Stage 113 N1" in pr and "Stage 113 C1" in pr and "Stage 113 S1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_113_FIDELITY.md" in roadmap and "Stage 113 D1" in roadmap
    assert "ADR_232_STAGE113_OPEN.md" in roadmap and "STAGE_113_PLAN.md" in roadmap
