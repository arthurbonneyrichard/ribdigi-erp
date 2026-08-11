"""Stage 52 I1 — industry partnerships honesty (not live industry partnership program Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "industry-partnerships.json"
PARTNER = ROOT / "ops" / "mvp" / "partner-reseller.json"
MARKETPLACE = ROOT / "ops" / "mvp" / "marketplace-presence.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage52_i1_industry_partnerships.json"

REQUIRED_IDS = {
    "ip-product-overview",
    "ip-partner-adjacency",
    "ip-marketplace-adjacency",
    "ip-referral-adjacency",
    "ip-billing-deferred",
    "ip-deferred-adr",
    "ip-roadmap-backlog",
    "ip-plan-honesty",
    "ip-program-remaining",
    "ip-deals-remaining",
}
REQUIRED_CATEGORIES = {"industry", "partnership", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_industry_partnerships_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "52"
    assert mapping["workstream"] == "I1"
    assert mapping["packaging_complete"] is True
    assert mapping["industry_partnership_program_live"] is False
    assert mapping["signed_association_deals_claimed"] is False
    assert mapping["federation_endorsement_claimed"] is False
    assert mapping["guild_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/INDUSTRY_PARTNERSHIPS_MVP.md"
    assert "stage52_i1_industry_partnerships.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ip-program-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ip-deals-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "partnership" in d.lower() or "association" in d.lower() or "guild" in d.lower() or "federation" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["marketplace_presence"],
        mapping["marketplace_presence_doc"],
        mapping["referral_program"],
        mapping["referral_program_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage52_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_industry_partnerships_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    partner = json.loads(PARTNER.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    assert mapping["industry_partnership_program_live"] is False
    assert mapping["signed_association_deals_claimed"] is False
    assert partner.get("partner_program_live") is False
    assert marketplace.get("marketplace_listing_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "Industry Partnerships" in po or "association" in po.lower() or "federation" in po.lower()


def test_industry_partnerships_doc_and_readme():
    doc = _read("docs/INDUSTRY_PARTNERSHIPS_MVP.md")
    assert "Stage 52 I1" in doc
    assert "test_industry_partnerships_i1.py" in doc
    assert "industry-partnerships.json" in doc
    assert "stage52_i1_industry_partnerships.json" in doc
    assert "industry_partnership_program_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "partnership" in doc.lower() or "industry" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 52 I1" in readme
    assert "INDUSTRY_PARTNERSHIPS_MVP.md" in readme
    assert "industry-partnerships.json" in readme


def test_i1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_52_PLAN.md")
    i1_line = [ln for ln in plan.splitlines() if "| **I1** |" in ln][0]
    assert "COMPLETE" in i1_line
    assert "test_industry_partnerships_i1.py" in plan
    assert (
        "I1 next" in plan
        or "I1 complete" in plan
        or "R1 next" in plan
        or "R1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H52x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_industry_partnerships_i1.py" in launch
    assert "Stage 52 I1" in launch
    assert "INDUSTRY_PARTNERSHIPS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 52 I1" in roadmap
    assert "test_industry_partnerships_i1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 52 I1" in pr
    assert "test_industry_partnerships_i1.py" in pr or "INDUSTRY_PARTNERSHIPS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "52",
        "workstream": "I1",
        "passed": True,
        "doc": "docs/INDUSTRY_PARTNERSHIPS_MVP.md",
        "register": "ops/mvp/industry-partnerships.json",
        "packaging_complete": True,
        "industry_partnership_program_live": False,
        "signed_association_deals_claimed": False,
        "federation_endorsement_claimed": False,
        "guild_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["industry_partnership_program_live"] is False
    assert loaded["signed_association_deals_claimed"] is False
    assert loaded["step_count"] >= 10
