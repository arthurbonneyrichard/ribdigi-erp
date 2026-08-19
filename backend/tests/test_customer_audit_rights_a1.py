"""Stage 47 A1 — customer audit rights honesty (not audit executed Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "customer-audit-rights.json"
ASSURANCE = ROOT / "ops" / "mvp" / "assurance-evidence.json"
CYBER = ROOT / "ops" / "mvp" / "cyber-insurance.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage47_a1_customer_audit_rights.json"

REQUIRED_IDS = {
    "ar-assurance-adjacency",
    "ar-pentest-adjacency",
    "ar-msa-adjacency",
    "ar-compliance-themes",
    "ar-insurance-adjacency",
    "ar-vuln-adjacency",
    "ar-residual-risk",
    "ar-security-guide",
    "ar-executed-remaining",
    "ar-schedule-remaining",
}
REQUIRED_CATEGORIES = {"audit", "rights", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_customer_audit_rights_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "47"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["customer_audit_rights_live"] is False
    assert mapping["on_site_audit_claimed"] is False
    assert mapping["audit_executed_claimed"] is False
    assert mapping["audit_schedule_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/CUSTOMER_AUDIT_RIGHTS_MVP.md"
    assert "stage47_a1_customer_audit_rights.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ar-executed-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ar-schedule-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "audit" in d.lower() or "on-site" in d.lower() or "soc" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["assurance_evidence"],
        mapping["assurance_evidence_doc"],
        mapping["pentest_pack_doc"],
        mapping["pentest_checklist"],
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["compliance_questionnaire_doc"],
        mapping["compliance_readiness_doc"],
        mapping["cyber_insurance"],
        mapping["cyber_insurance_doc"],
        mapping["vuln_disclosure"],
        mapping["vuln_disclosure_doc"],
        mapping["residual_risk"],
        mapping["residual_risk_doc"],
        mapping["security_guide"],
        mapping["stage47_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_customer_audit_rights_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assurance = json.loads(ASSURANCE.read_text(encoding="utf-8"))
    cyber = json.loads(CYBER.read_text(encoding="utf-8"))
    assert mapping["customer_audit_rights_live"] is False
    assert mapping["audit_executed_claimed"] is False
    assert cyber.get("coi_issued_claimed") is False
    assert assurance.get("packaging_complete") is True
    for step in mapping["steps"]:
        assert step["done"] is False
    ae = _read("docs/ASSURANCE_EVIDENCE_MVP.md")
    assert "assurance" in ae.lower() or "evidence" in ae.lower()
    pt = _read("docs/PENTEST_PACK_MVP.md")
    assert "pen" in pt.lower() or "ZAP" in pt or "test" in pt.lower()


def test_customer_audit_rights_doc_and_readme():
    doc = _read("docs/CUSTOMER_AUDIT_RIGHTS_MVP.md")
    assert "Stage 47 A1" in doc
    assert "test_customer_audit_rights_a1.py" in doc
    assert "customer-audit-rights.json" in doc
    assert "stage47_a1_customer_audit_rights.json" in doc
    assert "customer_audit_rights_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "audit" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 47 A1" in readme
    assert "CUSTOMER_AUDIT_RIGHTS_MVP.md" in readme
    assert "customer-audit-rights.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_47_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_customer_audit_rights_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H47x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_customer_audit_rights_a1.py" in launch
    assert "Stage 47 A1" in launch
    assert "CUSTOMER_AUDIT_RIGHTS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 47 A1" in roadmap
    assert "test_customer_audit_rights_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 47 A1" in pr
    assert "test_customer_audit_rights_a1.py" in pr or "CUSTOMER_AUDIT_RIGHTS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "47",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/CUSTOMER_AUDIT_RIGHTS_MVP.md",
        "register": "ops/mvp/customer-audit-rights.json",
        "packaging_complete": True,
        "customer_audit_rights_live": False,
        "on_site_audit_claimed": False,
        "audit_executed_claimed": False,
        "audit_schedule_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["customer_audit_rights_live"] is False
    assert loaded["audit_executed_claimed"] is False
    assert loaded["step_count"] >= 10
