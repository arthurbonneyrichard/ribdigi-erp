"""Stage 42 A1 — AI use disclosure honesty (not AI certification Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ai-use-disclosure.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage42_a1_ai_use_disclosure.json"

REQUIRED_IDS = {
    "ai-stage20-fidelity",
    "ai-chat-rule-based",
    "ai-insights-assistive",
    "ai-ocr-human-confirm",
    "ai-security-guide",
    "ai-rbac-tenant",
    "ai-audit-redaction",
    "ai-not-binding-advice",
    "ai-certification-remaining",
    "ai-output-pii-remaining",
}
REQUIRED_CATEGORIES = {"disclosure", "assistive", "security", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ai_use_disclosure_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "42"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["ai_certification_claimed"] is False
    assert mapping["ai_advice_binding_claimed"] is False
    assert mapping["external_llm_claimed"] is False
    assert mapping["output_pii_scanner_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/AI_USE_DISCLOSURE_MVP.md"
    assert "stage42_a1_ai_use_disclosure.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ai-certification-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ai-output-pii-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ai-stage20-fidelity" for s in steps)
    assert any(
        "ai" in d.lower() or "llm" in d.lower() or "certification" in d.lower() or "pii" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage20_fidelity"],
        mapping["stage20_exit"],
        mapping["stage20_plan"],
        mapping["security_guide"],
        mapping["business_requirements"],
        mapping["production_readiness"],
        mapping["stage42_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_ai_use_disclosure_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["ai_certification_claimed"] is False
    assert mapping["external_llm_claimed"] is False
    s20 = _read("docs/STAGE_20_FIDELITY.md")
    assert "BR-21" in s20 or "AI" in s20
    assert "External LLM" in s20 or "external LLM" in s20.lower() or "LLM" in s20
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "AI Security" in sec or "ai_guard" in sec
    assert "ai_guard" in sec or "prompt injection" in sec.lower()
    for step in mapping["steps"]:
        assert step["done"] is False
    pr = _read("PRODUCTION_READINESS.md")
    assert "ai_guard" in pr or "external LLM" in pr or "BR-21" in pr
    assert "ocr-apply" in pr.lower() or "human-confirmed" in pr.lower() or "OCR" in pr


def test_ai_use_disclosure_doc_and_readme():
    doc = _read("docs/AI_USE_DISCLOSURE_MVP.md")
    assert "Stage 42 A1" in doc
    assert "test_ai_use_disclosure_a1.py" in doc
    assert "ai-use-disclosure.json" in doc
    assert "stage42_a1_ai_use_disclosure.json" in doc
    assert "ai_certification_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "AI" in doc or "disclosure" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 42 A1" in readme
    assert "AI_USE_DISCLOSURE_MVP.md" in readme
    assert "ai-use-disclosure.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_42_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_ai_use_disclosure_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "P1 next" in plan
        or "P1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H42x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ai_use_disclosure_a1.py" in launch
    assert "Stage 42 A1" in launch
    assert "AI_USE_DISCLOSURE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 42 A1" in roadmap
    assert "test_ai_use_disclosure_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 42 A1" in pr
    assert "test_ai_use_disclosure_a1.py" in pr or "AI_USE_DISCLOSURE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "42",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/AI_USE_DISCLOSURE_MVP.md",
        "register": "ops/mvp/ai-use-disclosure.json",
        "packaging_complete": True,
        "ai_certification_claimed": False,
        "ai_advice_binding_claimed": False,
        "external_llm_claimed": False,
        "output_pii_scanner_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["ai_certification_claimed"] is False
    assert loaded["external_llm_claimed"] is False
    assert loaded["step_count"] >= 10
