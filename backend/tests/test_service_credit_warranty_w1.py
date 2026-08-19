"""Stage 46 W1 — service credit / warranty honesty (not live credits Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "service-credit-warranty.json"
STATUS = ROOT / "ops" / "mvp" / "status-uptime.json"
SLA = ROOT / "ops" / "mvp" / "support-sla-boundary.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage46_w1_service_credit_warranty.json"

REQUIRED_IDS = {
    "sc-support-sla",
    "sc-status-uptime",
    "sc-rto-rpo",
    "sc-incident",
    "sc-liability-adjacency",
    "sc-msa-adjacency",
    "sc-change-governance",
    "sc-product-overview",
    "sc-credits-remaining",
    "sc-warranty-remaining",
}
REQUIRED_CATEGORIES = {"credit", "warranty", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_service_credit_warranty_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "46"
    assert mapping["workstream"] == "W1"
    assert mapping["packaging_complete"] is True
    assert mapping["service_credits_live"] is False
    assert mapping["warranty_live_claimed"] is False
    assert mapping["uptime_credit_claimed"] is False
    assert mapping["remedy_schedule_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/SERVICE_CREDIT_WARRANTY_MVP.md"
    assert "stage46_w1_service_credit_warranty.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "sc-credits-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sc-warranty-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "credit" in d.lower() or "warranty" in d.lower() or "uptime" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["support_sla"],
        mapping["support_sla_doc"],
        mapping["status_uptime"],
        mapping["status_uptime_doc"],
        mapping["rto_rpo"],
        mapping["rto_rpo_doc"],
        mapping["incident_pack_doc"],
        mapping["incident_checklist"],
        mapping["liability_indemnity"],
        mapping["liability_indemnity_doc"],
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["change_governance"],
        mapping["change_governance_doc"],
        mapping["product_overview"],
        mapping["stage46_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_service_credit_warranty_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    sla = json.loads(SLA.read_text(encoding="utf-8"))
    assert mapping["service_credits_live"] is False
    assert mapping["warranty_live_claimed"] is False
    assert status.get("uptime_sla_claimed") is False
    assert status.get("measured_uptime_claimed") is False
    assert sla.get("support_sla_claimed") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    sla_doc = _read("docs/SUPPORT_SLA_BOUNDARY_MVP.md")
    assert "SLA" in sla_doc or "severity" in sla_doc.lower()
    up_doc = _read("docs/STATUS_UPTIME_MVP.md")
    assert "uptime" in up_doc.lower() or "99.9" in up_doc


def test_service_credit_warranty_doc_and_readme():
    doc = _read("docs/SERVICE_CREDIT_WARRANTY_MVP.md")
    assert "Stage 46 W1" in doc
    assert "test_service_credit_warranty_w1.py" in doc
    assert "service-credit-warranty.json" in doc
    assert "stage46_w1_service_credit_warranty.json" in doc
    assert "service_credits_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "credit" in doc.lower() or "warranty" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 46 W1" in readme
    assert "SERVICE_CREDIT_WARRANTY_MVP.md" in readme
    assert "service-credit-warranty.json" in readme


def test_w1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_46_PLAN.md")
    w1_line = [ln for ln in plan.splitlines() if "| **W1** |" in ln][0]
    assert "COMPLETE" in w1_line
    assert "test_service_credit_warranty_w1.py" in plan
    assert (
        "W1 next" in plan
        or "W1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H46x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_service_credit_warranty_w1.py" in launch
    assert "Stage 46 W1" in launch
    assert "SERVICE_CREDIT_WARRANTY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 46 W1" in roadmap
    assert "test_service_credit_warranty_w1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 46 W1" in pr
    assert "test_service_credit_warranty_w1.py" in pr or "SERVICE_CREDIT_WARRANTY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "46",
        "workstream": "W1",
        "passed": True,
        "doc": "docs/SERVICE_CREDIT_WARRANTY_MVP.md",
        "register": "ops/mvp/service-credit-warranty.json",
        "packaging_complete": True,
        "service_credits_live": False,
        "warranty_live_claimed": False,
        "uptime_credit_claimed": False,
        "remedy_schedule_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["service_credits_live"] is False
    assert loaded["warranty_live_claimed"] is False
    assert loaded["step_count"] >= 10
