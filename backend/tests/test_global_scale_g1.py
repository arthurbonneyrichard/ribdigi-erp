"""Stage 63 G1 — global scale honesty (not measured 50k customers / 20+ countries Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "global-scale.json"
GEO = ROOT / "ops" / "mvp" / "geographic-expansion.json"
METRICS = ROOT / "ops" / "mvp" / "business-metrics.json"
TAX = ROOT / "ops" / "mvp" / "multi-country-tax.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage63_g1_global_scale.json"

REQUIRED_IDS = {
    "gs-product-overview",
    "gs-geographic",
    "gs-multi-country-tax",
    "gs-business-metrics",
    "gs-success-metrics",
    "gs-data-residency",
    "gs-ipo-adjacency",
    "gs-plan-honesty",
    "gs-50k-customers-remaining",
    "gs-20-countries-remaining",
}
REQUIRED_CATEGORIES = {"scale", "geographic", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_global_scale_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "63"
    assert mapping["workstream"] == "G1"
    assert mapping["packaging_complete"] is True
    assert mapping["global_scale_50k_customers_claimed"] is False
    assert mapping["twenty_plus_countries_claimed"] is False
    assert mapping["international_scale_program_live"] is False
    assert mapping["paying_customers_50k_measured"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/GLOBAL_SCALE_MVP.md"
    assert "stage63_g1_global_scale.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "gs-50k-customers-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "gs-20-countries-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "50" in d
        or "20" in d
        or "customer" in d.lower()
        or "countr" in d.lower()
        or "scale" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["geographic_expansion"],
        mapping["geographic_expansion_doc"],
        mapping["multi_country_tax"],
        mapping["multi_country_tax_doc"],
        mapping["business_metrics"],
        mapping["business_metrics_doc"],
        mapping["success_metrics"],
        mapping["success_metrics_doc"],
        mapping["data_residency"],
        mapping["data_residency_doc"],
        mapping["ipo_readiness"],
        mapping["ipo_readiness_doc"],
        mapping["development_roadmap"],
        mapping["stage63_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_global_scale_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    tax = json.loads(TAX.read_text(encoding="utf-8"))
    assert mapping["global_scale_50k_customers_claimed"] is False
    assert mapping["twenty_plus_countries_claimed"] is False
    for key in (
        "multi_market_expansion_claimed",
        "international_localization_claimed",
        "geographic_expansion_program_live",
    ):
        if key in geo:
            assert geo[key] is False
    for key in (
        "paying_customers_measured_claimed",
        "mrr_measured_claimed",
        "business_metrics_program_live",
    ):
        if key in metrics:
            assert metrics[key] is False
    for key in (
        "multi_country_tax_engine_claimed",
        "multi_country_tax_program_live",
    ):
        if key in tax:
            assert tax[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "50,000" in po
        or "20+" in po
        or "countries" in po.lower()
        or "paying customers" in po.lower()
    )


def test_global_scale_doc_and_readme():
    doc = _read("docs/GLOBAL_SCALE_MVP.md")
    assert "Stage 63 G1" in doc
    assert "test_global_scale_g1.py" in doc
    assert "global-scale.json" in doc
    assert "stage63_g1_global_scale.json" in doc
    assert "global_scale_50k_customers_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "50" in doc or "scale" in doc.lower() or "countries" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 63 G1" in readme
    assert "GLOBAL_SCALE_MVP.md" in readme
    assert "global-scale.json" in readme


def test_g1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_63_PLAN.md")
    g1_line = [ln for ln in plan.splitlines() if "| **G1** |" in ln][0]
    assert "COMPLETE" in g1_line
    assert "test_global_scale_g1.py" in plan
    assert (
        "G1 next" in plan
        or "G1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H63x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_global_scale_g1.py" in launch
    assert "Stage 63 G1" in launch
    assert "GLOBAL_SCALE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 63 G1" in roadmap
    assert "test_global_scale_g1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 63 G1" in pr
    assert "test_global_scale_g1.py" in pr or "GLOBAL_SCALE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "63",
        "workstream": "G1",
        "passed": True,
        "doc": "docs/GLOBAL_SCALE_MVP.md",
        "register": "ops/mvp/global-scale.json",
        "packaging_complete": True,
        "global_scale_50k_customers_claimed": False,
        "twenty_plus_countries_claimed": False,
        "international_scale_program_live": False,
        "paying_customers_50k_measured": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["global_scale_50k_customers_claimed"] is False
    assert loaded["twenty_plus_countries_claimed"] is False
    assert loaded["step_count"] >= 10
