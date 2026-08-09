"""Stage 9 D1 — documentation fidelity for J1/R1/R2 (no false COMPLETE claims)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage9_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_9_FIDELITY.md")
    assert "standard cost" in fidelity.lower()
    assert "FIFO" in fidelity
    assert "not claimed" in fidelity.lower() or "Explicitly not claimed" in fidelity
    assert "J1" in fidelity and "R1" in fidelity and "R2" in fidelity

    plan = _read("docs/STAGE_9_PLAN.md")
    assert "| **D1**" in plan and "COMPLETE" in plan
    assert "STAGE_9_FIDELITY.md" in plan
    # H9x must still be pending until exit freeze
    assert "| **H9x**" in plan
    assert "PENDING" in plan


def test_stage9_api_docs_match_live_routes():
    api = _read("docs/API_DOCUMENTATION.md")
    for token in (
        "/accounting/journal-entries/{entry_id}/attachment",
        "/reports/purchases/pending-orders",
        "/reports/purchases/returns",
        "/reports/inventory/valuation",
        "/purchasing/returns",
        "standard_cost",
    ):
        assert token in api, token
    # Legacy wrong purchasing prefix must not remain for module CRUD
    assert "GET /purchases/returns" not in api
    assert "GET /purchases/orders" not in api


def test_stage9_br_and_user_manual_costing_language():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Attach supporting documents (Stage 9 J1)" in br
    assert "Stage 9 R1" in br
    assert "Stage 9 R2" in br
    assert "FIFO/LIFO/WA deferred" in br

    manual = _read("docs/USER_MANUAL.md")
    assert "standard cost" in manual.lower()
    assert "FIFO/LIFO" in manual or "FIFO/LIFO/weighted-average" in manual
    # Must not claim historical layers survive cost changes
    assert "does not affect existing stock valuation" not in manual

    dbdoc = _read("docs/DATABASE_DOCUMENTATION.md")
    assert "attachment_url" in dbdoc
    assert "source_type" in dbdoc


def test_stage9_readiness_mentions_delivered_work():
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 9 J1" in pr or "journal supporting documents" in pr
    assert "pending-orders" in pr or "pending POs" in pr
    assert "inventory/valuation" in pr or "stock valuation" in pr.lower()
    assert "STAGE_9_FIDELITY.md" in pr
