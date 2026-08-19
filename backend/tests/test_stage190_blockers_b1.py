"""Stage 190 B1 — offline materials blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-materials-blockers.json"


def test_offline_materials_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 190 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["browser_e2e_claimed"] is False
    blockers = data["blockers"]
    assert blockers["offline_complete_product_claim"] == "REMAINING"
    assert blockers["playwright_offline_e2e"] == "REMAINING"
    assert blockers["stage171_faq_as_offline_complete"] == "NON_CLAIM"
    assert blockers["stages172_175_checklists_as_offline_complete"] == "NON_CLAIM"
    assert blockers["stage179_gate_as_offline_complete"] == "NON_CLAIM"
    assert blockers["offline_complete_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ob-offline-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_materials_blockers_doc_b1():
    doc = (ROOT / "docs/OFFLINE_MATERIALS_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "Stage 171" in doc
    assert "Playwright" in doc or "playwright" in doc.lower()
