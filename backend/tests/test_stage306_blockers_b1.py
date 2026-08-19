"""Stage 306 B1 — data residency pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-residency-pack-rg-blockers.json"


def test_data_residency_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 306 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["multi_region_residency_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["multi_region_residency_claimed"] == "REMAINING"
    assert blockers["schema_per_tenant_claimed"] == "REMAINING"
    assert blockers["gdpr_residency_cert_claimed"] == "REMAINING"
    assert blockers["customer_region_pinning_live"] == "REMAINING"
    assert blockers["stage44_as_multi_region"] == "NON_CLAIM"
    assert blockers["multi_region_residency_claimed_flag"] == "false"
    assert blockers["schema_per_tenant_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "drprb-residency-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_data_residency_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/DATA_RESIDENCY_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "multi_region_residency_claimed" in doc
    assert "schema_per_tenant_claimed" in doc
    assert "Stage 44" in doc
