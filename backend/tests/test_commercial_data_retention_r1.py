"""Stage 79 R1 — Commercial data retention honesty (not data return portal Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-data-retention.json"
RETENTION = ROOT / "ops" / "mvp" / "data-retention-return.json"
DPA = ROOT / "ops" / "mvp" / "commercial-dpa.json"
PRIVACY = ROOT / "ops" / "mvp" / "commercial-privacy-notice.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage79_r1_commercial_data_retention.json"

REQUIRED_IDS = {
    "cdr-owner-outline", "cdr-stage45", "cdr-dpa", "cdr-portability", "cdr-privacy",
    "cdr-terms", "cdr-plan-honesty", "cdr-offboarding-ownership", "cdr-portal-remaining", "cdr-golive-remaining",
}
REQUIRED_CATEGORIES = {"retention", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_data_retention_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "79" and mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    for k in ("data_return_portal_claimed", "contract_exit_return_live", "offboarding_workflow_claimed",
              "hot_audit_purge_claimed", "dpa_signed_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_DATA_RETENTION_MVP.md"
    assert "stage79_r1_commercial_data_retention.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cdr-portal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cdr-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("return" in d.lower() or "offboarding" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage79_plan"], mapping["retention_doc"], mapping["retention"],
                mapping["dpa_commercial_doc"], mapping["dpa_commercial"], mapping["portability_doc"],
                mapping["portability"], mapping["privacy_doc"], mapping["privacy"],
                mapping["terms_doc"], mapping["terms"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_data_retention_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    retention = json.loads(RETENTION.read_text(encoding="utf-8"))
    dpa = json.loads(DPA.read_text(encoding="utf-8"))
    privacy = json.loads(PRIVACY.read_text(encoding="utf-8"))
    assert mapping["data_return_portal_claimed"] is False
    for key in ("data_return_portal_claimed", "contract_exit_return_live", "offboarding_workflow_claimed", "go_live_claimed"):
        if key in retention:
            assert retention[key] is False
    for key in ("dpa_signed_claimed", "go_live_claimed"):
        if key in dpa:
            assert dpa[key] is False
    for key in ("privacy_notice_live", "go_live_claimed"):
        if key in privacy:
            assert privacy[key] is False
    plan = _read("docs/STAGE_79_PLAN.md")
    assert "Retention" in plan and "Audit" in plan


def test_commercial_data_retention_doc_and_readme():
    doc = _read("docs/COMMERCIAL_DATA_RETENTION_MVP.md")
    assert "Stage 79 R1" in doc and "test_commercial_data_retention_r1.py" in doc
    assert "commercial-data-retention.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 79 R1" in readme and "COMMERCIAL_DATA_RETENTION_MVP.md" in readme and "commercial-data-retention.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_79_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "test_commercial_data_retention_r1.py" in plan
    assert any(x in plan for x in ("R1 next", "R1 complete", "A1 next", "A1 complete", "D1 next", "D1 complete", "H79x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_data_retention_r1.py" in launch and "Stage 79 R1" in launch and "COMMERCIAL_DATA_RETENTION_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 79 R1" in roadmap and "test_commercial_data_retention_r1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 79 R1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "79", "workstream": "R1", "passed": True, "doc": "docs/COMMERCIAL_DATA_RETENTION_MVP.md",
               "register": "ops/mvp/commercial-data-retention.json", "packaging_complete": True,
               "data_return_portal_claimed": False, "contract_exit_return_live": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["data_return_portal_claimed"] is False and loaded["step_count"] >= 10
