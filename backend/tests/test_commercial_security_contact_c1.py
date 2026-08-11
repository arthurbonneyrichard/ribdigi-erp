"""Stage 75 C1 — Commercial security contact honesty (not security contact live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-security-contact.json"
BREACH = ROOT / "ops" / "mvp" / "breach-notification.json"
VULN = ROOT / "ops" / "mvp" / "vuln-disclosure.json"
SUPPORT = ROOT / "ops" / "mvp" / "commercial-support.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage75_c1_commercial_security_contact.json"

REQUIRED_IDS = {
    "csc-owner-outline", "csc-breach", "csc-vuln", "csc-support", "csc-status",
    "csc-assurance", "csc-plan-honesty", "csc-intake-ownership", "csc-contact-remaining", "csc-golive-remaining",
}
REQUIRED_CATEGORIES = {"security", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_security_contact_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "75" and mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    for k in ("security_contact_live_claimed", "breach_drill_claimed", "vuln_disclosure_live_claimed",
              "commercial_support_claimed", "status_page_live", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_SECURITY_CONTACT_MVP.md"
    assert "stage75_c1_commercial_security_contact.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "csc-contact-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "csc-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("security" in d.lower() or "breach" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage75_plan"], mapping["breach_doc"], mapping["breach"],
                mapping["vuln_doc"], mapping["vuln"], mapping["support_doc"], mapping["support"],
                mapping["status_doc"], mapping["status"], mapping["assurance_doc"], mapping["assurance"],
                mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_security_contact_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    breach = json.loads(BREACH.read_text(encoding="utf-8"))
    vuln = json.loads(VULN.read_text(encoding="utf-8"))
    support = json.loads(SUPPORT.read_text(encoding="utf-8"))
    assert mapping["security_contact_live_claimed"] is False
    for key in ("breach_drill_claimed", "go_live_claimed", "security_mailbox_live"):
        if key in breach:
            assert breach[key] is False
    for key in ("disclosure_program_claimed", "researcher_intake_live", "go_live_claimed"):
        if key in vuln:
            assert vuln[key] is False
    for key in ("commercial_support_claimed", "support_boundary_live_claimed", "go_live_claimed"):
        if key in support:
            assert support[key] is False
    plan = _read("docs/STAGE_75_PLAN.md")
    assert "Security Contact" in plan and "Privacy Notice" in plan


def test_commercial_security_contact_doc_and_readme():
    doc = _read("docs/COMMERCIAL_SECURITY_CONTACT_MVP.md")
    assert "Stage 75 C1" in doc and "test_commercial_security_contact_c1.py" in doc
    assert "commercial-security-contact.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 75 C1" in readme and "COMMERCIAL_SECURITY_CONTACT_MVP.md" in readme and "commercial-security-contact.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_75_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "test_commercial_security_contact_c1.py" in plan
    assert any(x in plan for x in ("C1 next", "C1 complete", "P1 next", "P1 complete", "D1 next", "D1 complete", "H75x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_security_contact_c1.py" in launch and "Stage 75 C1" in launch and "COMMERCIAL_SECURITY_CONTACT_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 75 C1" in roadmap and "test_commercial_security_contact_c1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 75 C1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "75", "workstream": "C1", "passed": True, "doc": "docs/COMMERCIAL_SECURITY_CONTACT_MVP.md",
               "register": "ops/mvp/commercial-security-contact.json", "packaging_complete": True,
               "security_contact_live_claimed": False, "breach_drill_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["security_contact_live_claimed"] is False and loaded["step_count"] >= 10
