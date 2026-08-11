"""Stage 73 E1 — Commercial evidence chain honesty (not evidence chain live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-evidence-chain.json"
LEDGER = ROOT / "ops" / "evidence" / "ledger.json"
RESIDUAL = ROOT / "ops" / "mvp" / "commercial-residual.json"
ATTEST = ROOT / "ops" / "mvp" / "golive-attestation.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage73_e1_commercial_evidence_chain.json"

REQUIRED_IDS = {
    "cec-owner-outline", "cec-ledger", "cec-attestation", "cec-residual", "cec-archive",
    "cec-golive-attest", "cec-mvp-declaration", "cec-plan-honesty",
    "cec-evidence-remaining", "cec-golive-remaining",
}
REQUIRED_CATEGORIES = {"evidence", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_evidence_chain_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "73" and mapping["workstream"] == "E1"
    assert mapping["packaging_complete"] is True
    for k in ("evidence_chain_live_claimed", "customer_assurance_claimed", "assurance_claimed",
              "residual_closed_claimed", "go_live_claimed", "section_7_signed", "attestation_claimed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md"
    assert "stage73_e1_commercial_evidence_chain.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cec-evidence-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cec-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("evidence" in d.lower() or "assurance" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage73_plan"], mapping["evidence_ledger_doc"], mapping["evidence_ledger"],
                mapping["attestation_doc"], mapping["attestation_matrix"],
                mapping["residual_doc"], mapping["residual"], mapping["archive_doc"], mapping["archive"],
                mapping["golive_attestation_doc"], mapping["golive_attestation"],
                mapping["mvp_declaration_doc"], mapping["mvp_declaration"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_evidence_chain_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    attest = json.loads(ATTEST.read_text(encoding="utf-8"))
    assert mapping["evidence_chain_live_claimed"] is False
    assert LEDGER.is_file()
    for key in ("residual_closed_claimed", "go_live_claimed"):
        if key in residual:
            assert residual[key] is False
    for key in ("section_7_signed", "attestation_claimed", "go_live_claimed"):
        if key in attest:
            assert attest[key] is False
    plan = _read("docs/STAGE_73_PLAN.md")
    assert "Evidence" in plan and "Assurance" in plan


def test_commercial_evidence_chain_doc_and_readme():
    doc = _read("docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md")
    assert "Stage 73 E1" in doc and "test_commercial_evidence_chain_e1.py" in doc
    assert "commercial-evidence-chain.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 73 E1" in readme and "COMMERCIAL_EVIDENCE_CHAIN_MVP.md" in readme and "commercial-evidence-chain.json" in readme


def test_e1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_73_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **E1** |" in ln][0]
    assert "test_commercial_evidence_chain_e1.py" in plan
    assert any(x in plan for x in ("E1 next", "E1 complete", "A1 next", "A1 complete", "D1 next", "D1 complete", "H73x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_evidence_chain_e1.py" in launch and "Stage 73 E1" in launch and "COMMERCIAL_EVIDENCE_CHAIN_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 73 E1" in roadmap and "test_commercial_evidence_chain_e1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 73 E1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "73", "workstream": "E1", "passed": True, "doc": "docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md",
               "register": "ops/mvp/commercial-evidence-chain.json", "packaging_complete": True,
               "evidence_chain_live_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["evidence_chain_live_claimed"] is False and loaded["step_count"] >= 10
