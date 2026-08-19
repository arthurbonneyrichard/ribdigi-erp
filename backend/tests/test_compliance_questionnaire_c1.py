"""Stage 34 C1 — compliance questionnaire (not SOC 2 / ISO certification Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "compliance-questionnaire.json"
COMPLIANCE = ROOT / "ops" / "mvp" / "compliance-readiness-register.json"
ASSURANCE = ROOT / "ops" / "mvp" / "assurance-evidence.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage34_c1_compliance_questionnaire.json"

REQUIRED_IDS = {
    "cq-access-control",
    "cq-audit-logging",
    "cq-encryption-tls",
    "cq-vulnerability",
    "cq-incident",
    "cq-backup-dr",
    "cq-monitoring",
    "cq-change-ci",
    "cq-privacy",
    "cq-attestation",
    "cq-certification-boundary",
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
    "certification_status",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_compliance_questionnaire_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "34"
    assert mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    assert mapping["soc2_complete_claimed"] is False
    assert mapping["iso27001_complete_claimed"] is False
    assert mapping["certification_complete_claimed"] is False
    assert mapping["questionnaire_answers_certified"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["vendor_pen_test_purchased"] is False
    assert mapping["doc"] == "docs/COMPLIANCE_QUESTIONNAIRE_MVP.md"
    assert "stage34_c1_compliance_questionnaire.json" in mapping["evidence_artifact"]
    themes = mapping["themes"]
    assert len(themes) >= 10
    ids = {t["id"] for t in themes}
    assert REQUIRED_IDS.issubset(ids)
    theme_names = {t["theme"] for t in themes}
    assert REQUIRED_THEMES.issubset(theme_names)
    for theme in themes:
        assert theme["certified"] is False
        assert theme["status"] in ("mapped",)
        assert theme["title"]
        assert theme["source"]
        assert theme["maps_to_control"]
        assert isinstance(theme["pack_refs"], list) and theme["pack_refs"]
        for pack in theme["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(t["id"] == "cq-certification-boundary" for t in themes)
    assert any("SOC" in d or "ISO" in d for d in mapping["deferred"])
    for rel in (
        mapping["compliance_readiness_register"],
        mapping["assurance_evidence"],
        mapping["security_guide"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_compliance_questionnaire_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    compliance = json.loads(COMPLIANCE.read_text(encoding="utf-8"))
    assurance = json.loads(ASSURANCE.read_text(encoding="utf-8"))

    assert compliance["soc2_complete_claimed"] is False
    assert compliance["iso27001_complete_claimed"] is False
    assert compliance["certification_complete_claimed"] is False
    control_ids = {c["id"] for c in compliance["controls"]}
    for theme in mapping["themes"]:
        assert theme["maps_to_control"] in control_ids
        assert theme["certified"] is False
    assert assurance["certification_complete_claimed"] is False
    assert assurance["attestation_claimed"] is False
    assert mapping["questionnaire_answers_certified"] is False


def test_compliance_questionnaire_doc_and_readme():
    doc = _read("docs/COMPLIANCE_QUESTIONNAIRE_MVP.md")
    assert "Stage 34 C1" in doc
    assert "test_compliance_questionnaire_c1.py" in doc
    assert "compliance-questionnaire.json" in doc
    assert "stage34_c1_compliance_questionnaire.json" in doc
    assert "COMPLIANCE_READINESS_MVP.md" in doc
    assert "SOC 2" in doc or "SOC2" in doc
    assert "ISO" in doc
    assert "soc2_complete_claimed" in doc or "certification" in doc.lower()
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 34 C1" in readme
    assert "COMPLIANCE_QUESTIONNAIRE_MVP.md" in readme
    assert "compliance-questionnaire.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_34_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_compliance_questionnaire_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H34x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_compliance_questionnaire_c1.py" in launch
    assert "Stage 34 C1" in launch
    assert "COMPLIANCE_QUESTIONNAIRE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 34 C1" in roadmap
    assert "test_compliance_questionnaire_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 34 C1" in pr
    assert "test_compliance_questionnaire_c1.py" in pr or "COMPLIANCE_QUESTIONNAIRE_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 34 C1" in sec
    assert "COMPLIANCE_QUESTIONNAIRE_MVP.md" in sec or "test_compliance_questionnaire_c1.py" in sec
    assert "SOC 2" in sec or "ISO 27001" in sec

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "34",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/COMPLIANCE_QUESTIONNAIRE_MVP.md",
        "register": "ops/mvp/compliance-questionnaire.json",
        "packaging_complete": True,
        "soc2_complete_claimed": False,
        "iso27001_complete_claimed": False,
        "certification_complete_claimed": False,
        "questionnaire_answers_certified": False,
        "theme_count": len(mapping["themes"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["soc2_complete_claimed"] is False
    assert loaded["iso27001_complete_claimed"] is False
    assert loaded["questionnaire_answers_certified"] is False
    assert loaded["theme_count"] >= 10
