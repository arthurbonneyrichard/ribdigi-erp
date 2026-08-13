"""Stage 183 B1 — hard-delete blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "hard-delete-blockers.json"


def test_hard_delete_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 183 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["hard_delete_claimed"] is False
    assert data["hard_delete_api_claimed"] is False
    assert data["archival_complete_claimed"] is False
    assert data["soft_delete_as_hard_delete_claimed"] is False
    blockers = data["blockers"]
    assert blockers["adr003_hard_delete"] == "DEFERRED"
    assert blockers["hard_delete_api"] == "REMAINING"
    assert blockers["data_archival_anonymize"] == "REMAINING"
    assert blockers["soft_delete_as_hard_delete"] == "NON_CLAIM"
    assert blockers["hard_delete_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "hb-hard-delete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_hard_delete_blockers_doc_b1():
    doc = (ROOT / "docs/HARD_DELETE_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR-003" in doc or "ADR_003" in doc
    assert "hard-delete" in doc.lower() or "hard_delete" in doc
    assert "archival" in doc.lower() or "anonymize" in doc.lower()
    assert "soft-delete" in doc.lower() or "soft_delete" in doc
    assert "hard_delete_claimed" in doc
