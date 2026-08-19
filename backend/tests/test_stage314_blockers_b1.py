"""Stage 314 B1 — SBOM disclosure pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "sbom-disclosure-pack-rg-blockers.json"


def test_sbom_disclosure_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 314 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["sbom_pipeline_live"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["sbom_pipeline_live"] == "REMAINING"
    assert blockers["cosign_signing_claimed"] == "REMAINING"
    assert blockers["snyk_saas_claimed"] == "REMAINING"
    assert blockers["dependabot_live"] == "REMAINING"
    assert blockers["stage40_as_sbom_pipeline"] == "NON_CLAIM"
    assert blockers["sbom_pipeline_live_flag"] == "false"
    assert blockers["cosign_signing_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sdprb-pipeline-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_sbom_disclosure_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/SBOM_DISCLOSURE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "sbom_pipeline_live" in doc
    assert "cosign_signing_claimed" in doc
    assert "Stage 40" in doc
