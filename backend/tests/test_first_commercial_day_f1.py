"""Stage 70 F1 — First commercial day ops honesty (not first-day live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-commercial-day.json"
LAUNCH = ROOT / "ops" / "mvp" / "production-launch.json"
HYPERCARE = ROOT / "ops" / "mvp" / "production-hypercare.json"
PREFLIGHT = ROOT / "ops" / "mvp" / "preflight-verification.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage70_f1_first_commercial_day.json"

REQUIRED_IDS = {
    "fcd-owner-outline",
    "fcd-production-launch",
    "fcd-first-tenant",
    "fcd-hypercare",
    "fcd-preflight",
    "fcd-attestation",
    "fcd-support-sla",
    "fcd-plan-honesty",
    "fcd-first-day-remaining",
    "fcd-golive-remaining",
}
REQUIRED_CATEGORIES = {"day_ops", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_first_commercial_day_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "70"
    assert mapping["workstream"] == "F1"
    assert mapping["packaging_complete"] is True
    assert mapping["first_commercial_day_claimed"] is False
    assert mapping["commercial_day_ops_live_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["doc"] == "docs/FIRST_COMMERCIAL_DAY_MVP.md"
    assert "stage70_f1_first_commercial_day.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "fcd-first-day-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "fcd-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "first" in d.lower() or "day" in d.lower() or "go-live" in d.lower() or "section" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage70_plan"],
        mapping["production_launch_doc"],
        mapping["production_launch"],
        mapping["first_tenant_doc"],
        mapping["first_tenant"],
        mapping["hypercare_doc"],
        mapping["hypercare"],
        mapping["preflight_doc"],
        mapping["preflight"],
        mapping["golive_attestation_doc"],
        mapping["golive_attestation"],
        mapping["support_sla_doc"],
        mapping["support_sla"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_first_commercial_day_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    launch = json.loads(LAUNCH.read_text(encoding="utf-8"))
    hypercare = json.loads(HYPERCARE.read_text(encoding="utf-8"))
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    assert mapping["first_commercial_day_claimed"] is False
    assert mapping["go_live_claimed"] is False
    for key in ("go_live_claimed", "section_7_signed", "production_cutover_claimed"):
        if key in launch:
            assert launch[key] is False
    for key in ("production_hypercare_live_claimed", "go_live_claimed", "section_7_signed"):
        if key in hypercare:
            assert hypercare[key] is False
    for key in ("sections_1_3_verified", "section_7_signed", "go_live_claimed"):
        if key in preflight:
            assert preflight[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_70_PLAN.md")
    assert "First Commercial Day" in plan
    assert "Go-Live" in plan or "go-live" in plan.lower() or "Closeout" in plan


def test_first_commercial_day_doc_and_readme():
    doc = _read("docs/FIRST_COMMERCIAL_DAY_MVP.md")
    assert "Stage 70 F1" in doc
    assert "test_first_commercial_day_f1.py" in doc
    assert "first-commercial-day.json" in doc
    assert "first_commercial_day_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 70 F1" in readme
    assert "FIRST_COMMERCIAL_DAY_MVP.md" in readme
    assert "first-commercial-day.json" in readme


def test_f1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_70_PLAN.md")
    f1_line = [ln for ln in plan.splitlines() if "| **F1** |" in ln][0]
    assert "COMPLETE" in f1_line
    assert "test_first_commercial_day_f1.py" in plan
    assert (
        "F1 next" in plan
        or "F1 complete" in plan
        or "G1 next" in plan
        or "G1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H70x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_first_commercial_day_f1.py" in launch
    assert "Stage 70 F1" in launch
    assert "FIRST_COMMERCIAL_DAY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 70 F1" in roadmap
    assert "test_first_commercial_day_f1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 70 F1" in pr
    assert "test_first_commercial_day_f1.py" in pr or "FIRST_COMMERCIAL_DAY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "70",
        "workstream": "F1",
        "passed": True,
        "doc": "docs/FIRST_COMMERCIAL_DAY_MVP.md",
        "register": "ops/mvp/first-commercial-day.json",
        "packaging_complete": True,
        "first_commercial_day_claimed": False,
        "commercial_day_ops_live_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["first_commercial_day_claimed"] is False
    assert loaded["step_count"] >= 10
