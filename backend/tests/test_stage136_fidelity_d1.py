"""Stage 136 D1 — documentation fidelity for payment register & aging export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage136_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_136_FIDELITY.md")
    assert (
        "payment" in fidelity.lower()
        or "aging" in fidelity.lower()
        or "customer" in fidelity.lower()
    )
    for name in (
        "test_stage136_customer_payments_c1.py",
        "test_stage136_supplier_payments_s1.py",
        "test_stage136_aging_export_a1.py",
        "test_stage136_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-278" in fidelity or "ADR_278" in fidelity
    assert "H136x" in fidelity
    plan = _read("docs/STAGE_136_PLAN.md")
    assert "STAGE_136_FIDELITY.md" in plan
    for ws in ("C1", "S1", "A1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage136_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_136_FIDELITY.md" in br
    assert "Stage 136 D1" in br or "test_stage136_fidelity_d1.py" in br
    assert "Stage 136 C1" in br or "Stage 136 S1" in br or "Stage 136 A1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_136_FIDELITY.md" in fidelity_tail or "Stage 136 D1" in fidelity_tail


def test_stage136_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 136 D1" in api or "STAGE_136_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 136 D1" in deploy or "STAGE_136_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 136 D1" in sec or "STAGE_136_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage136_customer_payments_c1.py" in launch
    assert "test_stage136_supplier_payments_s1.py" in launch
    assert "test_stage136_aging_export_a1.py" in launch
    assert "test_stage136_fidelity_d1.py" in launch
    assert "STAGE_136_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Customer Payment" in manual
        or "customer-payments" in manual
        or "Supplier Payment" in manual
        or "supplier-payments" in manual
        or "aging/export" in manual
        or "Aging CSV" in manual
    )


def test_stage136_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_136_FIDELITY.md" in pr and "test_stage136_fidelity_d1.py" in pr
    assert "Stage 136 D1" in pr and "Stage 136 C1" in pr and "Stage 136 S1" in pr and "Stage 136 A1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_136_FIDELITY.md" in roadmap and "Stage 136 D1" in roadmap
    assert "ADR_278_STAGE136_OPEN.md" in roadmap and "STAGE_136_PLAN.md" in roadmap
