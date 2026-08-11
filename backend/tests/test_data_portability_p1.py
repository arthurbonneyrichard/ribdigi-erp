"""Stage 37 P1 — Data subject access / portability (not GDPR / DSAR Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-portability.json"
QUESTIONNAIRE = ROOT / "ops" / "mvp" / "compliance-questionnaire.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage37_p1_data_portability.json"

REQUIRED_IDS = {
    "dp-backup-download",
    "dp-reports-export",
    "dp-audit-export",
    "dp-catalog-export-deferred",
    "dp-tenant-isolation",
    "dp-compliance-questionnaire-privacy",
    "dp-security-guide-gdpr",
    "dp-brd-gdpr-ready",
    "dp-dsar-portal-remaining",
    "dp-gdpr-cert-remaining",
}
REQUIRED_CATEGORIES = {"access", "portability", "deferred", "compliance", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_data_portability_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "37"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    assert mapping["gdpr_complete_claimed"] is False
    assert mapping["dsar_portal_claimed"] is False
    assert mapping["live_portability_workflow_claimed"] is False
    assert mapping["consent_management_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/DATA_PORTABILITY_MVP.md"
    assert "stage37_p1_data_portability.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    ids = {s["id"] for s in steps}
    assert REQUIRED_IDS.issubset(ids)
    cats = {s["category"] for s in steps}
    assert REQUIRED_CATEGORIES.issubset(cats)
    for step in steps:
        assert step["done"] is False
        assert step["status"] in ("packaged", "remaining")
        assert step["title"]
        assert step["source"]
        assert isinstance(step["pack_refs"], list) and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "dp-dsar-portal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "dp-backup-download" for s in steps)
    assert any(
        "gdpr" in d.lower() or "dsar" in d.lower() or "portability" in d.lower() or "consent" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["backup_runbook"],
        mapping["compliance_questionnaire"],
        mapping["compliance_readiness"],
        mapping["compliance_questionnaire_doc"],
        mapping["compliance_readiness_doc"],
        mapping["security_guide"],
        mapping["stage37_plan"],
        mapping["launch_checklist"],
        mapping["api_documentation"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_data_portability_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    questionnaire = json.loads(QUESTIONNAIRE.read_text(encoding="utf-8"))
    assert mapping["gdpr_complete_claimed"] is False
    assert mapping["dsar_portal_claimed"] is False
    qflags = json.dumps(questionnaire).lower()
    assert "gdpr" in qflags or "privacy" in qflags or "data protection" in qflags
    for step in mapping["steps"]:
        assert step["done"] is False
    backup = _read("docs/DR_LOGICAL_BACKUP_RUNBOOK.md")
    assert "download" in backup.lower() or "ribbak" in backup.lower() or "backup" in backup.lower()
    api = _read("docs/API_DOCUMENTATION.md")
    assert "/reports/export" in api or "reports/export" in api
    assert "audit-logs/export" in api or "/backup" in api
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "GDPR" in sec


def test_data_portability_doc_and_readme():
    doc = _read("docs/DATA_PORTABILITY_MVP.md")
    assert "Stage 37 P1" in doc
    assert "test_data_portability_p1.py" in doc
    assert "data-portability.json" in doc
    assert "stage37_p1_data_portability.json" in doc
    assert "gdpr_complete_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "DSAR" in doc or "dsar" in doc.lower() or "portability" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 37 P1" in readme
    assert "DATA_PORTABILITY_MVP.md" in readme
    assert "data-portability.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_37_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_data_portability_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "E1 next" in plan
        or "E1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H37x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_data_portability_p1.py" in launch
    assert "Stage 37 P1" in launch
    assert "DATA_PORTABILITY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 37 P1" in roadmap
    assert "test_data_portability_p1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 37 P1" in pr
    assert "test_data_portability_p1.py" in pr or "DATA_PORTABILITY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "37",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/DATA_PORTABILITY_MVP.md",
        "register": "ops/mvp/data-portability.json",
        "packaging_complete": True,
        "gdpr_complete_claimed": False,
        "dsar_portal_claimed": False,
        "live_portability_workflow_claimed": False,
        "consent_management_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["gdpr_complete_claimed"] is False
    assert loaded["dsar_portal_claimed"] is False
    assert loaded["live_portability_workflow_claimed"] is False
    assert loaded["step_count"] >= 10
