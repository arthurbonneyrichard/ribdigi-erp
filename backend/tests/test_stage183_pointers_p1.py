"""Stage 183 P1 — hard-delete pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "hard-delete-pack-pointers.json"


def test_hard_delete_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 183 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["hard_delete_claimed"] is False
    assert data["hard_delete_api_claimed"] is False
    assert data["archival_complete_claimed"] is False
    for topic in (
        "adr003_user_delete_policy",
        "erasure_honesty",
        "deferred_adr_register",
        "membership_remaining_gate_stage182",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "hp-hard-delete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_hard_delete_pack_pointers_doc_p1():
    doc = (ROOT / "docs/HARD_DELETE_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_003_USER_DELETE_POLICY.md" in doc
    assert "ERASURE_HONESTY_MVP.md" in doc
    assert "DEFERRED_ADR_REGISTER_MVP.md" in doc
    assert "hard_delete_claimed" in doc
