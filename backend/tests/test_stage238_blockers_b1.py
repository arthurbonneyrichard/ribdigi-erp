"""Stage 238 B1 — knowledge base pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "knowledge-base-pack-rg-blockers.json"


def test_knowledge_base_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 238 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_knowledge_base_claimed"] is False
    assert data["hosted_kb_saas_claimed"] is False
    assert data["live_training_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_hosted_knowledge_base_portal"] == "REMAINING"
    assert blockers["hosted_faq_saas"] == "REMAINING"
    assert blockers["stage171_k1_as_live_knowledge_base"] == "NON_CLAIM"
    assert blockers["stage33_t1_as_live_knowledge_base"] == "NON_CLAIM"
    assert blockers["live_knowledge_base_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "kbprb-kb-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_knowledge_base_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/KNOWLEDGE_BASE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_knowledge_base_claimed" in doc
    assert "Stage 171" in doc
