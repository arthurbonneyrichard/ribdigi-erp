"""Stage 314 P1 — SBOM disclosure pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "sbom-disclosure-pack-rg-pointers.json"


def test_sbom_disclosure_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 314 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["sbom_pipeline_live"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "sbom_disclosure_stage40",
        "commercial_liability_pack_remaining_gate_stage313",
        "status_uptime_pack_remaining_gate_stage312",
        "vuln_disclosure_pack_remaining_gate_stage38",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sdprp-pipeline-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_sbom_disclosure_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SBOM_DISCLOSURE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SBOM_DISCLOSURE_MVP.md" in doc
    assert "COMMERCIAL_LIABILITY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "STATUS_UPTIME_PACK_REMAINING_GATE_MVP.md" in doc
    assert "VULN_DISCLOSURE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "sbom_pipeline_live" in doc
    assert "cosign_signing_claimed" in doc
