"""Stage 79 A1 — Commercial customer audit honesty (not customer audit rights live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-customer-audit.json"
AUDIT = ROOT / "ops" / "mvp" / "customer-audit-rights.json"
RETENTION = ROOT / "ops" / "mvp" / "commercial-data-retention.json"
ASSURE = ROOT / "ops" / "mvp" / "commercial-assurance.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage79_a1_commercial_customer_audit.json"

REQUIRED_IDS = {
    "cca-owner-outline", "cca-stage47", "cca-retention", "cca-dpa", "cca-assurance",
    "cca-evidence", "cca-plan-honesty", "cca-schedule-ownership", "cca-audit-remaining", "cca-golive-remaining",
}
REQUIRED_CATEGORIES = {"audit", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_customer_audit_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "79" and mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    for k in ("customer_audit_rights_live", "on_site_audit_claimed", "audit_executed_claimed",
              "audit_schedule_live", "data_return_portal_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_CUSTOMER_AUDIT_MVP.md"
    assert "stage79_a1_commercial_customer_audit.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cca-audit-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cca-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("audit" in d.lower() or "return" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage79_plan"], mapping["audit_doc"], mapping["audit"],
                mapping["retention_commercial_doc"], mapping["retention_commercial"],
                mapping["dpa_commercial_doc"], mapping["dpa_commercial"], mapping["assurance_doc"],
                mapping["assurance"], mapping["evidence_chain_doc"], mapping["evidence_chain"],
                mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_customer_audit_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    retention = json.loads(RETENTION.read_text(encoding="utf-8"))
    assure = json.loads(ASSURE.read_text(encoding="utf-8"))
    assert mapping["customer_audit_rights_live"] is False
    for key in ("customer_audit_rights_live", "on_site_audit_claimed", "audit_executed_claimed", "go_live_claimed"):
        if key in audit:
            assert audit[key] is False
    for key in ("data_return_portal_claimed", "go_live_claimed"):
        if key in retention:
            assert retention[key] is False
    for key in ("customer_assurance_claimed", "go_live_claimed"):
        if key in assure:
            assert assure[key] is False
    plan = _read("docs/STAGE_79_PLAN.md")
    assert "Audit" in plan and "Retention" in plan


def test_commercial_customer_audit_doc_and_readme():
    doc = _read("docs/COMMERCIAL_CUSTOMER_AUDIT_MVP.md")
    assert "Stage 79 A1" in doc and "test_commercial_customer_audit_a1.py" in doc
    assert "commercial-customer-audit.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 79 A1" in readme and "COMMERCIAL_CUSTOMER_AUDIT_MVP.md" in readme and "commercial-customer-audit.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_79_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "test_commercial_customer_audit_a1.py" in plan
    assert any(x in plan for x in ("A1 next", "A1 complete", "D1 next", "D1 complete", "H79x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_customer_audit_a1.py" in launch and "Stage 79 A1" in launch and "COMMERCIAL_CUSTOMER_AUDIT_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 79 A1" in roadmap and "test_commercial_customer_audit_a1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 79 A1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "79", "workstream": "A1", "passed": True, "doc": "docs/COMMERCIAL_CUSTOMER_AUDIT_MVP.md",
               "register": "ops/mvp/commercial-customer-audit.json", "packaging_complete": True,
               "customer_audit_rights_live": False, "audit_executed_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["customer_audit_rights_live"] is False and loaded["step_count"] >= 10
