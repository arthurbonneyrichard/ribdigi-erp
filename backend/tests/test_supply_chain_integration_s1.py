"""Stage 61 S1 — supply chain integration honesty (not live supplier network Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "supply-chain-integration.json"
PURCHASE = ROOT / "ops" / "mvp" / "e2e-purchase-stock.json"
MANUFACTURING = ROOT / "ops" / "mvp" / "advanced-manufacturing.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage61_s1_supply_chain_integration.json"

REQUIRED_IDS = {
    "sci-product-overview",
    "sci-purchase-stock",
    "sci-manufacturing",
    "sci-fintech-adjacency",
    "sci-industry",
    "sci-partner",
    "sci-api-commercial",
    "sci-plan-honesty",
    "sci-supplier-network-remaining",
    "sci-portal-remaining",
}
REQUIRED_CATEGORIES = {"supply_chain", "ops", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_supply_chain_integration_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "61"
    assert mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    assert mapping["supplier_supply_chain_live_claimed"] is False
    assert mapping["supplier_portal_live_claimed"] is False
    assert mapping["edi_asn_program_live"] is False
    assert mapping["supply_chain_integration_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/SUPPLY_CHAIN_INTEGRATION_MVP.md"
    assert "stage61_s1_supply_chain_integration.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "sci-supplier-network-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sci-portal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "supply" in d.lower()
        or "supplier" in d.lower()
        or "edi" in d.lower()
        or "asn" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["e2e_purchase_stock"],
        mapping["e2e_purchase_stock_doc"],
        mapping["advanced_manufacturing"],
        mapping["advanced_manufacturing_doc"],
        mapping["embedded_fintech"],
        mapping["embedded_fintech_doc"],
        mapping["industry_partnerships"],
        mapping["industry_partnerships_doc"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["api_integration_commercial"],
        mapping["api_integration_commercial_doc"],
        mapping["development_roadmap"],
        mapping["stage61_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_supply_chain_integration_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    purchase = json.loads(PURCHASE.read_text(encoding="utf-8"))
    manufacturing = json.loads(MANUFACTURING.read_text(encoding="utf-8"))
    assert mapping["supplier_supply_chain_live_claimed"] is False
    assert mapping["supplier_portal_live_claimed"] is False
    for key in ("purchase_stock_e2e_program_live", "live_purchase_stock_claimed"):
        if key in purchase:
            assert purchase[key] is False
    for key in (
        "mrp_module_live_claimed",
        "production_scheduling_live_claimed",
        "advanced_manufacturing_program_live",
    ):
        if key in manufacturing:
            assert manufacturing[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "Supply chain" in po or "supply chain" in po.lower() or "suppliers" in po.lower()


def test_supply_chain_integration_doc_and_readme():
    doc = _read("docs/SUPPLY_CHAIN_INTEGRATION_MVP.md")
    assert "Stage 61 S1" in doc
    assert "test_supply_chain_integration_s1.py" in doc
    assert "supply-chain-integration.json" in doc
    assert "stage61_s1_supply_chain_integration.json" in doc
    assert "supplier_supply_chain_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "supply" in doc.lower() or "supplier" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 61 S1" in readme
    assert "SUPPLY_CHAIN_INTEGRATION_MVP.md" in readme
    assert "supply-chain-integration.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_61_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_supply_chain_integration_s1.py" in plan
    assert (
        "S1 next" in plan
        or "S1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H61x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_supply_chain_integration_s1.py" in launch
    assert "Stage 61 S1" in launch
    assert "SUPPLY_CHAIN_INTEGRATION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 61 S1" in roadmap
    assert "test_supply_chain_integration_s1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 61 S1" in pr
    assert "test_supply_chain_integration_s1.py" in pr or "SUPPLY_CHAIN_INTEGRATION_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "61",
        "workstream": "S1",
        "passed": True,
        "doc": "docs/SUPPLY_CHAIN_INTEGRATION_MVP.md",
        "register": "ops/mvp/supply-chain-integration.json",
        "packaging_complete": True,
        "supplier_supply_chain_live_claimed": False,
        "supplier_portal_live_claimed": False,
        "edi_asn_program_live": False,
        "supply_chain_integration_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["supplier_supply_chain_live_claimed"] is False
    assert loaded["supplier_portal_live_claimed"] is False
    assert loaded["step_count"] >= 10
