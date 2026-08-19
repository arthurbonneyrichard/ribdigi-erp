"""Stage 33 C1 — compliance readiness (not SOC 2 / ISO certification Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "compliance-readiness-register.json"
REMAINING = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
RESIDUAL = ROOT / "ops" / "mvp" / "residual-risk-register.json"
GATE = ROOT / "ops" / "mvp" / "gate-matrix.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage33_c1_compliance_readiness.json"

REQUIRED_IDS = {
    "cr-access-control",
    "cr-audit-logging",
    "cr-encryption-tls",
    "cr-vulnerability",
    "cr-incident",
    "cr-backup-dr",
    "cr-monitoring",
    "cr-change-ci",
    "cr-privacy",
    "cr-attestation",
    "cr-residual-risk",
}
REQUIRED_THEMES = {
    "access_control",
    "audit_logging",
    "encryption_tls",
    "vulnerability_mgmt",
    "incident_response",
    "backup_dr",
    "monitoring",
    "change_management",
    "data_protection",
    "go_live_attestation",
    "residual_risk",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_compliance_readiness_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "33"
    assert mapping["workstream"] == "C1"
    assert mapping["register_complete"] is True
    assert mapping["soc2_complete_claimed"] is False
    assert mapping["iso27001_complete_claimed"] is False
    assert mapping["certification_complete_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["vendor_pen_test_purchased"] is False
    assert mapping["doc"] == "docs/COMPLIANCE_READINESS_MVP.md"
    assert "stage33_c1_compliance_readiness.json" in mapping["evidence_artifact"]
    controls = mapping["controls"]
    assert len(controls) >= 10
    ids = {c["id"] for c in controls}
    assert REQUIRED_IDS.issubset(ids)
    themes = {c["theme"] for c in controls}
    assert REQUIRED_THEMES.issubset(themes)
    for control in controls:
        assert control["certified"] is False
        assert control["status"] in ("mapped", "partial", "deferred")
        assert control["title"]
        assert control["source"]
        assert isinstance(control["framework_hints"], list) and control["framework_hints"]
        assert isinstance(control["evidence_packs"], list) and control["evidence_packs"]
        for pack in control["evidence_packs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(c["id"] == "cr-attestation" and c["status"] == "deferred" for c in controls)
    assert any("SOC" in h or "ISO" in h for c in controls for h in c["framework_hints"])
    assert any("SOC" in d or "ISO" in d for d in mapping["deferred"])
    for rel in (
        mapping["residual_risk_register"],
        mapping["operator_remaining_register"],
        mapping["gate_matrix"],
        mapping["security_guide"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_compliance_readiness_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    remaining = json.loads(REMAINING.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    gate = json.loads(GATE.read_text(encoding="utf-8"))

    assert remaining["attestation_claimed"] is False
    assert remaining["section_7_signed"] is False
    assert remaining["live_runs_certified"] is False
    assert residual["risks_closed_claimed"] is False
    assert residual["go_live_claimed"] is False
    assert gate["go_live_claimed"] is False
    assert mapping["soc2_complete_claimed"] is False
    assert mapping["iso27001_complete_claimed"] is False
    assert mapping["certification_complete_claimed"] is False
    for control in mapping["controls"]:
        assert control["certified"] is False


def test_compliance_readiness_doc_and_readme():
    doc = _read("docs/COMPLIANCE_READINESS_MVP.md")
    assert "Stage 33 C1" in doc
    assert "test_compliance_readiness_c1.py" in doc
    assert "compliance-readiness-register.json" in doc
    assert "stage33_c1_compliance_readiness.json" in doc
    assert "SECURITY_GUIDE.md" in doc
    assert "SOC 2" in doc or "SOC2" in doc
    assert "ISO" in doc
    assert "soc2_complete_claimed" in doc or "certification" in doc.lower()
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 33 C1" in readme
    assert "COMPLIANCE_READINESS_MVP.md" in readme
    assert "compliance-readiness-register.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_33_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_compliance_readiness_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "F1 next" in plan
        or "F1 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H33x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_compliance_readiness_c1.py" in launch
    assert "Stage 33 C1" in launch
    assert "COMPLIANCE_READINESS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 33 C1" in roadmap
    assert "test_compliance_readiness_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 33 C1" in pr
    assert "test_compliance_readiness_c1.py" in pr or "COMPLIANCE_READINESS_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 33 C1" in sec
    assert "COMPLIANCE_READINESS_MVP.md" in sec or "test_compliance_readiness_c1.py" in sec
    assert "SOC 2" in sec or "ISO 27001" in sec

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "33",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/COMPLIANCE_READINESS_MVP.md",
        "register": "ops/mvp/compliance-readiness-register.json",
        "register_complete": True,
        "soc2_complete_claimed": False,
        "iso27001_complete_claimed": False,
        "certification_complete_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "control_count": len(mapping["controls"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["soc2_complete_claimed"] is False
    assert loaded["iso27001_complete_claimed"] is False
    assert loaded["certification_complete_claimed"] is False
    assert loaded["control_count"] >= 10
