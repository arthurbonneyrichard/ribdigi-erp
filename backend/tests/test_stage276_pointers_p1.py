"""Stage 276 P1 — Hard delete pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "hard-delete-pack-rg-pointers.json"


def test_hard_delete_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 276 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["hard_delete_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "hard_delete_adr003",
        "menu_permissions_pack_remaining_gate_stage275",
        "language_i18n_pack_remaining_gate_stage274",
        "hard_delete_remaining_gate_stage183",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "hdprp-hard-delete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_hard_delete_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/HARD_DELETE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_003_USER_DELETE_POLICY.md" in doc
    assert "MENU_PERMISSIONS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "LANGUAGE_I18N_PACK_REMAINING_GATE_MVP.md" in doc
    assert "HARD_DELETE_REMAINING_GATE_MVP.md" in doc
    assert "hard_delete_complete_claimed" in doc
    assert "archival_complete_claimed" in doc
