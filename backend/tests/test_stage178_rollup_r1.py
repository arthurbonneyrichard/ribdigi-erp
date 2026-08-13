"""Stage 178 R1 — quarterly monthly outcomes rollup packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "quarterly-pos-ops-rollup.json"


def test_quarterly_pos_ops_rollup_register_r1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 178 and data["pack"] == "R1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    for topic in (
        "monthly_m1_t1_p1_summary",
        "hold_conflict_themes",
        "device_backup_residual_followthrough",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "qo-offline-golive-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_quarterly_pos_ops_rollup_doc_r1():
    doc = (ROOT / "docs/QUARTERLY_POS_OPS_ROLLUP_MVP.md").read_text(encoding="utf-8")
    assert "MONTHLY_POS_OPS_REVIEW_MVP.md" in doc
    assert "MONTHLY_POS_OPS_TRENDS_MVP.md" in doc
    assert "MONTHLY_POS_OPS_POINTERS_MVP.md" in doc
    assert "offline_complete_claimed" in doc
