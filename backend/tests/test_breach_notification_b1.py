"""Stage 38 B1 — Breach notification / security contact (not live breach drill Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "breach-notification.json"
INCIDENT = ROOT / "ops" / "incident" / "incident-checklist.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage38_b1_breach_notification.json"

REQUIRED_IDS = {
    "bn-severity-ack",
    "bn-gdpr-72h",
    "bn-incident-checklist",
    "bn-security-contact",
    "bn-playbook",
    "bn-post-incident-evidence",
    "bn-alertmanager-pagerduty",
    "bn-vuln-disclosure-adjacency",
    "bn-breach-drill-remaining",
    "bn-regulatory-filing-remaining",
}
REQUIRED_CATEGORIES = {"incident", "regulatory", "contact", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_breach_notification_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "38"
    assert mapping["workstream"] == "B1"
    assert mapping["packaging_complete"] is True
    assert mapping["breach_drill_claimed"] is False
    assert mapping["regulatory_filing_claimed"] is False
    assert mapping["customer_notify_saas_claimed"] is False
    assert mapping["security_mailbox_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/BREACH_NOTIFICATION_MVP.md"
    assert "stage38_b1_breach_notification.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "bn-breach-drill-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "bn-gdpr-72h" for s in steps)
    assert any(
        "breach" in d.lower() or "72" in d or "filing" in d.lower() or "mailbox" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["incident_pack"],
        mapping["incident_checklist"],
        mapping["oncall_runbook"],
        mapping["security_guide"],
        mapping["vuln_disclosure"],
        mapping["vuln_disclosure_doc"],
        mapping["support_sla"],
        mapping["evidence_ledger"],
        mapping["stage38_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_breach_notification_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    incident = json.loads(INCIDENT.read_text(encoding="utf-8"))
    assert mapping["breach_drill_claimed"] is False
    assert mapping["regulatory_filing_claimed"] is False
    assert mapping["security_mailbox_live"] is False
    flags = json.dumps(incident).lower()
    assert "false" in flags or "incident" in flags or "pagerduty" in flags
    for step in mapping["steps"]:
        assert step["done"] is False
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "72" in sec
    assert "breach" in sec.lower()
    incident_doc = _read("docs/INCIDENT_PACK_MVP.md")
    assert "P1" in incident_doc or "severity" in incident_doc.lower()


def test_breach_notification_doc_and_readme():
    doc = _read("docs/BREACH_NOTIFICATION_MVP.md")
    assert "Stage 38 B1" in doc
    assert "test_breach_notification_b1.py" in doc
    assert "breach-notification.json" in doc
    assert "stage38_b1_breach_notification.json" in doc
    assert "breach_drill_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "72" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 38 B1" in readme
    assert "BREACH_NOTIFICATION_MVP.md" in readme
    assert "breach-notification.json" in readme


def test_b1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_38_PLAN.md")
    b1_line = [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_breach_notification_b1.py" in plan
    assert (
        "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H38x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_breach_notification_b1.py" in launch
    assert "Stage 38 B1" in launch
    assert "BREACH_NOTIFICATION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 38 B1" in roadmap
    assert "test_breach_notification_b1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 38 B1" in pr
    assert "test_breach_notification_b1.py" in pr or "BREACH_NOTIFICATION_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "38",
        "workstream": "B1",
        "passed": True,
        "doc": "docs/BREACH_NOTIFICATION_MVP.md",
        "register": "ops/mvp/breach-notification.json",
        "packaging_complete": True,
        "breach_drill_claimed": False,
        "regulatory_filing_claimed": False,
        "customer_notify_saas_claimed": False,
        "security_mailbox_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["breach_drill_claimed"] is False
    assert loaded["regulatory_filing_claimed"] is False
    assert loaded["security_mailbox_live"] is False
    assert loaded["step_count"] >= 10
