"""Stage 76 T1 — Commercial terms honesty (not signed ToS Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-terms.json"
TOS = ROOT / "ops" / "mvp" / "tos-aup.json"
MSA = ROOT / "ops" / "mvp" / "msa-addendum.json"
PRIVACY = ROOT / "ops" / "mvp" / "commercial-privacy-notice.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage76_t1_commercial_terms.json"

REQUIRED_IDS = {
    "ct-owner-outline", "ct-tos-aup", "ct-msa", "ct-privacy", "ct-security-contact",
    "ct-billing-deferred", "ct-plan-honesty", "ct-counsel-review", "ct-tos-remaining", "ct-golive-remaining",
}
REQUIRED_CATEGORIES = {"terms", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_terms_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "76" and mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    for k in ("tos_signed_claimed", "aup_enforced_claimed", "clickwrap_live",
              "legal_counsel_claimed", "privacy_notice_live", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_TERMS_MVP.md"
    assert "stage76_t1_commercial_terms.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "ct-tos-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ct-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("tos" in d.lower() or "billing" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage76_plan"], mapping["tos_aup_doc"], mapping["tos_aup"],
                mapping["msa_doc"], mapping["msa"], mapping["privacy_doc"], mapping["privacy"],
                mapping["security_contact_doc"], mapping["security_contact"],
                mapping["billing_deferred_doc"], mapping["billing_deferred"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_terms_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    tos = json.loads(TOS.read_text(encoding="utf-8"))
    msa = json.loads(MSA.read_text(encoding="utf-8"))
    privacy = json.loads(PRIVACY.read_text(encoding="utf-8"))
    assert mapping["tos_signed_claimed"] is False
    for key in ("tos_signed_claimed", "aup_enforced_claimed", "clickwrap_live", "go_live_claimed"):
        if key in tos:
            assert tos[key] is False
    for key in ("go_live_claimed", "section_7_signed"):
        if key in msa:
            assert msa[key] is False
    for key in ("privacy_notice_live", "go_live_claimed"):
        if key in privacy:
            assert privacy[key] is False
    plan = _read("docs/STAGE_76_PLAN.md")
    assert "Terms" in plan and "Billing" in plan


def test_commercial_terms_doc_and_readme():
    doc = _read("docs/COMMERCIAL_TERMS_MVP.md")
    assert "Stage 76 T1" in doc and "test_commercial_terms_t1.py" in doc
    assert "commercial-terms.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 76 T1" in readme and "COMMERCIAL_TERMS_MVP.md" in readme and "commercial-terms.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_76_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "test_commercial_terms_t1.py" in plan
    assert any(x in plan for x in ("T1 next", "T1 complete", "B1 next", "B1 complete", "D1 next", "D1 complete", "H76x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_terms_t1.py" in launch and "Stage 76 T1" in launch and "COMMERCIAL_TERMS_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 76 T1" in roadmap and "test_commercial_terms_t1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 76 T1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "76", "workstream": "T1", "passed": True, "doc": "docs/COMMERCIAL_TERMS_MVP.md",
               "register": "ops/mvp/commercial-terms.json", "packaging_complete": True,
               "tos_signed_claimed": False, "clickwrap_live": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["tos_signed_claimed"] is False and loaded["step_count"] >= 10
