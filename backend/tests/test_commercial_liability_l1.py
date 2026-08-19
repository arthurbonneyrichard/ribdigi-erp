"""Stage 77 L1 — Commercial liability honesty (not liability cap signed Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-liability.json"
LIABILITY = ROOT / "ops" / "mvp" / "liability-indemnity.json"
DPA = ROOT / "ops" / "mvp" / "commercial-dpa.json"
TERMS = ROOT / "ops" / "mvp" / "commercial-terms.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage77_l1_commercial_liability.json"

REQUIRED_IDS = {
    "cli-owner-outline", "cli-stage46", "cli-dpa", "cli-terms", "cli-msa",
    "cli-tos-aup", "cli-plan-honesty", "cli-counsel-review", "cli-liability-remaining", "cli-golive-remaining",
}
REQUIRED_CATEGORIES = {"liability", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_liability_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "77" and mapping["workstream"] == "L1"
    assert mapping["packaging_complete"] is True
    for k in ("liability_cap_claimed", "indemnity_signed_claimed", "legal_counsel_claimed",
              "contract_liability_live", "dpa_signed_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_LIABILITY_MVP.md"
    assert "stage77_l1_commercial_liability.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cli-liability-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cli-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("liability" in d.lower() or "indemnity" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage77_plan"], mapping["liability_doc"], mapping["liability"],
                mapping["dpa_commercial_doc"], mapping["dpa_commercial"], mapping["terms_doc"], mapping["terms"],
                mapping["msa_doc"], mapping["msa"], mapping["tos_aup_doc"], mapping["tos_aup"],
                mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_liability_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    liability = json.loads(LIABILITY.read_text(encoding="utf-8"))
    dpa = json.loads(DPA.read_text(encoding="utf-8"))
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    assert mapping["liability_cap_claimed"] is False
    for key in ("liability_cap_claimed", "indemnity_signed_claimed", "contract_liability_live", "go_live_claimed"):
        if key in liability:
            assert liability[key] is False
    for key in ("dpa_signed_claimed", "go_live_claimed"):
        if key in dpa:
            assert dpa[key] is False
    for key in ("tos_signed_claimed", "go_live_claimed"):
        if key in terms:
            assert terms[key] is False
    plan = _read("docs/STAGE_77_PLAN.md")
    assert "Liability" in plan and "DPA" in plan


def test_commercial_liability_doc_and_readme():
    doc = _read("docs/COMMERCIAL_LIABILITY_MVP.md")
    assert "Stage 77 L1" in doc and "test_commercial_liability_l1.py" in doc
    assert "commercial-liability.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 77 L1" in readme and "COMMERCIAL_LIABILITY_MVP.md" in readme and "commercial-liability.json" in readme


def test_l1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_77_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **L1** |" in ln][0]
    assert "test_commercial_liability_l1.py" in plan
    assert any(x in plan for x in ("L1 next", "L1 complete", "D1 next", "D1 complete", "H77x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_liability_l1.py" in launch and "Stage 77 L1" in launch and "COMMERCIAL_LIABILITY_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 77 L1" in roadmap and "test_commercial_liability_l1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 77 L1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "77", "workstream": "L1", "passed": True, "doc": "docs/COMMERCIAL_LIABILITY_MVP.md",
               "register": "ops/mvp/commercial-liability.json", "packaging_complete": True,
               "liability_cap_claimed": False, "indemnity_signed_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["liability_cap_claimed"] is False and loaded["step_count"] >= 10
