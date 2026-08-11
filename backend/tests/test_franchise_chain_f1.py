"""Stage 64 F1 — Franchise & chain enterprise honesty (not live franchise deals Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "franchise-chain.json"
WHITE = ROOT / "ops" / "mvp" / "white-label-licensing.json"
PARTNER = ROOT / "ops" / "mvp" / "partner-reseller.json"
DIRECT = ROOT / "ops" / "mvp" / "direct-sales.json"
INDUSTRY = ROOT / "ops" / "mvp" / "industry-partnerships.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage64_f1_franchise_chain.json"

REQUIRED_IDS = {
    "fc-product-overview",
    "fc-white-label",
    "fc-partner-reseller",
    "fc-direct-sales",
    "fc-industry-partnerships",
    "fc-advanced-bi",
    "fc-plan-honesty",
    "fc-franchise-remaining",
    "fc-chain-deals-remaining",
    "fc-network-remaining",
}
REQUIRED_CATEGORIES = {"franchise", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_franchise_chain_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "64"
    assert mapping["workstream"] == "F1"
    assert mapping["packaging_complete"] is True
    assert mapping["franchise_chain_live_claimed"] is False
    assert mapping["chain_enterprise_deals_claimed"] is False
    assert mapping["franchise_deal_program_live"] is False
    assert mapping["franchise_network_live_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/FRANCHISE_CHAIN_MVP.md"
    assert "stage64_f1_franchise_chain.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "fc-franchise-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "fc-chain-deals-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "franchise" in d.lower() or "chain" in d.lower() for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["white_label_licensing"],
        mapping["white_label_licensing_doc"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["direct_sales"],
        mapping["direct_sales_doc"],
        mapping["industry_partnerships"],
        mapping["industry_partnerships_doc"],
        mapping["advanced_bi"],
        mapping["advanced_bi_doc"],
        mapping["development_roadmap"],
        mapping["stage64_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_franchise_chain_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    white = json.loads(WHITE.read_text(encoding="utf-8"))
    partner = json.loads(PARTNER.read_text(encoding="utf-8"))
    direct = json.loads(DIRECT.read_text(encoding="utf-8"))
    industry = json.loads(INDUSTRY.read_text(encoding="utf-8"))
    assert mapping["franchise_chain_live_claimed"] is False
    assert mapping["chain_enterprise_deals_claimed"] is False
    for key in (
        "white_label_licensing_live",
        "franchise_revenue_share_billing_claimed",
        "white_label_licensing_program_live",
    ):
        if key in white:
            assert white[key] is False
    for key in ("partner_program_live", "signed_reseller_agreement_claimed", "white_label_live_claimed"):
        if key in partner:
            assert partner[key] is False
    for key in ("inside_sales_team_live", "enterprise_pipeline_claimed", "direct_sales_program_live"):
        if key in direct:
            assert direct[key] is False
    for key in ("industry_partnership_program_live", "signed_association_deals_claimed"):
        if key in industry:
            assert industry[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "Franchise" in po or "franchise" in po.lower()
    assert "chain" in po.lower()


def test_franchise_chain_doc_and_readme():
    doc = _read("docs/FRANCHISE_CHAIN_MVP.md")
    assert "Stage 64 F1" in doc
    assert "test_franchise_chain_f1.py" in doc
    assert "franchise-chain.json" in doc
    assert "stage64_f1_franchise_chain.json" in doc
    assert "franchise_chain_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "franchise" in doc.lower() or "chain" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 64 F1" in readme
    assert "FRANCHISE_CHAIN_MVP.md" in readme
    assert "franchise-chain.json" in readme


def test_f1_plan_launch_roadmap():
    plan = _read("docs/STAGE_64_PLAN.md")
    f1_line = [ln for ln in plan.splitlines() if "| **F1** |" in ln][0]
    assert "COMPLETE" in f1_line
    assert "test_franchise_chain_f1.py" in plan
    assert (
        "F1 next" in plan
        or "F1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H64x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_franchise_chain_f1.py" in launch
    assert "Stage 64 F1" in launch
    assert "FRANCHISE_CHAIN_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 64 F1" in roadmap
    assert "test_franchise_chain_f1.py" in roadmap

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "64",
        "workstream": "F1",
        "passed": True,
        "doc": "docs/FRANCHISE_CHAIN_MVP.md",
        "register": "ops/mvp/franchise-chain.json",
        "packaging_complete": True,
        "franchise_chain_live_claimed": False,
        "chain_enterprise_deals_claimed": False,
        "franchise_deal_program_live": False,
        "franchise_network_live_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["franchise_chain_live_claimed"] is False
    assert loaded["chain_enterprise_deals_claimed"] is False
    assert loaded["step_count"] >= 10
