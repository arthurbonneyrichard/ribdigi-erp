"""Stage 215 P1 — knowledge base RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "knowledge-base-rg-pointers.json"


def test_knowledge_base_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 215 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_knowledge_base_claimed"] is False
    assert data["hosted_kb_saas_claimed"] is False
    for topic in (
        "knowledge_base_stage171_k1",
        "faq_offline_pos",
        "troubleshooting_index",
        "support_runbook_remaining_gate_stage214",
        "hosted_faq_saas_remaining_gate_stage191",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "kbp-saas-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_knowledge_base_rg_pointers_doc_p1():
    doc = (ROOT / "docs/KNOWLEDGE_BASE_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "KNOWLEDGE_BASE_MVP.md" in doc
    assert "SUPPORT_RUNBOOK_REMAINING_GATE_MVP.md" in doc
    assert "HOSTED_FAQ_SAAS_REMAINING_GATE_MVP.md" in doc
    assert "live_knowledge_base_claimed" in doc
