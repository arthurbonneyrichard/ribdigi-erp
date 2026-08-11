"""Stage 67 C1 — Post-launch continuity honesty (not live continuity Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "post-launch-continuity.json"
HANDOFF = ROOT / "ops" / "mvp" / "operator-handoff.json"
KT = ROOT / "ops" / "mvp" / "knowledge-transfer.json"
HYPER = ROOT / "ops" / "mvp" / "production-hypercare.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage67_c1_post_launch_continuity.json"

REQUIRED_IDS = {
    "plc-owner-outline",
    "plc-operator-handoff",
    "plc-knowledge-transfer",
    "plc-residual-risk",
    "plc-customer-training",
    "plc-first-tenant",
    "plc-hypercare",
    "plc-plan-honesty",
    "plc-continuity-remaining",
    "plc-handoff-remaining",
    "plc-success-remaining",
}
REQUIRED_CATEGORIES = {"continuity", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_post_launch_continuity_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "67"
    assert mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    assert mapping["post_launch_continuity_live_claimed"] is False
    assert mapping["handoff_complete_claimed"] is False
    assert mapping["live_training_claimed"] is False
    assert mapping["training_complete_claimed"] is False
    assert mapping["customer_success_stabilization_claimed"] is False
    assert mapping["risks_closed_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/POST_LAUNCH_CONTINUITY_MVP.md"
    assert "stage67_c1_post_launch_continuity.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "plc-continuity-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "plc-handoff-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "plc-success-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "continuity" in d.lower() or "handoff" in d.lower() or "training" in d.lower() or "success" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage67_plan"],
        mapping["operator_handoff_doc"],
        mapping["operator_handoff"],
        mapping["knowledge_transfer_doc"],
        mapping["knowledge_transfer"],
        mapping["residual_risk_doc"],
        mapping["residual_risk"],
        mapping["customer_training_doc"],
        mapping["customer_training"],
        mapping["first_tenant_golive_doc"],
        mapping["first_tenant_golive"],
        mapping["production_hypercare_doc"],
        mapping["production_hypercare"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_post_launch_continuity_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    kt = json.loads(KT.read_text(encoding="utf-8"))
    hyper = json.loads(HYPER.read_text(encoding="utf-8"))
    assert mapping["post_launch_continuity_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    for key in ("handoff_complete_claimed", "go_live_claimed", "section_7_signed"):
        if key in handoff:
            assert handoff[key] is False
    for key in ("live_training_claimed", "training_complete_claimed", "go_live_claimed"):
        if key in kt:
            assert kt[key] is False
    for key in ("production_hypercare_live_claimed", "go_live_claimed", "section_7_signed"):
        if key in hyper:
            assert hyper[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_67_PLAN.md")
    assert "Post-Launch Continuity" in plan or "continuity" in plan.lower()
    assert "Steady-State" in plan or "handoff" in plan.lower()


def test_post_launch_continuity_doc_and_readme():
    doc = _read("docs/POST_LAUNCH_CONTINUITY_MVP.md")
    assert "Stage 67 C1" in doc
    assert "test_post_launch_continuity_c1.py" in doc
    assert "post-launch-continuity.json" in doc
    assert "stage67_c1_post_launch_continuity.json" in doc
    assert "post_launch_continuity_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "continuity" in doc.lower() or "handoff" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 67 C1" in readme
    assert "POST_LAUNCH_CONTINUITY_MVP.md" in readme
    assert "post-launch-continuity.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_67_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_post_launch_continuity_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H67x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_post_launch_continuity_c1.py" in launch
    assert "Stage 67 C1" in launch
    assert "POST_LAUNCH_CONTINUITY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 67 C1" in roadmap
    assert "test_post_launch_continuity_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 67 C1" in pr
    assert "test_post_launch_continuity_c1.py" in pr or "POST_LAUNCH_CONTINUITY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "67",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/POST_LAUNCH_CONTINUITY_MVP.md",
        "register": "ops/mvp/post-launch-continuity.json",
        "packaging_complete": True,
        "post_launch_continuity_live_claimed": False,
        "handoff_complete_claimed": False,
        "live_training_claimed": False,
        "customer_success_stabilization_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["post_launch_continuity_live_claimed"] is False
    assert loaded["handoff_complete_claimed"] is False
    assert loaded["step_count"] >= 10
