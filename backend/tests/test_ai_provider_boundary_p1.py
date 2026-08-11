"""Stage 42 P1 — AI model / provider boundary honesty (not external LLM Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ai-provider-boundary.json"
AI_USE = ROOT / "ops" / "mvp" / "ai-use-disclosure.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage42_p1_ai_provider_boundary.json"

REQUIRED_IDS = {
    "ap-stage24-provider-gate",
    "ap-optional-llm-unset",
    "ap-rules-deterministic",
    "ap-stage20-llm-remaining",
    "ap-prophet-remaining",
    "ap-ai-guard",
    "ap-use-disclosure-adjacency",
    "ap-isolationforest-remaining",
    "ap-external-llm-configure-remaining",
    "ap-output-pii-remaining",
}
REQUIRED_CATEGORIES = {"provider", "model", "security", "disclosure", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ai_provider_boundary_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "42"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    assert mapping["external_llm_claimed"] is False
    assert mapping["prophet_claimed"] is False
    assert mapping["paid_model_vendor_required"] is False
    assert mapping["output_pii_scanner_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/AI_PROVIDER_BOUNDARY_MVP.md"
    assert "stage42_p1_ai_provider_boundary.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ap-stage20-llm-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ap-prophet-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ap-stage24-provider-gate" for s in steps)
    assert any(
        "llm" in d.lower() or "prophet" in d.lower() or "isolation" in d.lower() or "pii" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["ai_use_disclosure"],
        mapping["ai_use_disclosure_doc"],
        mapping["stage20_fidelity"],
        mapping["stage20_exit"],
        mapping["stage24_plan"],
        mapping["security_guide"],
        mapping["production_readiness"],
        mapping["ops_ai_gate_test"],
        mapping["stage42_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_ai_provider_boundary_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    ai_use = json.loads(AI_USE.read_text(encoding="utf-8"))
    assert mapping["external_llm_claimed"] is False
    assert mapping["prophet_claimed"] is False
    assert ai_use.get("external_llm_claimed") is False
    s20 = _read("docs/STAGE_20_FIDELITY.md")
    assert "External LLM" in s20 or "external LLM" in s20.lower() or "Prophet" in s20
    s24 = _read("docs/STAGE_24_PLAN.md")
    assert "O1" in s24 and ("AI" in s24 or "provider" in s24.lower())
    assert "test_ops_ai_gate_closure_o1.py" in s24
    for step in mapping["steps"]:
        assert step["done"] is False
    pr = _read("PRODUCTION_READINESS.md")
    assert "external LLM" in pr or "LLM" in pr
    assert "ai_guard" in pr or "provider" in pr.lower()
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "ai_guard" in sec or "AI Security" in sec


def test_ai_provider_boundary_doc_and_readme():
    doc = _read("docs/AI_PROVIDER_BOUNDARY_MVP.md")
    assert "Stage 42 P1" in doc
    assert "test_ai_provider_boundary_p1.py" in doc
    assert "ai-provider-boundary.json" in doc
    assert "stage42_p1_ai_provider_boundary.json" in doc
    assert "external_llm_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "provider" in doc.lower() or "LLM" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 42 P1" in readme
    assert "AI_PROVIDER_BOUNDARY_MVP.md" in readme
    assert "ai-provider-boundary.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_42_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_ai_provider_boundary_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H42x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
        or "A1 complete" in plan
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ai_provider_boundary_p1.py" in launch
    assert "Stage 42 P1" in launch
    assert "AI_PROVIDER_BOUNDARY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 42 P1" in roadmap
    assert "test_ai_provider_boundary_p1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 42 P1" in pr
    assert "test_ai_provider_boundary_p1.py" in pr or "AI_PROVIDER_BOUNDARY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "42",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/AI_PROVIDER_BOUNDARY_MVP.md",
        "register": "ops/mvp/ai-provider-boundary.json",
        "packaging_complete": True,
        "external_llm_claimed": False,
        "prophet_claimed": False,
        "paid_model_vendor_required": False,
        "output_pii_scanner_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["external_llm_claimed"] is False
    assert loaded["prophet_claimed"] is False
    assert loaded["step_count"] >= 10
