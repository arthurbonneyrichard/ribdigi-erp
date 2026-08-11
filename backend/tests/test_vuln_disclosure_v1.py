"""Stage 38 V1 — Vulnerability disclosure policy (not live disclosure / bug-bounty Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "vuln-disclosure.json"
PENTEST = ROOT / "ops" / "security" / "pentest-engagement-checklist.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage38_v1_vuln_disclosure.json"

REQUIRED_IDS = {
    "vd-security-guide-severity",
    "vd-owasp-baseline",
    "vd-pentest-engagement",
    "vd-coordinated-policy",
    "vd-security-contact",
    "vd-scope-matrix",
    "vd-dependency-scan-remaining",
    "vd-zap-outside-ci",
    "vd-disclosure-program-remaining",
    "vd-bug-bounty-remaining",
}
REQUIRED_CATEGORIES = {"policy", "security", "contact", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_vuln_disclosure_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "38"
    assert mapping["workstream"] == "V1"
    assert mapping["packaging_complete"] is True
    assert mapping["disclosure_program_claimed"] is False
    assert mapping["bug_bounty_claimed"] is False
    assert mapping["continuous_disclosure_claimed"] is False
    assert mapping["researcher_intake_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/VULN_DISCLOSURE_MVP.md"
    assert "stage38_v1_vuln_disclosure.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "vd-disclosure-program-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "vd-owasp-baseline" for s in steps)
    assert any(
        "disclosure" in d.lower() or "bug-bounty" in d.lower() or "bug bounty" in d.lower() or "pen-test" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["security_scan"],
        mapping["pentest_pack"],
        mapping["pentest_checklist"],
        mapping["security_guide"],
        mapping["incident_pack"],
        mapping["zap_template"],
        mapping["stage38_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_vuln_disclosure_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    pentest = json.loads(PENTEST.read_text(encoding="utf-8"))
    assert mapping["disclosure_program_claimed"] is False
    assert mapping["bug_bounty_claimed"] is False
    pflags = json.dumps(pentest).lower()
    assert "false" in pflags or "vendor" in pflags or "zap" in pflags
    for step in mapping["steps"]:
        assert step["done"] is False
    scan = _read("docs/SECURITY_SCAN_MVP.md")
    assert "OWASP" in scan or "ZAP" in scan
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "vulnerability" in sec.lower() or "Vulnerability" in sec
    assert "P1" in sec or "Critical" in sec


def test_vuln_disclosure_doc_and_readme():
    doc = _read("docs/VULN_DISCLOSURE_MVP.md")
    assert "Stage 38 V1" in doc
    assert "test_vuln_disclosure_v1.py" in doc
    assert "vuln-disclosure.json" in doc
    assert "stage38_v1_vuln_disclosure.json" in doc
    assert "disclosure_program_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "bug-bounty" in doc.lower() or "bug bounty" in doc.lower() or "disclosure" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 38 V1" in readme
    assert "VULN_DISCLOSURE_MVP.md" in readme
    assert "vuln-disclosure.json" in readme


def test_v1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_38_PLAN.md")
    v1_line = [ln for ln in plan.splitlines() if "| **V1** |" in ln][0]
    assert "COMPLETE" in v1_line
    assert "test_vuln_disclosure_v1.py" in plan
    assert (
        "V1 next" in plan
        or "V1 complete" in plan
        or "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H38x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_vuln_disclosure_v1.py" in launch
    assert "Stage 38 V1" in launch
    assert "VULN_DISCLOSURE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 38 V1" in roadmap
    assert "test_vuln_disclosure_v1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 38 V1" in pr
    assert "test_vuln_disclosure_v1.py" in pr or "VULN_DISCLOSURE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "38",
        "workstream": "V1",
        "passed": True,
        "doc": "docs/VULN_DISCLOSURE_MVP.md",
        "register": "ops/mvp/vuln-disclosure.json",
        "packaging_complete": True,
        "disclosure_program_claimed": False,
        "bug_bounty_claimed": False,
        "continuous_disclosure_claimed": False,
        "researcher_intake_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["disclosure_program_claimed"] is False
    assert loaded["bug_bounty_claimed"] is False
    assert loaded["researcher_intake_live"] is False
    assert loaded["step_count"] >= 10
