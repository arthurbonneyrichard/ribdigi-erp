"""Stage 215 B1 — knowledge base blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "knowledge-base-blockers.json"


def test_knowledge_base_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 215 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_knowledge_base_claimed"] is False
    assert data["hosted_kb_saas_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["hosted_faq_helpdesk_portal_saas"] == "REMAINING"
    assert blockers["public_knowledge_base_portal"] == "REMAINING"
    assert blockers["stage171_k1_as_hosted_faq_saas"] == "NON_CLAIM"
    assert blockers["hosted_kb_saas_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "kbb-saas-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_knowledge_base_blockers_doc_b1():
    doc = (ROOT / "docs/KNOWLEDGE_BASE_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "hosted_kb_saas_claimed" in doc
    assert "Stage 171" in doc
