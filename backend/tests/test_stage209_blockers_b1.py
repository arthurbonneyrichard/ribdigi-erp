"""Stage 209 B1 — pentest blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pentest-blockers.json"


def test_pentest_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 209 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["vendor_pen_test_purchased"] is False
    assert data["live_zap_executed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["purchased_vendor_pen_test_execution"] == "REMAINING"
    assert blockers["live_authenticated_staging_zap"] == "REMAINING"
    assert blockers["stage29_v1_as_live_pentest"] == "NON_CLAIM"
    assert blockers["vendor_pen_test_purchased"] == "false"
    assert blockers["live_zap_executed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pb-pentest-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pentest_blockers_doc_b1():
    doc = (ROOT / "docs/PENTEST_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "vendor_pen_test_purchased" in doc
    assert "Stage 29" in doc
    assert "live_zap_executed" in doc
