"""Stage 54 S1 — direct sales honesty (not live inside-sales / Enterprise pipeline Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "direct-sales.json"
PARTNER = ROOT / "ops" / "mvp" / "partner-reseller.json"
MARKETING = ROOT / "ops" / "mvp" / "digital-marketing.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage54_s1_direct_sales.json"

REQUIRED_IDS = {
    "ds-product-overview",
    "ds-partner-adjacency",
    "ds-marketing-adjacency",
    "ds-pricing-adjacency",
    "ds-marketplace-adjacency",
    "ds-billing-deferred",
    "ds-roadmap-backlog",
    "ds-plan-honesty",
    "ds-team-remaining",
    "ds-pipeline-remaining",
}
REQUIRED_CATEGORIES = {"sales", "pipeline", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_direct_sales_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "54"
    assert mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    assert mapping["inside_sales_team_live"] is False
    assert mapping["enterprise_pipeline_claimed"] is False
    assert mapping["white_label_sales_pipeline_claimed"] is False
    assert mapping["direct_sales_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/DIRECT_SALES_MVP.md"
    assert "stage54_s1_direct_sales.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ds-team-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ds-pipeline-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "sales" in d.lower()
        or "enterprise" in d.lower()
        or "white-label" in d.lower()
        or "pipeline" in d.lower()
        or "inside" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["digital_marketing"],
        mapping["digital_marketing_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["marketplace_presence"],
        mapping["marketplace_presence_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["development_roadmap"],
        mapping["stage54_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_direct_sales_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    partner = json.loads(PARTNER.read_text(encoding="utf-8"))
    marketing = json.loads(MARKETING.read_text(encoding="utf-8"))
    assert mapping["inside_sales_team_live"] is False
    assert mapping["enterprise_pipeline_claimed"] is False
    assert partner.get("partner_program_live") is False
    assert partner.get("white_label_live_claimed") is False
    assert marketing.get("digital_marketing_campaigns_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Direct Sales" in po
        or "inside sales" in po.lower()
        or "Enterprise" in po
        or "White-Label" in po
        or "White-label" in po
    )


def test_direct_sales_doc_and_readme():
    doc = _read("docs/DIRECT_SALES_MVP.md")
    assert "Stage 54 S1" in doc
    assert "test_direct_sales_s1.py" in doc
    assert "direct-sales.json" in doc
    assert "stage54_s1_direct_sales.json" in doc
    assert "inside_sales_team_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "sales" in doc.lower() or "enterprise" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 54 S1" in readme
    assert "DIRECT_SALES_MVP.md" in readme
    assert "direct-sales.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_54_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_direct_sales_s1.py" in plan
    assert (
        "S1 next" in plan
        or "S1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H54x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_direct_sales_s1.py" in launch
    assert "Stage 54 S1" in launch
    assert "DIRECT_SALES_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 54 S1" in roadmap
    assert "test_direct_sales_s1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 54 S1" in pr
    assert "test_direct_sales_s1.py" in pr or "DIRECT_SALES_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "54",
        "workstream": "S1",
        "passed": True,
        "doc": "docs/DIRECT_SALES_MVP.md",
        "register": "ops/mvp/direct-sales.json",
        "packaging_complete": True,
        "inside_sales_team_live": False,
        "enterprise_pipeline_claimed": False,
        "white_label_sales_pipeline_claimed": False,
        "direct_sales_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["inside_sales_team_live"] is False
    assert loaded["enterprise_pipeline_claimed"] is False
    assert loaded["step_count"] >= 10
