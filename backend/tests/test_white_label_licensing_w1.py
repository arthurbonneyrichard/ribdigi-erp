"""Stage 55 W1 — white-label licensing honesty (not live licensing / franchise billing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "white-label-licensing.json"
PARTNER = ROOT / "ops" / "mvp" / "partner-reseller.json"
SALES = ROOT / "ops" / "mvp" / "direct-sales.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage55_w1_white_label_licensing.json"

REQUIRED_IDS = {
    "wl-product-overview",
    "wl-partner-adjacency",
    "wl-sales-adjacency",
    "wl-pricing-adjacency",
    "wl-billing-deferred",
    "wl-deferred-adr",
    "wl-roadmap-backlog",
    "wl-plan-honesty",
    "wl-licensing-remaining",
    "wl-franchise-remaining",
}
REQUIRED_CATEGORIES = {"licensing", "franchise", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_white_label_licensing_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "55"
    assert mapping["workstream"] == "W1"
    assert mapping["packaging_complete"] is True
    assert mapping["white_label_licensing_live"] is False
    assert mapping["franchise_revenue_share_billing_claimed"] is False
    assert mapping["per_tenant_licensing_fee_enforced"] is False
    assert mapping["white_label_licensing_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/WHITE_LABEL_LICENSING_MVP.md"
    assert "stage55_w1_white_label_licensing.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "wl-licensing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "wl-franchise-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "white-label" in d.lower()
        or "licensing" in d.lower()
        or "franchise" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["direct_sales"],
        mapping["direct_sales_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage55_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_white_label_licensing_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    partner = json.loads(PARTNER.read_text(encoding="utf-8"))
    sales = json.loads(SALES.read_text(encoding="utf-8"))
    assert mapping["white_label_licensing_live"] is False
    assert mapping["franchise_revenue_share_billing_claimed"] is False
    assert partner.get("white_label_live_claimed") is False
    assert partner.get("partner_program_live") is False
    if "white_label_sales_pipeline_claimed" in sales:
        assert sales["white_label_sales_pipeline_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "White-Label" in po
        or "white-label" in po.lower()
        or "Licensing" in po
        or "franchise" in po.lower()
        or "reseller" in po.lower()
    )


def test_white_label_licensing_doc_and_readme():
    doc = _read("docs/WHITE_LABEL_LICENSING_MVP.md")
    assert "Stage 55 W1" in doc
    assert "test_white_label_licensing_w1.py" in doc
    assert "white-label-licensing.json" in doc
    assert "stage55_w1_white_label_licensing.json" in doc
    assert "white_label_licensing_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "licensing" in doc.lower() or "white-label" in doc.lower() or "franchise" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 55 W1" in readme
    assert "WHITE_LABEL_LICENSING_MVP.md" in readme
    assert "white-label-licensing.json" in readme


def test_w1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_55_PLAN.md")
    w1_line = [ln for ln in plan.splitlines() if "| **W1** |" in ln][0]
    assert "COMPLETE" in w1_line
    assert "test_white_label_licensing_w1.py" in plan
    assert (
        "W1 next" in plan
        or "W1 complete" in plan
        or "U1 next" in plan
        or "U1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H55x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_white_label_licensing_w1.py" in launch
    assert "Stage 55 W1" in launch
    assert "WHITE_LABEL_LICENSING_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 55 W1" in roadmap
    assert "test_white_label_licensing_w1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 55 W1" in pr
    assert "test_white_label_licensing_w1.py" in pr or "WHITE_LABEL_LICENSING_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "55",
        "workstream": "W1",
        "passed": True,
        "doc": "docs/WHITE_LABEL_LICENSING_MVP.md",
        "register": "ops/mvp/white-label-licensing.json",
        "packaging_complete": True,
        "white_label_licensing_live": False,
        "franchise_revenue_share_billing_claimed": False,
        "per_tenant_licensing_fee_enforced": False,
        "white_label_licensing_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["white_label_licensing_live"] is False
    assert loaded["franchise_revenue_share_billing_claimed"] is False
    assert loaded["step_count"] >= 10
