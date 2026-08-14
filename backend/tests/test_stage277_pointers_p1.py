"""Stage 277 P1 — Soft-delete erasure pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "soft-delete-erasure-pack-rg-pointers.json"


def test_soft_delete_erasure_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 277 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["erasure_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "erasure_honesty_stage37",
        "hard_delete_adr003",
        "hard_delete_pack_remaining_gate_stage276",
        "menu_permissions_pack_remaining_gate_stage275",
        "hard_delete_remaining_gate_stage183",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sdeprp-erasure-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_soft_delete_erasure_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SOFT_DELETE_ERASURE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ERASURE_HONESTY_MVP.md" in doc
    assert "ADR_003_USER_DELETE_POLICY.md" in doc
    assert "HARD_DELETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "MENU_PERMISSIONS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "HARD_DELETE_REMAINING_GATE_MVP.md" in doc
    assert "erasure_complete_claimed" in doc
    assert "hard_delete_complete_claimed" in doc
