"""Stage 314 I1 — SBOM disclosure pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "sbom-disclosure-pack-remaining-gate.json"


def test_sbom_disclosure_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 314 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["sbom_pipeline_live"] is False
    assert data["cosign_signing_claimed"] is False
    assert data["snyk_saas_claimed"] is False
    assert data["dependabot_live"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage40_sbom_disclosure"] is True
    assert data["distinct_from_stage313_commercial_liability_pack_remaining_gate"] is True
    assert data["distinct_from_stage312_status_uptime_pack_remaining_gate"] is True
    assert data["distinct_from_stage38_vuln_disclosure_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sdpr-pipeline-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_sbom_disclosure_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/SBOM_DISCLOSURE_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "sbom_pipeline_live" in doc
    assert "cosign_signing_claimed" in doc
    assert "SBOM_DISCLOSURE_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "SBOM_DISCLOSURE_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 40" in doc
    assert "SBOM_DISCLOSURE_MVP.md" in doc
