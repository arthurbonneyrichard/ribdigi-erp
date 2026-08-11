"""Stage 77 A1 — Commercial DPA honesty (not signed DPA Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-dpa.json"
DPA = ROOT / "ops" / "mvp" / "dpa-subprocessor.json"
MSA = ROOT / "ops" / "mvp" / "msa-addendum.json"
TERMS = ROOT / "ops" / "mvp" / "commercial-terms.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage77_a1_commercial_dpa.json"

REQUIRED_IDS = {
    "cdpa-owner-outline", "cdpa-stage39", "cdpa-msa", "cdpa-terms", "cdpa-privacy",
    "cdpa-portability", "cdpa-plan-honesty", "cdpa-counsel-review", "cdpa-dpa-remaining", "cdpa-golive-remaining",
}
REQUIRED_CATEGORIES = {"dpa", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_dpa_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "77" and mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    for k in ("dpa_signed_claimed", "subprocessor_register_live", "legal_counsel_claimed",
              "contract_execution_claimed", "tos_signed_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_DPA_MVP.md"
    assert "stage77_a1_commercial_dpa.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cdpa-dpa-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cdpa-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("dpa" in d.lower() or "liability" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage77_plan"], mapping["dpa_doc"], mapping["dpa"], mapping["msa_doc"], mapping["msa"],
                mapping["terms_doc"], mapping["terms"], mapping["privacy_doc"], mapping["privacy"],
                mapping["portability_doc"], mapping["portability"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_dpa_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    dpa = json.loads(DPA.read_text(encoding="utf-8"))
    msa = json.loads(MSA.read_text(encoding="utf-8"))
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    assert mapping["dpa_signed_claimed"] is False
    for key in ("dpa_signed_claimed", "subprocessor_register_live", "go_live_claimed"):
        if key in dpa:
            assert dpa[key] is False
    for key in ("msa_signed_claimed", "go_live_claimed"):
        if key in msa:
            assert msa[key] is False
    for key in ("tos_signed_claimed", "go_live_claimed"):
        if key in terms:
            assert terms[key] is False
    plan = _read("docs/STAGE_77_PLAN.md")
    assert "DPA" in plan and "Liability" in plan


def test_commercial_dpa_doc_and_readme():
    doc = _read("docs/COMMERCIAL_DPA_MVP.md")
    assert "Stage 77 A1" in doc and "test_commercial_dpa_a1.py" in doc
    assert "commercial-dpa.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 77 A1" in readme and "COMMERCIAL_DPA_MVP.md" in readme and "commercial-dpa.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_77_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "test_commercial_dpa_a1.py" in plan
    assert any(x in plan for x in ("A1 next", "A1 complete", "L1 next", "L1 complete", "D1 next", "D1 complete", "H77x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_dpa_a1.py" in launch and "Stage 77 A1" in launch and "COMMERCIAL_DPA_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 77 A1" in roadmap and "test_commercial_dpa_a1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 77 A1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "77", "workstream": "A1", "passed": True, "doc": "docs/COMMERCIAL_DPA_MVP.md",
               "register": "ops/mvp/commercial-dpa.json", "packaging_complete": True,
               "dpa_signed_claimed": False, "subprocessor_register_live": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["dpa_signed_claimed"] is False and loaded["step_count"] >= 10
