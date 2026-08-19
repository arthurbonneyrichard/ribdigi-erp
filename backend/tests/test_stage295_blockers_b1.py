"""Stage 295 B1 — Commercial support pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-support-pack-rg-blockers.json"


def test_commercial_support_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 295 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["commercial_support_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["commercial_support_claimed"] == "REMAINING"
    assert blockers["support_boundary_live_claimed"] == "REMAINING"
    assert blockers["support_sla_claimed"] == "REMAINING"
    assert blockers["status_page_live"] == "REMAINING"
    assert blockers["stage74_as_commercial_support"] == "NON_CLAIM"
    assert blockers["commercial_support_claimed_flag"] == "false"
    assert blockers["support_sla_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "csprb-support-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_support_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/COMMERCIAL_SUPPORT_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "commercial_support_claimed" in doc
    assert "support_sla_claimed" in doc
    assert "Stage 74" in doc
