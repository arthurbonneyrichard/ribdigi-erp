"""Stage 43 T1 — ToS / AUP honesty (not signed ToS Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tos-aup.json"
MSA = ROOT / "ops" / "mvp" / "msa-addendum.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage43_t1_tos_aup.json"

REQUIRED_IDS = {
    "ta-msa-adjacency",
    "ta-billing-deferred",
    "ta-ai-aup",
    "ta-support-sla",
    "ta-release-notes",
    "ta-trial-lifecycle",
    "ta-no-fake-payment",
    "ta-dpa-adjacency",
    "ta-tos-signed-remaining",
    "ta-clickwrap-remaining",
}
REQUIRED_CATEGORIES = {"terms", "commercial", "aup", "privacy", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_tos_aup_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "43"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["tos_signed_claimed"] is False
    assert mapping["aup_enforced_claimed"] is False
    assert mapping["legal_counsel_claimed"] is False
    assert mapping["clickwrap_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/TOS_AUP_MVP.md"
    assert "stage43_t1_tos_aup.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ta-tos-signed-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ta-clickwrap-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ta-msa-adjacency" for s in steps)
    assert any(
        "tos" in d.lower() or "aup" in d.lower() or "clickwrap" in d.lower() or "counsel" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["ai_use_disclosure"],
        mapping["ai_use_disclosure_doc"],
        mapping["support_sla"],
        mapping["support_sla_doc"],
        mapping["release_notes"],
        mapping["release_notes_doc"],
        mapping["dpa_subprocessor"],
        mapping["stage43_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_tos_aup_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    msa = json.loads(MSA.read_text(encoding="utf-8"))
    assert mapping["tos_signed_claimed"] is False
    assert mapping["legal_counsel_claimed"] is False
    assert msa.get("msa_signed_claimed") is False
    assert msa.get("legal_counsel_claimed") is False
    msa_doc = _read("docs/MSA_ADDENDUM_MVP.md")
    assert "MSA" in msa_doc or "addendum" in msa_doc.lower()
    for step in mapping["steps"]:
        assert step["done"] is False
    billing = _read("docs/BILLING_DEFERRED_HONESTY_MVP.md")
    assert "billing" in billing.lower() or "ADR-002" in billing
    ai = _read("docs/AI_USE_DISCLOSURE_MVP.md")
    assert "binding" in ai.lower() or "assistive" in ai.lower() or "not" in ai.lower()


def test_tos_aup_doc_and_readme():
    doc = _read("docs/TOS_AUP_MVP.md")
    assert "Stage 43 T1" in doc
    assert "test_tos_aup_t1.py" in doc
    assert "tos-aup.json" in doc
    assert "stage43_t1_tos_aup.json" in doc
    assert "tos_signed_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "Terms" in doc or "Acceptable" in doc or "ToS" in doc or "AUP" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 43 T1" in readme
    assert "TOS_AUP_MVP.md" in readme
    assert "tos-aup.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_43_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_tos_aup_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H43x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_tos_aup_t1.py" in launch
    assert "Stage 43 T1" in launch
    assert "TOS_AUP_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 43 T1" in roadmap
    assert "test_tos_aup_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 43 T1" in pr
    assert "test_tos_aup_t1.py" in pr or "TOS_AUP_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "43",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/TOS_AUP_MVP.md",
        "register": "ops/mvp/tos-aup.json",
        "packaging_complete": True,
        "tos_signed_claimed": False,
        "aup_enforced_claimed": False,
        "legal_counsel_claimed": False,
        "clickwrap_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["tos_signed_claimed"] is False
    assert loaded["legal_counsel_claimed"] is False
    assert loaded["step_count"] >= 10
