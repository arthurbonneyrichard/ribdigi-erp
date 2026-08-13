"""Stage 184 B1 — i18n blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "i18n-blockers.json"


def test_i18n_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 184 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["i18n_packs_claimed"] is False
    assert data["multi_language_claimed"] is False
    assert data["non_english_switcher_claimed"] is False
    assert data["english_as_i18n_complete_claimed"] is False
    blockers = data["blockers"]
    assert blockers["adr006_non_english_packs"] == "DEFERRED"
    assert blockers["multi_language_ui_switching"] == "REMAINING"
    assert blockers["fake_translation_packs"] == "BANNED"
    assert blockers["english_scaffold_as_i18n_complete"] == "NON_CLAIM"
    assert blockers["i18n_packs_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ib-i18n-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_i18n_blockers_doc_b1():
    doc = (ROOT / "docs/I18N_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR-006" in doc or "ADR_006" in doc
    assert "English" in doc or "english" in doc
    assert "i18n" in doc.lower()
    assert "i18n_packs_claimed" in doc
