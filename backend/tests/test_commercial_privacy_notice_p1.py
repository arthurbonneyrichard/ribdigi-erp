"""Stage 75 P1 — Commercial privacy notice honesty (not privacy notice live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-privacy-notice.json"
COOKIE = ROOT / "ops" / "mvp" / "cookie-privacy-notice.json"
PORTABILITY = ROOT / "ops" / "mvp" / "data-portability.json"
CONTACT = ROOT / "ops" / "mvp" / "commercial-security-contact.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage75_p1_commercial_privacy_notice.json"

REQUIRED_IDS = {
    "cpn-owner-outline", "cpn-cookie-privacy", "cpn-portability", "cpn-security-contact", "cpn-support",
    "cpn-status", "cpn-plan-honesty", "cpn-legal-review", "cpn-privacy-remaining", "cpn-golive-remaining",
}
REQUIRED_CATEGORIES = {"privacy", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_privacy_notice_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "75" and mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    for k in ("privacy_notice_live", "cookie_consent_live", "security_contact_live_claimed",
              "commercial_support_claimed", "status_page_live", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md"
    assert "stage75_p1_commercial_privacy_notice.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cpn-privacy-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cpn-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("privacy" in d.lower() or "cookie" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage75_plan"], mapping["cookie_privacy_doc"], mapping["cookie_privacy"],
                mapping["portability_doc"], mapping["portability"], mapping["security_contact_doc"],
                mapping["security_contact"], mapping["support_doc"], mapping["support"],
                mapping["status_doc"], mapping["status"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_privacy_notice_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    cookie = json.loads(COOKIE.read_text(encoding="utf-8"))
    portability = json.loads(PORTABILITY.read_text(encoding="utf-8"))
    contact = json.loads(CONTACT.read_text(encoding="utf-8"))
    assert mapping["privacy_notice_live"] is False
    for key in ("privacy_notice_live", "cookie_consent_live", "go_live_claimed"):
        if key in cookie:
            assert cookie[key] is False
    for key in ("live_portability_workflow_claimed", "consent_management_claimed", "go_live_claimed"):
        if key in portability:
            assert portability[key] is False
    for key in ("security_contact_live_claimed", "go_live_claimed"):
        if key in contact:
            assert contact[key] is False
    plan = _read("docs/STAGE_75_PLAN.md")
    assert "Privacy Notice" in plan and "Security Contact" in plan


def test_commercial_privacy_notice_doc_and_readme():
    doc = _read("docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md")
    assert "Stage 75 P1" in doc and "test_commercial_privacy_notice_p1.py" in doc
    assert "commercial-privacy-notice.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 75 P1" in readme and "COMMERCIAL_PRIVACY_NOTICE_MVP.md" in readme and "commercial-privacy-notice.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_75_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "test_commercial_privacy_notice_p1.py" in plan
    assert any(x in plan for x in ("P1 next", "P1 complete", "D1 next", "D1 complete", "H75x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_privacy_notice_p1.py" in launch and "Stage 75 P1" in launch and "COMMERCIAL_PRIVACY_NOTICE_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 75 P1" in roadmap and "test_commercial_privacy_notice_p1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 75 P1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "75", "workstream": "P1", "passed": True, "doc": "docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md",
               "register": "ops/mvp/commercial-privacy-notice.json", "packaging_complete": True,
               "privacy_notice_live": False, "cookie_consent_live": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["privacy_notice_live"] is False and loaded["step_count"] >= 10
