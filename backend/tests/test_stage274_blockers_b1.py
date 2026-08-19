"""Stage 274 B1 — Language i18n pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "language-i18n-pack-rg-blockers.json"


def test_language_i18n_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 274 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["multilang_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["multilang_complete"] == "REMAINING"
    assert blockers["non_english_packs_complete"] == "REMAINING"
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["adr006_as_multilang_complete"] == "NON_CLAIM"
    assert blockers["multilang_complete_claimed"] == "false"
    assert blockers["non_english_packs_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "liprb-multilang-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_language_i18n_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/LANGUAGE_I18N_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "multilang_complete_claimed" in doc
    assert "non_english_packs_claimed" in doc
    assert "ADR-006" in doc or "ADR_006" in doc
