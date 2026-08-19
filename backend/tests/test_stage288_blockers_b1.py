"""Stage 288 B1 — Cyber insurance pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cyber-insurance-pack-rg-blockers.json"


def test_cyber_insurance_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 288 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["coi_issued_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["coi_issued"] == "REMAINING"
    assert blockers["cyber_insurance_live"] == "REMAINING"
    assert blockers["insurance_certificate"] == "REMAINING"
    assert blockers["broker_attestation"] == "REMAINING"
    assert blockers["stage47_as_coi_issued"] == "NON_CLAIM"
    assert blockers["coi_issued_claimed"] == "false"
    assert blockers["insurance_certificate_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ciprb-coi-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cyber_insurance_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/CYBER_INSURANCE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "coi_issued_claimed" in doc
    assert "cyber_insurance_live" in doc
    assert "Stage 47" in doc
