"""Stage 205 P1 — staging GHA pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "staging-gha-pack-pointers.json"


def test_staging_gha_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 205 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_staging_apply_claimed"] is False
    assert data["gha_staging_wired_into_main_ci"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "staging_gha_stage28",
        "deploy_free_ci_stage18",
        "k8s_deploy_stage26",
        "launch_cert_remaining_gate_stage204",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sp-apply-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_staging_gha_pack_pointers_doc_p1():
    doc = (ROOT / "docs/STAGING_GHA_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "STAGING_GHA_MVP.md" in doc
    assert "ci.yml" in doc
    assert "LAUNCH_CERT_REMAINING_GATE_MVP.md" in doc
    assert "live_staging_apply_claimed" in doc
