"""Stage 132 D1 — documentation fidelity for Sales/Purchase invoices & Stock Transfers Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage132_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_132_FIDELITY.md")
    assert (
        "invoice" in fidelity.lower()
        or "transfer" in fidelity.lower()
        or "purchase" in fidelity.lower()
    )
    for name in (
        "test_stage132_sales_invoices_export_i1.py",
        "test_stage132_stock_transfers_t1.py",
        "test_stage132_purchase_invoices_export_p1.py",
        "test_stage132_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-270" in fidelity or "ADR_270" in fidelity
    assert "H132x" in fidelity
    plan = _read("docs/STAGE_132_PLAN.md")
    assert "STAGE_132_FIDELITY.md" in plan
    for ws in ("I1", "T1", "P1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage132_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_132_FIDELITY.md" in br
    assert "Stage 132 D1" in br or "test_stage132_fidelity_d1.py" in br
    assert "Stage 132 I1" in br or "Stage 132 T1" in br or "Stage 132 P1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_132_FIDELITY.md" in fidelity_tail or "Stage 132 D1" in fidelity_tail


def test_stage132_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 132 D1" in api or "STAGE_132_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 132 D1" in deploy or "STAGE_132_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 132 D1" in sec or "STAGE_132_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage132_sales_invoices_export_i1.py" in launch
    assert "test_stage132_stock_transfers_t1.py" in launch
    assert "test_stage132_purchase_invoices_export_p1.py" in launch
    assert "test_stage132_fidelity_d1.py" in launch
    assert "STAGE_132_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Sales Invoice" in manual
        or "sales/invoices/export" in manual
        or "Purchase Invoice" in manual
        or "purchasing/invoices/export" in manual
        or "Stock Transfer" in manual
        or "stock-transfers/export" in manual
    )


def test_stage132_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_132_FIDELITY.md" in pr and "test_stage132_fidelity_d1.py" in pr
    assert "Stage 132 D1" in pr and "Stage 132 I1" in pr and "Stage 132 T1" in pr and "Stage 132 P1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_132_FIDELITY.md" in roadmap and "Stage 132 D1" in roadmap
    assert "ADR_270_STAGE132_OPEN.md" in roadmap and "STAGE_132_PLAN.md" in roadmap
