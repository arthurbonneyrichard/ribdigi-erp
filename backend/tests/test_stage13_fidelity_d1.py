"""Stage 13 D1 — documentation fidelity for POS execution chain (H1/H2)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage13_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_13_FIDELITY.md")
    assert "INSUFFICIENT_STOCK" in fidelity
    assert "pos_receipt_sent" in fidelity
    assert "has_cash_tender" in fidelity or "cash tender" in fidelity.lower()
    assert "H1" in fidelity and "H2" in fidelity
    assert "test_pos_sale_atomicity_h1.py" in fidelity
    assert "test_pos_execution_chain_h2.py" in fidelity

    plan = _read("docs/STAGE_13_PLAN.md")
    assert "| **D1**" in plan and "COMPLETE" in plan
    assert "STAGE_13_FIDELITY.md" in plan
    assert "| **H1**" in plan and "COMPLETE" in plan
    assert "| **H2**" in plan and "COMPLETE" in plan


def test_stage13_api_docs_pos_routes():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "POST /pos/sales" in api
    assert "INSUFFICIENT_STOCK" in api
    assert "/pos/sales/{sale_id}/receipt/send" in api
    assert "pos_receipt_sent" in api
    assert "format=json|text|pdf" in api
    assert "drawer/open" in api
    # Legacy wrong receipt query must not remain
    assert "template=thermal" not in api


def test_stage13_br_launch_and_manual():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 13 H1" in br
    assert "Stage 13 H2" in br
    assert "pos_receipt_sent" in br
    assert "POS transaction submission (Stage 12 C2 / Stage 13 H1–H2" in br

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_pos_sale_atomicity_h1.py" in launch
    assert "test_pos_execution_chain_h2.py" in launch

    manual = _read("docs/USER_MANUAL.md")
    assert "INSUFFICIENT_STOCK" in manual
    assert "pos_receipt_sent" in manual


def test_stage13_readiness_mentions_delivered_work():
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 13 H1/H2" in pr or "ADR-031" in pr
    assert "STAGE_13_FIDELITY.md" in pr
    assert "pos_receipt_sent" in pr
