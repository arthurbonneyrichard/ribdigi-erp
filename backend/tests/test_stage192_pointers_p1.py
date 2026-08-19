"""Stage 192 P1 — live DR pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-dr-pack-pointers.json"


def test_live_dr_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 192 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_dr_claimed"] is False
    assert data["live_backup_restore_claimed"] is False
    assert data["live_pitr_drill_claimed"] is False
    for topic in (
        "backup_drill_honesty_stage169",
        "e2e_backup_restore_stage35",
        "pitr_drill_pack",
        "hosted_faq_saas_remaining_gate_stage191",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lp-dr-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_dr_pack_pointers_doc_p1():
    doc = (ROOT / "docs/LIVE_DR_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "BACKUP_RESTORE_DRILL_HONESTY_MVP.md" in doc
    assert "E2E_BACKUP_RESTORE_MVP.md" in doc
    assert "PITR_DRILL_PACK_MVP.md" in doc
    assert "live_dr_claimed" in doc
