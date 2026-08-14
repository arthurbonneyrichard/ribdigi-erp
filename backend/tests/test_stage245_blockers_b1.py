"""Stage 245 B1 — first-tenant go-live pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-golive-pack-rg-blockers.json"


def test_first_tenant_golive_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 245 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["first_paying_tenant_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["first_paying_tenant_delivery_execution"] == "REMAINING"
    assert blockers["go_live_complete"] == "REMAINING"
    assert blockers["stage66_t1_as_first_paying_tenant"] == "NON_CLAIM"
    assert blockers["stage66_t1_as_go_live"] == "NON_CLAIM"
    assert blockers["stage244_i1_as_go_live"] == "NON_CLAIM"
    assert blockers["first_paying_tenant_claimed"] == "false"
    assert blockers["go_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ftgprb-golive-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_golive_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/FIRST_TENANT_GOLIVE_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "first_paying_tenant_claimed" in doc
    assert "go_live_claimed" in doc
    assert "Stage 66" in doc
