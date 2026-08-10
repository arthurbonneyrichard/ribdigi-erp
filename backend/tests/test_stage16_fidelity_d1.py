"""Stage 16 D1 — documentation fidelity for Multi-Store / Reports / Notifications."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage16_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_16_FIDELITY.md")
    assert "BR-13" in fidelity and "BR-14" in fidelity and "BR-15" in fidelity
    assert "INSUFFICIENT_WAREHOUSE_STOCK" in fidelity
    assert "transfer_history" in fidelity
    assert "test_multistore_transfer_chain_m1.py" in fidelity
    assert "test_notification_emission_n1.py" in fidelity
    assert "test_reports_suite_r1.py" in fidelity
    assert "test_credit_tax_reports_r2.py" in fidelity
    assert "test_transfer_history_m2.py" in fidelity
    assert "test_notification_channel_delivery_n2.py" in fidelity
    assert "test_stage16_fidelity_d1.py" in fidelity
    assert "ADR-005" in fidelity or "multi-bin" in fidelity.lower()
    assert "WebSocket" in fidelity

    plan = _read("docs/STAGE_16_PLAN.md")
    assert "| **D1**" in plan and "COMPLETE" in plan
    assert "STAGE_16_FIDELITY.md" in plan
    for ws in ("M1", "N1", "R1", "R2", "M2", "N2", "D1"):
        assert f"| **{ws}**" in plan
    assert "COMPLETE" in plan
    assert "| **H16x**" in plan and "PENDING" in plan
    assert "Pending H16x" in plan or "pending H16x" in plan.lower()


def test_stage16_br_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 16 M1" in br
    assert "Stage 16 M2" in br
    assert "Stage 16 N1" in br
    assert "Stage 16 N2" in br
    assert "Stage 16 R1" in br
    assert "[x] Create stores with unique code, name, location" in br
    assert "[x] Store-specific inventory view" in br
    assert "[x] Auto-update inventory at both stores on receipt confirmation" in br
    assert "[x] Transfer history and reporting" in br
    assert "ADR-005" in br  # staff membership Partial
    assert "[x] **Low Stock:**" in br
    assert "[x] **New Orders:**" in br
    assert "[x] **Credit Limit Reached:**" in br
    assert "[x] **Shift Variance:**" in br
    assert "[x] **Expense Approval Required:**" in br
    assert "[x] **Email:**" in br
    assert "[x] **SMS:**" in br
    assert "Partial: date on sales" in br or "balance sheet store/branch filters deferred" in br


def test_stage16_api_manual_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 16 M1" in api
    assert "Stage 16 M2" in api
    assert "Stage 16 N2" in api
    assert "INSUFFICIENT_WAREHOUSE_STOCK" in api
    assert "transfer_history" in api
    assert "mode=console" in api

    manual = _read("docs/USER_MANUAL.md")
    assert "STAGE_16_FIDELITY.md" in manual
    assert "Stage 16 N1" in manual or "Stage 16 N2" in manual
    assert "Reports → Transfers" in manual
    assert "reject with reason" not in manual.lower()
    assert "side-by-side store comparison" not in manual.lower()
    assert "Cancels" in manual or "Cancel" in manual

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_multistore_transfer_chain_m1.py" in launch
    assert "test_notification_emission_n1.py" in launch
    assert "test_reports_suite_r1.py" in launch
    assert "test_credit_tax_reports_r2.py" in launch
    assert "test_transfer_history_m2.py" in launch
    assert "test_notification_channel_delivery_n2.py" in launch
    assert "test_stage16_fidelity_d1.py" in launch
    assert "STAGE_16_FIDELITY.md" in launch


def test_stage16_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_16_FIDELITY.md" in pr
    assert "test_stage16_fidelity_d1.py" in pr
    assert "test_multistore_transfer_chain_m1.py" in pr
    assert "test_notification_channel_delivery_n2.py" in pr
    assert "N2/D1/H16x" not in pr  # N2 no longer listed as remaining open fidelity WS
    assert "H16x" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_16_FIDELITY.md" in roadmap
    assert "Stage 16 D1" in roadmap
    assert "ADR_037_STAGE16_OPEN.md" in roadmap
    assert "STAGE_16_PLAN.md" in roadmap
