"""Stage 73 A1 — Commercial assurance boundary honesty (not customer assurance Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-assurance.json"
ASSURE = ROOT / "ops" / "mvp" / "assurance-evidence.json"
CHAIN = ROOT / "ops" / "mvp" / "commercial-evidence-chain.json"
ACCEPT = ROOT / "ops" / "mvp" / "commercial-acceptance.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage73_a1_commercial_assurance.json"

REQUIRED_IDS = {
    "ca-owner-outline", "ca-assurance-evidence", "ca-evidence-chain", "ca-acceptance",
    "ca-residual", "ca-golive-attest", "ca-compliance", "ca-plan-honesty",
    "ca-assurance-remaining", "ca-golive-remaining",
}
REQUIRED_CATEGORIES = {"assurance", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_assurance_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "73" and mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    for k in ("customer_assurance_claimed", "assurance_claimed", "evidence_chain_live_claimed",
              "commercial_acceptance_claimed", "go_live_claimed", "section_7_signed", "attestation_claimed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_ASSURANCE_MVP.md"
    assert "stage73_a1_commercial_assurance.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "ca-assurance-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ca-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("assurance" in d.lower() or "evidence" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage73_plan"], mapping["assurance_doc"], mapping["assurance"],
                mapping["evidence_chain_doc"], mapping["evidence_chain"],
                mapping["acceptance_doc"], mapping["acceptance"],
                mapping["residual_doc"], mapping["residual"],
                mapping["golive_attestation_doc"], mapping["golive_attestation"],
                mapping["compliance_doc"], mapping["compliance"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_assurance_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assure = json.loads(ASSURE.read_text(encoding="utf-8"))
    chain = json.loads(CHAIN.read_text(encoding="utf-8"))
    accept = json.loads(ACCEPT.read_text(encoding="utf-8"))
    assert mapping["customer_assurance_claimed"] is False
    for key in ("customer_assurance_claimed", "assurance_claimed", "attestation_claimed"):
        if key in assure:
            assert assure[key] is False
    for key in ("evidence_chain_live_claimed", "go_live_claimed"):
        if key in chain:
            assert chain[key] is False
    for key in ("commercial_acceptance_claimed", "go_live_claimed"):
        if key in accept:
            assert accept[key] is False
    plan = _read("docs/STAGE_73_PLAN.md")
    assert "Assurance" in plan and "Evidence" in plan


def test_commercial_assurance_doc_and_readme():
    doc = _read("docs/COMMERCIAL_ASSURANCE_MVP.md")
    assert "Stage 73 A1" in doc and "test_commercial_assurance_a1.py" in doc
    assert "commercial-assurance.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 73 A1" in readme and "COMMERCIAL_ASSURANCE_MVP.md" in readme and "commercial-assurance.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_73_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "test_commercial_assurance_a1.py" in plan
    assert any(x in plan for x in ("A1 next", "A1 complete", "D1 next", "D1 complete", "H73x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_assurance_a1.py" in launch and "Stage 73 A1" in launch and "COMMERCIAL_ASSURANCE_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 73 A1" in roadmap and "test_commercial_assurance_a1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 73 A1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "73", "workstream": "A1", "passed": True, "doc": "docs/COMMERCIAL_ASSURANCE_MVP.md",
               "register": "ops/mvp/commercial-assurance.json", "packaging_complete": True,
               "customer_assurance_claimed": False, "assurance_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["customer_assurance_claimed"] is False and loaded["step_count"] >= 10
