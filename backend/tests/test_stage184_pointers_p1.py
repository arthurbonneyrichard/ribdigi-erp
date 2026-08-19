"""Stage 184 P1 — i18n pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "i18n-pack-pointers.json"


def test_i18n_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 184 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["i18n_packs_claimed"] is False
    assert data["multi_language_claimed"] is False
    assert data["non_english_switcher_claimed"] is False
    for topic in (
        "adr006_language_i18n",
        "deferred_adr_register",
        "i18n_scaffold",
        "hard_delete_remaining_gate_stage183",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ip-i18n-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_i18n_pack_pointers_doc_p1():
    doc = (ROOT / "docs/I18N_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_006_LANGUAGE_I18N.md" in doc
    assert "DEFERRED_ADR_REGISTER_MVP.md" in doc
    assert "frontend/lib/i18n.ts" in doc
    assert "i18n_packs_claimed" in doc
