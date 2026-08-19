"""Stage 170 S1 — support readiness packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "support-readiness.json"


def test_support_readiness_register_s1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 170 and data["pack"] == "S1"
    assert data["packaging_complete"] is True
    assert data["support_sla_claimed"] is False
    assert data["helpdesk_hosted_claimed"] is False
    assert data["oncall_rota_live"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["offline_complete_claimed"] is False
    assert all(s["done"] is False for s in data["steps"])
    assert any(s["id"] == "sr-live-remaining" and s["status"] == "remaining" for s in data["steps"])
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_support_readiness_doc_s1():
    doc = (ROOT / "docs/SUPPORT_READINESS_MVP.md").read_text(encoding="utf-8")
    assert "support_sla_claimed" in doc
    assert "OFFLINE_SYNC_RUNBOOK_MVP.md" in doc
    prior = (ROOT / "docs/SUPPORT_RUNBOOK_MVP.md").read_text(encoding="utf-8")
    assert "SUPPORT_READINESS_MVP.md" in prior or "Stage 170 S1" in prior
