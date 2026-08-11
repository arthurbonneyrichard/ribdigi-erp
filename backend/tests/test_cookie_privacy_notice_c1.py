"""Stage 43 C1 — Cookie / privacy notice honesty (not live cookie-consent Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cookie-privacy-notice.json"
PORTABILITY = ROOT / "ops" / "mvp" / "data-portability.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage43_c1_cookie_privacy_notice.json"

REQUIRED_IDS = {
    "cp-httponly-session",
    "cp-samesite-csrf",
    "cp-portability-consent",
    "cp-erasure-session",
    "cp-dpa-adjacency",
    "cp-compliance-questionnaire",
    "cp-compliance-readiness",
    "cp-tos-adjacency",
    "cp-cookie-consent-remaining",
    "cp-privacy-notice-remaining",
}
REQUIRED_CATEGORIES = {"cookie", "privacy", "compliance", "notice", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_cookie_privacy_notice_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "43"
    assert mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    assert mapping["cookie_consent_live"] is False
    assert mapping["cmp_saas_claimed"] is False
    assert mapping["privacy_notice_live"] is False
    assert mapping["legal_counsel_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/COOKIE_PRIVACY_NOTICE_MVP.md"
    assert "stage43_c1_cookie_privacy_notice.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "cp-cookie-consent-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cp-privacy-notice-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cp-httponly-session" for s in steps)
    assert any(
        "cookie" in d.lower() or "cmp" in d.lower() or "privacy" in d.lower() or "consent" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["security_guide"],
        mapping["data_portability"],
        mapping["data_portability_doc"],
        mapping["erasure_honesty"],
        mapping["erasure_honesty_doc"],
        mapping["dpa_subprocessor"],
        mapping["dpa_subprocessor_doc"],
        mapping["compliance_questionnaire"],
        mapping["compliance_questionnaire_doc"],
        mapping["compliance_readiness"],
        mapping["compliance_readiness_doc"],
        mapping["tos_aup"],
        mapping["tos_aup_doc"],
        mapping["stage43_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_cookie_privacy_notice_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    portability = json.loads(PORTABILITY.read_text(encoding="utf-8"))
    assert mapping["cookie_consent_live"] is False
    assert mapping["cmp_saas_claimed"] is False
    assert mapping["privacy_notice_live"] is False
    assert portability.get("consent_management_claimed") is False
    assert portability.get("gdpr_complete_claimed") is False
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "cookie" in sec.lower() or "HttpOnly" in sec or "SameSite" in sec
    for step in mapping["steps"]:
        assert step["done"] is False
    port_doc = _read("docs/DATA_PORTABILITY_MVP.md")
    assert "consent" in port_doc.lower() or "GDPR" in port_doc or "portability" in port_doc.lower()
    erasure = _read("docs/ERASURE_HONESTY_MVP.md")
    assert "erasure" in erasure.lower() or "session" in erasure.lower() or "delete" in erasure.lower()


def test_cookie_privacy_notice_doc_and_readme():
    doc = _read("docs/COOKIE_PRIVACY_NOTICE_MVP.md")
    assert "Stage 43 C1" in doc
    assert "test_cookie_privacy_notice_c1.py" in doc
    assert "cookie-privacy-notice.json" in doc
    assert "stage43_c1_cookie_privacy_notice.json" in doc
    assert "cookie_consent_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "Cookie" in doc or "Privacy" in doc or "consent" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 43 C1" in readme
    assert "COOKIE_PRIVACY_NOTICE_MVP.md" in readme
    assert "cookie-privacy-notice.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_43_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_cookie_privacy_notice_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H43x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_cookie_privacy_notice_c1.py" in launch
    assert "Stage 43 C1" in launch
    assert "COOKIE_PRIVACY_NOTICE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 43 C1" in roadmap
    assert "test_cookie_privacy_notice_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 43 C1" in pr
    assert "test_cookie_privacy_notice_c1.py" in pr or "COOKIE_PRIVACY_NOTICE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "43",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/COOKIE_PRIVACY_NOTICE_MVP.md",
        "register": "ops/mvp/cookie-privacy-notice.json",
        "packaging_complete": True,
        "cookie_consent_live": False,
        "cmp_saas_claimed": False,
        "privacy_notice_live": False,
        "legal_counsel_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["cookie_consent_live"] is False
    assert loaded["cmp_saas_claimed"] is False
    assert loaded["step_count"] >= 10
