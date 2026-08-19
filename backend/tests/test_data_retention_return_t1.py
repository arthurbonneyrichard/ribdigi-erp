"""Stage 45 T1 — Data retention / return honesty (not data-return portal Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-retention-return.json"
ERASURE = ROOT / "ops" / "mvp" / "erasure-honesty.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage45_t1_data_retention_return.json"

REQUIRED_IDS = {
    "drt-adr007-audit",
    "drt-br-schedule",
    "drt-erasure-adjacency",
    "drt-portability-adjacency",
    "drt-compliance-readiness",
    "drt-dpa-exit",
    "drt-rto-adjacency",
    "drt-backup-retention",
    "drt-return-portal-remaining",
    "drt-purge-exit-remaining",
}
REQUIRED_CATEGORIES = {"retention", "return", "continuity", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_data_retention_return_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "45"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["data_return_portal_claimed"] is False
    assert mapping["hot_audit_purge_claimed"] is False
    assert mapping["contract_exit_return_live"] is False
    assert mapping["offboarding_workflow_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/DATA_RETENTION_RETURN_MVP.md"
    assert "stage45_t1_data_retention_return.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "drt-return-portal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "drt-purge-exit-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "drt-adr007-audit" for s in steps)
    assert any(
        "return" in d.lower() or "purge" in d.lower() or "offboard" in d.lower() or "portal" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["adr_007"],
        mapping["business_requirements"],
        mapping["erasure_honesty"],
        mapping["erasure_honesty_doc"],
        mapping["data_portability"],
        mapping["data_portability_doc"],
        mapping["compliance_readiness"],
        mapping["compliance_readiness_doc"],
        mapping["dpa_subprocessor"],
        mapping["dpa_subprocessor_doc"],
        mapping["rto_rpo"],
        mapping["rto_rpo_doc"],
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["logical_backup_doc"],
        mapping["stage45_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_data_retention_return_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    erasure = json.loads(ERASURE.read_text(encoding="utf-8"))
    assert mapping["data_return_portal_claimed"] is False
    assert mapping["hot_audit_purge_claimed"] is False
    assert erasure.get("hard_delete_claimed") is False
    assert erasure.get("erasure_complete_claimed") is False
    adr = _read("docs/ADR_007_AUDIT_RETENTION.md")
    assert "7 years" in adr or "retention" in adr.lower() or "cold archive" in adr.lower()
    for step in mapping["steps"]:
        assert step["done"] is False
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "retention" in br.lower() or "7 years" in br
    port = _read("docs/DATA_PORTABILITY_MVP.md")
    assert "portability" in port.lower() or "export" in port.lower() or "GDPR" in port


def test_data_retention_return_doc_and_readme():
    doc = _read("docs/DATA_RETENTION_RETURN_MVP.md")
    assert "Stage 45 T1" in doc
    assert "test_data_retention_return_t1.py" in doc
    assert "data-retention-return.json" in doc
    assert "stage45_t1_data_retention_return.json" in doc
    assert "data_return_portal_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "Retention" in doc or "Return" in doc or "retention" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 45 T1" in readme
    assert "DATA_RETENTION_RETURN_MVP.md" in readme
    assert "data-retention-return.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_45_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_data_retention_return_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H45x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_data_retention_return_t1.py" in launch
    assert "Stage 45 T1" in launch
    assert "DATA_RETENTION_RETURN_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 45 T1" in roadmap
    assert "test_data_retention_return_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 45 T1" in pr
    assert "test_data_retention_return_t1.py" in pr or "DATA_RETENTION_RETURN_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "45",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/DATA_RETENTION_RETURN_MVP.md",
        "register": "ops/mvp/data-retention-return.json",
        "packaging_complete": True,
        "data_return_portal_claimed": False,
        "hot_audit_purge_claimed": False,
        "contract_exit_return_live": False,
        "offboarding_workflow_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["data_return_portal_claimed"] is False
    assert loaded["hot_audit_purge_claimed"] is False
    assert loaded["step_count"] >= 10
