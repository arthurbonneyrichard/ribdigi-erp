"""Stage 172 Q1 — cashier quickstart hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cashier-quickstart.json"


def test_cashier_quickstart_register_q1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 172 and data["pack"] == "Q1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["live_training_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["distinct_from_stage171_faq_kb"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cq-offline-complete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cashier_quickstart_doc_q1():
    doc = (ROOT / "docs/CASHIER_QUICKSTART_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "CASHIER_BIND_CATALOG_MVP.md" in doc
    assert "CASHIER_POS_DAYONE_MVP.md" in doc
    assert "Stage 171" in doc
