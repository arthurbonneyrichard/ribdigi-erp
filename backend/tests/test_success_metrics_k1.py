"""Stage 57 K1 — success metrics honesty (not measured MAU / NPS / uptime Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "success-metrics.json"
STATUS = ROOT / "ops" / "mvp" / "status-uptime.json"
ECONOMICS = ROOT / "ops" / "mvp" / "unit-economics-positioning.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage57_k1_success_metrics.json"

REQUIRED_IDS = {
    "sm-product-overview",
    "sm-status-uptime",
    "sm-support-sla",
    "sm-unit-economics",
    "sm-mobile-adjacency",
    "sm-churn-adjacency",
    "sm-roadmap-backlog",
    "sm-plan-honesty",
    "sm-mau-remaining",
    "sm-nps-uptime-remaining",
}
REQUIRED_CATEGORIES = {"metrics", "uptime", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_success_metrics_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "57"
    assert mapping["workstream"] == "K1"
    assert mapping["packaging_complete"] is True
    assert mapping["mau_measured_claimed"] is False
    assert mapping["nps_measured_claimed"] is False
    assert mapping["uptime_sla_measured_claimed"] is False
    assert mapping["success_metrics_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/SUCCESS_METRICS_MVP.md"
    assert "stage57_k1_success_metrics.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "sm-mau-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sm-nps-uptime-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "mau" in d.lower()
        or "nps" in d.lower()
        or "uptime" in d.lower()
        or "metrics" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["status_uptime"],
        mapping["status_uptime_doc"],
        mapping["support_sla_boundary"],
        mapping["support_sla_boundary_doc"],
        mapping["unit_economics_positioning"],
        mapping["unit_economics_positioning_doc"],
        mapping["mobile_app_gtm"],
        mapping["mobile_app_gtm_doc"],
        mapping["cancellation_churn"],
        mapping["cancellation_churn_doc"],
        mapping["development_roadmap"],
        mapping["stage57_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_success_metrics_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    economics = json.loads(ECONOMICS.read_text(encoding="utf-8"))
    assert mapping["mau_measured_claimed"] is False
    assert mapping["nps_measured_claimed"] is False
    for key in ("status_page_live", "uptime_sla_claimed", "measured_uptime_claimed"):
        if key in status:
            assert status[key] is False
    for key in ("cac_ltv_measured_claimed", "arpu_payback_measured_claimed", "win_loss_analysis_live"):
        if key in economics:
            assert economics[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "MAU" in po
        or "NPS" in po
        or "uptime" in po.lower()
        or "Success Metrics" in po
    )


def test_success_metrics_doc_and_readme():
    doc = _read("docs/SUCCESS_METRICS_MVP.md")
    assert "Stage 57 K1" in doc
    assert "test_success_metrics_k1.py" in doc
    assert "success-metrics.json" in doc
    assert "stage57_k1_success_metrics.json" in doc
    assert "mau_measured_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "metrics" in doc.lower() or "mau" in doc.lower() or "nps" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 57 K1" in readme
    assert "SUCCESS_METRICS_MVP.md" in readme
    assert "success-metrics.json" in readme


def test_k1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_57_PLAN.md")
    k1_line = [ln for ln in plan.splitlines() if "| **K1** |" in ln][0]
    assert "COMPLETE" in k1_line
    assert "test_success_metrics_k1.py" in plan
    assert (
        "K1 next" in plan
        or "K1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H57x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_success_metrics_k1.py" in launch
    assert "Stage 57 K1" in launch
    assert "SUCCESS_METRICS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 57 K1" in roadmap
    assert "test_success_metrics_k1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 57 K1" in pr
    assert "test_success_metrics_k1.py" in pr or "SUCCESS_METRICS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "57",
        "workstream": "K1",
        "passed": True,
        "doc": "docs/SUCCESS_METRICS_MVP.md",
        "register": "ops/mvp/success-metrics.json",
        "packaging_complete": True,
        "mau_measured_claimed": False,
        "nps_measured_claimed": False,
        "uptime_sla_measured_claimed": False,
        "success_metrics_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["mau_measured_claimed"] is False
    assert loaded["nps_measured_claimed"] is False
    assert loaded["step_count"] >= 10
