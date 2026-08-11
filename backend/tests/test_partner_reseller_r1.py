"""Stage 49 R1 — partner / reseller honesty (not live partner program Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "partner-reseller.json"
TOS = ROOT / "ops" / "mvp" / "tos-aup.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage49_r1_partner_reseller.json"

REQUIRED_IDS = {
    "pr-product-overview",
    "pr-tos-adjacency",
    "pr-msa-adjacency",
    "pr-billing-deferred",
    "pr-sow-adjacency",
    "pr-deferred-adr",
    "pr-roadmap-backlog",
    "pr-plan-honesty",
    "pr-program-remaining",
    "pr-reseller-remaining",
}
REQUIRED_CATEGORIES = {"partner", "reseller", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_partner_reseller_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "49"
    assert mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    assert mapping["partner_program_live"] is False
    assert mapping["signed_reseller_agreement_claimed"] is False
    assert mapping["white_label_live_claimed"] is False
    assert mapping["channel_commission_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/PARTNER_RESELLER_MVP.md"
    assert "stage49_r1_partner_reseller.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "pr-program-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "pr-reseller-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "partner" in d.lower() or "reseller" in d.lower() or "white-label" in d.lower() or "commission" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["tos_aup"],
        mapping["tos_aup_doc"],
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["professional_services_sow"],
        mapping["professional_services_sow_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage49_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_partner_reseller_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    tos = json.loads(TOS.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    assert mapping["partner_program_live"] is False
    assert mapping["signed_reseller_agreement_claimed"] is False
    assert tos.get("tos_signed_claimed") is False
    assert billing.get("billing_complete_claimed") is False or billing.get("packaging_complete") is True
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "reseller" in po.lower() or "white-label" in po.lower() or "White-Label" in po
    tos_doc = _read("docs/TOS_AUP_MVP.md")
    assert "ToS" in tos_doc or "AUP" in tos_doc or "Terms" in tos_doc


def test_partner_reseller_doc_and_readme():
    doc = _read("docs/PARTNER_RESELLER_MVP.md")
    assert "Stage 49 R1" in doc
    assert "test_partner_reseller_r1.py" in doc
    assert "partner-reseller.json" in doc
    assert "stage49_r1_partner_reseller.json" in doc
    assert "partner_program_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "reseller" in doc.lower() or "partner" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 49 R1" in readme
    assert "PARTNER_RESELLER_MVP.md" in readme
    assert "partner-reseller.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_49_PLAN.md")
    r1_line = [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_partner_reseller_r1.py" in plan
    assert (
        "R1 next" in plan
        or "R1 complete" in plan
        or "L1 next" in plan
        or "L1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H49x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_partner_reseller_r1.py" in launch
    assert "Stage 49 R1" in launch
    assert "PARTNER_RESELLER_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 49 R1" in roadmap
    assert "test_partner_reseller_r1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 49 R1" in pr
    assert "test_partner_reseller_r1.py" in pr or "PARTNER_RESELLER_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "49",
        "workstream": "R1",
        "passed": True,
        "doc": "docs/PARTNER_RESELLER_MVP.md",
        "register": "ops/mvp/partner-reseller.json",
        "packaging_complete": True,
        "partner_program_live": False,
        "signed_reseller_agreement_claimed": False,
        "white_label_live_claimed": False,
        "channel_commission_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["partner_program_live"] is False
    assert loaded["signed_reseller_agreement_claimed"] is False
    assert loaded["step_count"] >= 10
