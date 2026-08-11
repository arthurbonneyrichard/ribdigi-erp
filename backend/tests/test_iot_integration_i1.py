"""Stage 62 I1 — IoT integration honesty (not live smart shelves / sensors Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "iot-integration.json"
PURCHASE = ROOT / "ops" / "mvp" / "e2e-purchase-stock.json"
MANUFACTURING = ROOT / "ops" / "mvp" / "advanced-manufacturing.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage62_i1_iot_integration.json"

REQUIRED_IDS = {
    "iot-product-overview",
    "iot-purchase-stock",
    "iot-manufacturing",
    "iot-supply-chain",
    "iot-ops-monitoring",
    "iot-api-commercial",
    "iot-roadmap",
    "iot-plan-honesty",
    "iot-smart-shelves-remaining",
    "iot-temperature-remaining",
}
REQUIRED_CATEGORIES = {"iot", "ops", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_iot_integration_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "62"
    assert mapping["workstream"] == "I1"
    assert mapping["packaging_complete"] is True
    assert mapping["iot_integration_live_claimed"] is False
    assert mapping["smart_shelves_live_claimed"] is False
    assert mapping["temperature_sensors_live_claimed"] is False
    assert mapping["iot_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/IOT_INTEGRATION_MVP.md"
    assert "stage62_i1_iot_integration.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "iot-smart-shelves-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "iot-temperature-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "iot" in d.lower()
        or "shelf" in d.lower()
        or "sensor" in d.lower()
        or "temperature" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["e2e_purchase_stock"],
        mapping["e2e_purchase_stock_doc"],
        mapping["advanced_manufacturing"],
        mapping["advanced_manufacturing_doc"],
        mapping["supply_chain_integration"],
        mapping["supply_chain_integration_doc"],
        mapping["ops_monitoring_doc"],
        mapping["api_integration_commercial"],
        mapping["api_integration_commercial_doc"],
        mapping["development_roadmap"],
        mapping["stage62_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_iot_integration_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    purchase = json.loads(PURCHASE.read_text(encoding="utf-8"))
    manufacturing = json.loads(MANUFACTURING.read_text(encoding="utf-8"))
    assert mapping["iot_integration_live_claimed"] is False
    assert mapping["smart_shelves_live_claimed"] is False
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
    assert (
        "IoT" in po
        or "iot" in po.lower()
        or "smart shelf" in po.lower()
        or "temperature" in po.lower()
    )


def test_iot_integration_doc_and_readme():
    doc = _read("docs/IOT_INTEGRATION_MVP.md")
    assert "Stage 62 I1" in doc
    assert "test_iot_integration_i1.py" in doc
    assert "iot-integration.json" in doc
    assert "stage62_i1_iot_integration.json" in doc
    assert "iot_integration_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "iot" in doc.lower() or "shelf" in doc.lower() or "sensor" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 62 I1" in readme
    assert "IOT_INTEGRATION_MVP.md" in readme
    assert "iot-integration.json" in readme


def test_i1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_62_PLAN.md")
    i1_line = [ln for ln in plan.splitlines() if "| **I1** |" in ln][0]
    assert "COMPLETE" in i1_line
    assert "test_iot_integration_i1.py" in plan
    assert (
        "I1 next" in plan
        or "I1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H62x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_iot_integration_i1.py" in launch
    assert "Stage 62 I1" in launch
    assert "IOT_INTEGRATION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 62 I1" in roadmap
    assert "test_iot_integration_i1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 62 I1" in pr
    assert "test_iot_integration_i1.py" in pr or "IOT_INTEGRATION_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "62",
        "workstream": "I1",
        "passed": True,
        "doc": "docs/IOT_INTEGRATION_MVP.md",
        "register": "ops/mvp/iot-integration.json",
        "packaging_complete": True,
        "iot_integration_live_claimed": False,
        "smart_shelves_live_claimed": False,
        "temperature_sensors_live_claimed": False,
        "iot_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["iot_integration_live_claimed"] is False
    assert loaded["smart_shelves_live_claimed"] is False
    assert loaded["step_count"] >= 10
