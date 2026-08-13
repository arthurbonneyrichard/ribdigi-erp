"""Stage 170 V1 — incident severity matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "incident-severity-matrix.json"


def test_severity_matrix_register_v1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 170 and data["pack"] == "V1"
    assert data["pagerduty_hosted_claimed"] is False
    assert data["oncall_rota_live"] is False
    assert data["incident_drill_executed"] is False
    levels = {lvl["id"]: lvl for lvl in data["levels"]}
    assert set(levels) == {"P1", "P2", "P3", "P4"}
    assert levels["P1"]["ack_minutes"] == 15
    assert levels["P2"]["ack_minutes"] == 60
    assert any("sync" in e or "pos" in e for e in levels["P2"]["examples"])
    assert any("catalog" in e or "conflict" in e or "revoke" in e for e in levels["P3"]["examples"])
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_severity_matrix_doc_v1():
    doc = (ROOT / "docs/INCIDENT_SEVERITY_MATRIX_MVP.md").read_text(encoding="utf-8")
    assert "P1" in doc and "P4" in doc
    assert "offline" in doc.lower() or "sync" in doc.lower()
    incident = (ROOT / "docs/INCIDENT_PACK_MVP.md").read_text(encoding="utf-8")
    assert "INCIDENT_SEVERITY_MATRIX_MVP.md" in incident or "Stage 170 V1" in incident
