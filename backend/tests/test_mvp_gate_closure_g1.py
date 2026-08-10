"""Stage 23 G1 — Commercial MVP gate closure (readiness honesty).

Gates whose Remaining work is explicitly post-MVP / deferred (ADR-001/002,
Open Banking, tax e-file, extra jurisdictions / FIFO-LIFO-WA) flip to Complete
(MVP) in PRODUCTION_READINESS.md. Ops DR drill evidence remains Stage 23 B1.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READINESS = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
PLAN = (ROOT / "docs" / "STAGE_23_PLAN.md").read_text(encoding="utf-8")


def _section(heading: str) -> str:
    start = READINESS.find(heading)
    assert start >= 0, f"missing heading {heading!r}"
    rest = READINESS[start:]
    nxt = rest.find("\n### ", 1)
    return rest if nxt < 0 else rest[:nxt]


def test_g1_plan_marks_complete() -> None:
    assert "| **G1** |" in PLAN
    assert "COMPLETE" in PLAN
    assert "test_mvp_gate_closure_g1.py" in PLAN
    assert (
        "G1 complete" in PLAN
        or "F1–C1–I1–G1 complete" in PLAN
        or "F1–C1–I1–G1–B1 complete" in PLAN
        or "F1–C1–I1–G1–B1–D1 complete" in PLAN
    )


def test_isolation_and_lifecycle_mvp_complete() -> None:
    assert "- [x] Cross-tenant isolation integration tests pass for every tenant-owned resource." in READINESS
    assert "Complete (shared-schema MVP)" in READINESS
    assert "Stage 23 G1" in READINESS
    assert "- [x] Tenant provisioning, suspension, activation and lifecycle management complete." in READINESS
    assert "Complete (MVP): register + defaults" in READINESS
    assert "ADR-002" in READINESS
    assert "schema-per-tenant (ADR-001)" in READINESS


def test_expenses_accounting_tax_reports_mvp_complete() -> None:
    sec = _section("### ERP operations")
    assert "- [x] Expenses and approval workflow complete." in sec
    assert "- [x] Double-entry accounting, journals, COA and financial statements complete." in sec
    assert "Complete (MVP): COA defaults" in sec
    assert "Open Banking" in sec  # Remaining post-MVP
    assert "- [x] VAT/tax calculation and reporting complete." in sec
    assert "Complete (MVP): tax types/modes" in sec
    assert "e-file" in sec
    assert "- [x] Reports and exports complete." in sec
    assert "Complete (MVP): sales/inventory/purchase" in sec
    assert "Stage 23 G1" in sec
    for label in (
        "- [ ] Expenses and approval workflow complete.",
        "- [ ] Double-entry accounting, journals, COA and financial statements complete.",
        "- [ ] VAT/tax calculation and reporting complete.",
        "- [ ] Reports and exports complete.",
    ):
        assert label not in sec


def test_deferred_ops_remain_open_or_partial() -> None:
    """G1 must not fake-complete ops items that remain post-MVP / still Partial."""
    assert "- [ ] Point-in-time recovery/WAL strategy complete." in READINESS
    assert "Partial" in READINESS  # inventory / sales / purchasing / ops still Partial
    assert "WAL" in READINESS or "PITR" in READINESS
