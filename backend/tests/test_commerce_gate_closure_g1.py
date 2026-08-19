"""Stage 24 G1 — Commerce surface gate closure (readiness honesty).

Inventory, Purchasing, Sales, POS, and Multi-store flip to Complete (MVP) where
Remaining is deferred-only (Kanban polish, vendor USB/serial, multi-bin, ADR-005).
Ops Redis/Celery + AI honesty remain Stage 24 O1; WAL/K8s/monitoring stay open.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READINESS = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
PLAN = (ROOT / "docs" / "STAGE_24_PLAN.md").read_text(encoding="utf-8")


def _section(heading: str) -> str:
    start = READINESS.find(heading)
    assert start >= 0, f"missing heading {heading!r}"
    rest = READINESS[start:]
    nxt = rest.find("\n### ", 1)
    return rest if nxt < 0 else rest[:nxt]


def test_g1_plan_marks_complete() -> None:
    assert "| **G1** |" in PLAN
    g1_line = [ln for ln in PLAN.splitlines() if "| **G1** |" in ln][0]
    assert "COMPLETE" in g1_line
    assert "test_commerce_gate_closure_g1.py" in PLAN
    assert (
        "G1 complete" in PLAN
        or "O1 next" in PLAN
        or "N1–G1–O1 complete" in PLAN
        or "N1–G1–O1–D1 complete" in PLAN
        or "D1 next" in PLAN
        or "H24x next" in PLAN
        or "Closed" in PLAN
        or "exit met" in PLAN.lower()
        or "ADR-054" in PLAN
    )


def test_commerce_gates_mvp_complete() -> None:
    sec = _section("### ERP operations")
    assert "- [x] Inventory catalog, variants, batches/expiry, stock movements and adjustments complete." in sec
    assert "Complete (MVP):" in sec
    assert "Stage 24 G1" in sec
    assert "test_commerce_gate_closure_g1.py" in sec
    assert "- [x] Purchasing/PO/GRN/supplier workflow complete." in sec
    assert "PO Kanban" in sec
    assert "- [x] Sales/invoice/payment/customer workflow complete." in sec
    assert "- [x] POS cart, barcode, payment, receipt, shift and stock deduction complete." in sec
    assert "USB/serial" in sec or "vendor-specific" in sec
    assert "- [x] Multi-store/warehouse inventory and transfer workflow complete." in sec
    assert "ADR-005" in sec or "multi-bin" in sec
    for label in (
        "- [ ] Inventory catalog, variants, batches/expiry, stock movements and adjustments complete.",
        "- [ ] Purchasing/PO/GRN/supplier workflow complete.",
        "- [ ] Sales/invoice/payment/customer workflow complete.",
        "- [ ] POS cart, barcode, payment, receipt, shift and stock deduction complete.",
        "- [ ] Multi-store/warehouse inventory and transfer workflow complete.",
    ):
        assert label not in sec


def test_ops_platform_gates_not_fake_completed() -> None:
    """G1 must not close post-MVP ops platform gates (K8s / load)."""
    assert (
        "- [ ] Point-in-time recovery/WAL strategy complete." in READINESS
        or (
            "- [x] Point-in-time recovery/WAL strategy complete." in READINESS
            and "Stage 26 W1" in READINESS
        )
    )
    assert (
        "- [ ] Kubernetes production deployment reviewed." in READINESS
        or (
            "- [x] Kubernetes production deployment reviewed." in READINESS
            and "Stage 26 K1" in READINESS
        )
    )
    assert (
        "- [ ] Load/performance tests meet documented targets." in READINESS
        or (
            "- [x] Load/performance tests meet documented targets." in READINESS
            and "Stage 26 C1" in READINESS
        )
    )
    # Stage 26 M1–C1 may mark ops gates Complete (MVP); G1 must not be the closer.
    assert "Partial" in READINESS or "Remaining" in READINESS
