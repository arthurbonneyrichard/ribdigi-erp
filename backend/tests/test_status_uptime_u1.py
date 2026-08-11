"""Stage 40 U1 — Status page / uptime honesty (not live status page / 99.9% SLA Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "status-uptime.json"
SUPPORT_SLA = ROOT / "ops" / "mvp" / "support-sla-boundary.json"
ADMIN_OPS = ROOT / "ops" / "support" / "admin-ops-map.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage40_u1_status_uptime.json"

REQUIRED_IDS = {
    "su-product-overview-uptime",
    "su-support-sla-status-page",
    "su-health-probes",
    "su-prometheus-grafana",
    "su-incident-alertmanager",
    "su-support-runbook",
    "su-admin-ops-map",
    "su-maintenance-window",
    "su-status-page-remaining",
    "su-uptime-sla-remaining",
}
REQUIRED_CATEGORIES = {"uptime", "status", "monitoring", "incident", "support", "change", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_status_uptime_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "40"
    assert mapping["workstream"] == "U1"
    assert mapping["packaging_complete"] is True
    assert mapping["status_page_live"] is False
    assert mapping["uptime_sla_claimed"] is False
    assert mapping["measured_uptime_claimed"] is False
    assert mapping["public_dashboard_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/STATUS_UPTIME_MVP.md"
    assert "stage40_u1_status_uptime.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "su-status-page-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "su-uptime-sla-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "su-product-overview-uptime" for s in steps)
    assert any(
        "status" in d.lower() or "uptime" in d.lower() or "99.9" in d or "grafana" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["support_sla_boundary"],
        mapping["support_sla_boundary_doc"],
        mapping["support_runbook"],
        mapping["ops_monitoring"],
        mapping["grafana_pack"],
        mapping["incident_pack"],
        mapping["incident_checklist"],
        mapping["admin_ops_map"],
        mapping["stage40_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_status_uptime_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    support = json.loads(SUPPORT_SLA.read_text(encoding="utf-8"))
    assert mapping["status_page_live"] is False
    assert mapping["uptime_sla_claimed"] is False
    assert support.get("support_sla_claimed") is False
    overview = _read("docs/PRODUCT_OVERVIEW.md")
    assert "99.9" in overview or "uptime" in overview.lower()
    for step in mapping["steps"]:
        assert step["done"] is False
    sla_doc = _read("docs/SUPPORT_SLA_BOUNDARY_MVP.md")
    assert "status-page" in sla_doc.lower() or "status page" in sla_doc.lower() or "SLA" in sla_doc
    admin = json.loads(ADMIN_OPS.read_text(encoding="utf-8"))
    admin_blob = json.dumps(admin).lower()
    assert "status-page" in admin_blob or "status page" in admin_blob or "sla" in admin_blob
    mon = _read("docs/OPS_MONITORING_MVP.md")
    assert "health" in mon.lower() or "prometheus" in mon.lower() or "monitor" in mon.lower()


def test_status_uptime_doc_and_readme():
    doc = _read("docs/STATUS_UPTIME_MVP.md")
    assert "Stage 40 U1" in doc
    assert "test_status_uptime_u1.py" in doc
    assert "status-uptime.json" in doc
    assert "stage40_u1_status_uptime.json" in doc
    assert "status_page_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "uptime" in doc.lower() or "status" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 40 U1" in readme
    assert "STATUS_UPTIME_MVP.md" in readme
    assert "status-uptime.json" in readme


def test_u1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_40_PLAN.md")
    u1_line = [ln for ln in plan.splitlines() if "| **U1** |" in ln][0]
    assert "COMPLETE" in u1_line
    assert "test_status_uptime_u1.py" in plan
    assert (
        "U1 next" in plan
        or "U1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H40x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_status_uptime_u1.py" in launch
    assert "Stage 40 U1" in launch
    assert "STATUS_UPTIME_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 40 U1" in roadmap
    assert "test_status_uptime_u1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 40 U1" in pr
    assert "test_status_uptime_u1.py" in pr or "STATUS_UPTIME_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "40",
        "workstream": "U1",
        "passed": True,
        "doc": "docs/STATUS_UPTIME_MVP.md",
        "register": "ops/mvp/status-uptime.json",
        "packaging_complete": True,
        "status_page_live": False,
        "uptime_sla_claimed": False,
        "measured_uptime_claimed": False,
        "public_dashboard_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["status_page_live"] is False
    assert loaded["uptime_sla_claimed"] is False
    assert loaded["measured_uptime_claimed"] is False
    assert loaded["step_count"] >= 10
