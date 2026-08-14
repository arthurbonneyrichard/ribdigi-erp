"""Stage 255 B1 — commercial residual pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-residual-pack-rg-blockers.json"


def test_commercial_residual_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 255 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["residual_closed_claimed"] is False
    assert data["packaging_archive_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["residual_closed_complete"] == "REMAINING"
    assert blockers["packaging_archive_live_complete"] == "REMAINING"
    assert blockers["commercial_acceptance_complete"] == "REMAINING"
    assert blockers["stage72_r1_as_residual_closed"] == "NON_CLAIM"
    assert blockers["residual_closed_claimed"] == "false"
    assert blockers["packaging_archive_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "crprb-residual-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_residual_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/COMMERCIAL_RESIDUAL_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "residual_closed_claimed" in doc
    assert "packaging_archive_live_claimed" in doc
    assert "Stage 72" in doc
