"""Stage 333 B1 — support readiness pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "support-readiness-pack-rg-blockers.json"


def test_support_readiness_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 333 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["support_sla_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["support_sla_claimed"] == "REMAINING"
    assert blockers["helpdesk_hosted_claimed"] == "REMAINING"
    assert blockers["oncall_rota_live"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["attestation_claimed"] == "REMAINING"
    assert blockers["stage170_as_live_support_readiness"] == "NON_CLAIM"
    assert blockers["support_sla_claimed_flag"] == "false"
    assert blockers["helpdesk_hosted_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "srprb-readiness-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_support_readiness_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/SUPPORT_READINESS_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "support_sla_claimed" in doc
    assert "helpdesk_hosted_claimed" in doc
    assert "Stage 170" in doc
