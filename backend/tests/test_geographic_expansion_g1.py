"""Stage 56 G1 — geographic expansion honesty (not multi-market / international localization Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "geographic-expansion.json"
RESIDENCY = ROOT / "ops" / "mvp" / "data-residency.json"
DEFERRED = ROOT / "ops" / "mvp" / "deferred-adr-register.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage56_g1_geographic_expansion.json"

REQUIRED_IDS = {
    "ge-product-overview",
    "ge-data-residency",
    "ge-deferred-adr-i18n",
    "ge-digital-marketing",
    "ge-direct-sales",
    "ge-white-label-partner",
    "ge-roadmap-backlog",
    "ge-plan-honesty",
    "ge-multi-market-remaining",
    "ge-international-remaining",
}
REQUIRED_CATEGORIES = {"expansion", "localization", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_geographic_expansion_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "56"
    assert mapping["workstream"] == "G1"
    assert mapping["packaging_complete"] is True
    assert mapping["multi_market_expansion_claimed"] is False
    assert mapping["international_localization_claimed"] is False
    assert mapping["i18n_localization_packs_live"] is False
    assert mapping["geographic_expansion_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/GEOGRAPHIC_EXPANSION_MVP.md"
    assert "stage56_g1_geographic_expansion.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ge-multi-market-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ge-international-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "market" in d.lower()
        or "international" in d.lower()
        or "localization" in d.lower()
        or "geographic" in d.lower()
        or "i18n" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["data_residency"],
        mapping["data_residency_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["digital_marketing"],
        mapping["digital_marketing_doc"],
        mapping["direct_sales"],
        mapping["direct_sales_doc"],
        mapping["white_label_licensing"],
        mapping["white_label_licensing_doc"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["development_roadmap"],
        mapping["stage56_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_geographic_expansion_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    residency = json.loads(RESIDENCY.read_text(encoding="utf-8"))
    deferred = json.loads(DEFERRED.read_text(encoding="utf-8"))
    assert mapping["multi_market_expansion_claimed"] is False
    assert mapping["international_localization_claimed"] is False
    for key in (
        "multi_region_residency_claimed",
        "schema_per_tenant_claimed",
        "gdpr_residency_cert_claimed",
        "customer_region_pinning_live",
    ):
        if key in residency:
            assert residency[key] is False
    if "i18n_packs_claimed" in deferred:
        assert deferred["i18n_packs_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "geographic" in po.lower()
        or "International" in po
        or "localization" in po.lower()
        or "markets" in po.lower()
    )


def test_geographic_expansion_doc_and_readme():
    doc = _read("docs/GEOGRAPHIC_EXPANSION_MVP.md")
    assert "Stage 56 G1" in doc
    assert "test_geographic_expansion_g1.py" in doc
    assert "geographic-expansion.json" in doc
    assert "stage56_g1_geographic_expansion.json" in doc
    assert "multi_market_expansion_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "geographic" in doc.lower() or "expansion" in doc.lower() or "localization" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 56 G1" in readme
    assert "GEOGRAPHIC_EXPANSION_MVP.md" in readme
    assert "geographic-expansion.json" in readme


def test_g1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_56_PLAN.md")
    g1_line = [ln for ln in plan.splitlines() if "| **G1** |" in ln][0]
    assert "COMPLETE" in g1_line
    assert "test_geographic_expansion_g1.py" in plan
    assert (
        "G1 next" in plan
        or "G1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H56x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_geographic_expansion_g1.py" in launch
    assert "Stage 56 G1" in launch
    assert "GEOGRAPHIC_EXPANSION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 56 G1" in roadmap
    assert "test_geographic_expansion_g1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 56 G1" in pr
    assert "test_geographic_expansion_g1.py" in pr or "GEOGRAPHIC_EXPANSION_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "56",
        "workstream": "G1",
        "passed": True,
        "doc": "docs/GEOGRAPHIC_EXPANSION_MVP.md",
        "register": "ops/mvp/geographic-expansion.json",
        "packaging_complete": True,
        "multi_market_expansion_claimed": False,
        "international_localization_claimed": False,
        "i18n_localization_packs_live": False,
        "geographic_expansion_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["multi_market_expansion_claimed"] is False
    assert loaded["international_localization_claimed"] is False
    assert loaded["step_count"] >= 10
