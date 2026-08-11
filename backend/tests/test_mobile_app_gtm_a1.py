"""Stage 57 A1 — mobile app GTM honesty (not live Flutter / store publish Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "mobile-app-gtm.json"
MARKETING = ROOT / "ops" / "mvp" / "digital-marketing.json"
STATUS = ROOT / "ops" / "mvp" / "status-uptime.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage57_a1_mobile_app_gtm.json"

REQUIRED_IDS = {
    "ma-product-overview",
    "ma-digital-marketing",
    "ma-direct-sales",
    "ma-partner-white-label",
    "ma-status-uptime",
    "ma-deferred-adr",
    "ma-roadmap-backlog",
    "ma-plan-honesty",
    "ma-flutter-remaining",
    "ma-store-remaining",
}
REQUIRED_CATEGORIES = {"mobile", "gtm", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_mobile_app_gtm_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "57"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["flutter_app_live_claimed"] is False
    assert mapping["app_store_play_publish_claimed"] is False
    assert mapping["native_mobile_app_program_live"] is False
    assert mapping["mobile_app_gtm_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/MOBILE_APP_GTM_MVP.md"
    assert "stage57_a1_mobile_app_gtm.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ma-flutter-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ma-store-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "flutter" in d.lower()
        or "mobile" in d.lower()
        or "store" in d.lower()
        or "play" in d.lower()
        or "app" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["digital_marketing"],
        mapping["digital_marketing_doc"],
        mapping["direct_sales"],
        mapping["direct_sales_doc"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["white_label_licensing"],
        mapping["white_label_licensing_doc"],
        mapping["status_uptime"],
        mapping["status_uptime_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage57_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_mobile_app_gtm_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    marketing = json.loads(MARKETING.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    assert mapping["flutter_app_live_claimed"] is False
    assert mapping["app_store_play_publish_claimed"] is False
    for key in (
        "digital_marketing_campaigns_live",
        "case_studies_published_claimed",
        "paid_ads_live",
    ):
        if key in marketing:
            assert marketing[key] is False
    for key in ("status_page_live", "uptime_sla_claimed", "measured_uptime_claimed"):
        if key in status:
            assert status[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "mobile" in po.lower()
        or "Flutter" in po
        or "Launch mobile" in po
    )


def test_mobile_app_gtm_doc_and_readme():
    doc = _read("docs/MOBILE_APP_GTM_MVP.md")
    assert "Stage 57 A1" in doc
    assert "test_mobile_app_gtm_a1.py" in doc
    assert "mobile-app-gtm.json" in doc
    assert "stage57_a1_mobile_app_gtm.json" in doc
    assert "flutter_app_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "mobile" in doc.lower() or "flutter" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 57 A1" in readme
    assert "MOBILE_APP_GTM_MVP.md" in readme
    assert "mobile-app-gtm.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_57_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_mobile_app_gtm_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "K1 next" in plan
        or "K1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H57x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_mobile_app_gtm_a1.py" in launch
    assert "Stage 57 A1" in launch
    assert "MOBILE_APP_GTM_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 57 A1" in roadmap
    assert "test_mobile_app_gtm_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 57 A1" in pr
    assert "test_mobile_app_gtm_a1.py" in pr or "MOBILE_APP_GTM_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "57",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/MOBILE_APP_GTM_MVP.md",
        "register": "ops/mvp/mobile-app-gtm.json",
        "packaging_complete": True,
        "flutter_app_live_claimed": False,
        "app_store_play_publish_claimed": False,
        "native_mobile_app_program_live": False,
        "mobile_app_gtm_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["flutter_app_live_claimed"] is False
    assert loaded["app_store_play_publish_claimed"] is False
    assert loaded["step_count"] >= 10
