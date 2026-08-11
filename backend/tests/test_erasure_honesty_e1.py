"""Stage 37 E1 — Erasure / soft-delete honesty (not hard-delete Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "erasure-honesty.json"
DEFERRED = ROOT / "ops" / "mvp" / "deferred-adr-register.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage37_e1_erasure_honesty.json"

REQUIRED_IDS = {
    "eh-adr003-accepted",
    "eh-soft-delete-api",
    "eh-user-deactivated-audit",
    "eh-reactivation",
    "eh-no-hard-delete-api",
    "eh-self-deactivate-forbidden",
    "eh-deferred-adr-register",
    "eh-post-mvp-backlog",
    "eh-product-soft-deactivate",
    "eh-hard-delete-remaining",
}
REQUIRED_CATEGORIES = {"adr", "soft-delete", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_erasure_honesty_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "37"
    assert mapping["workstream"] == "E1"
    assert mapping["packaging_complete"] is True
    assert mapping["hard_delete_claimed"] is False
    assert mapping["erasure_complete_claimed"] is False
    assert mapping["anonymize_workflow_claimed"] is False
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/ERASURE_HONESTY_MVP.md"
    assert "stage37_e1_erasure_honesty.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "eh-hard-delete-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "eh-adr003-accepted" for s in steps)
    assert any(
        "hard-delete" in d.lower()
        or "hard delete" in d.lower()
        or "erasure" in d.lower()
        or "anonymize" in d.lower()
        or "adr-003" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["adr_003"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_doc"],
        mapping["post_mvp_backlog"],
        mapping["post_mvp_doc"],
        mapping["data_portability"],
        mapping["data_portability_doc"],
        mapping["api_documentation"],
        mapping["stage37_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_erasure_honesty_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    deferred = json.loads(DEFERRED.read_text(encoding="utf-8"))
    assert mapping["hard_delete_claimed"] is False
    assert mapping["erasure_complete_claimed"] is False
    adr_rows = deferred.get("adrs") or deferred.get("items") or deferred.get("entries") or []
    if not adr_rows and isinstance(deferred, dict):
        # find ADR-003 somewhere in structure
        blob = json.dumps(deferred)
        assert "ADR-003" in blob
        assert "soft" in blob.lower() or "hard" in blob.lower()
    else:
        adr003 = next((r for r in adr_rows if r.get("id") == "ADR-003" or "003" in str(r.get("id", ""))), None)
        assert adr003 is not None
        assert "soft" in json.dumps(adr003).lower() or "hard" in json.dumps(adr003).lower()
    for step in mapping["steps"]:
        assert step["done"] is False
    adr = _read("docs/ADR_003_USER_DELETE_POLICY.md")
    assert "Soft-delete" in adr or "soft-delete" in adr.lower() or "soft delete" in adr.lower()
    assert "hard" in adr.lower()
    api = _read("docs/API_DOCUMENTATION.md")
    assert "user_deactivated" in api or "ADR-003" in api
    assert "hard-delete" in api.lower() or "hard delete" in api.lower() or "not removed" in api.lower()


def test_erasure_honesty_doc_and_readme():
    doc = _read("docs/ERASURE_HONESTY_MVP.md")
    assert "Stage 37 E1" in doc
    assert "test_erasure_honesty_e1.py" in doc
    assert "erasure-honesty.json" in doc
    assert "stage37_e1_erasure_honesty.json" in doc
    assert "hard_delete_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "ADR-003" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 37 E1" in readme
    assert "ERASURE_HONESTY_MVP.md" in readme
    assert "erasure-honesty.json" in readme


def test_e1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_37_PLAN.md")
    e1_line = [ln for ln in plan.splitlines() if "| **E1** |" in ln][0]
    assert "COMPLETE" in e1_line
    assert "test_erasure_honesty_e1.py" in plan
    assert (
        "E1 next" in plan
        or "E1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H37x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_erasure_honesty_e1.py" in launch
    assert "Stage 37 E1" in launch
    assert "ERASURE_HONESTY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 37 E1" in roadmap
    assert "test_erasure_honesty_e1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 37 E1" in pr
    assert "test_erasure_honesty_e1.py" in pr or "ERASURE_HONESTY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "37",
        "workstream": "E1",
        "passed": True,
        "doc": "docs/ERASURE_HONESTY_MVP.md",
        "register": "ops/mvp/erasure-honesty.json",
        "packaging_complete": True,
        "hard_delete_claimed": False,
        "erasure_complete_claimed": False,
        "anonymize_workflow_claimed": False,
        "deferred_implemented_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["hard_delete_claimed"] is False
    assert loaded["erasure_complete_claimed"] is False
    assert loaded["anonymize_workflow_claimed"] is False
    assert loaded["step_count"] >= 10
