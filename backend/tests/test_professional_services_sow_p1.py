"""Stage 48 P1 — professional services / SOW honesty (not signed SOW Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "professional-services-sow.json"
FIRST = ROOT / "ops" / "mvp" / "first-tenant-onboarding.json"
KT = ROOT / "ops" / "mvp" / "knowledge-transfer.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage48_p1_professional_services_sow.json"

REQUIRED_IDS = {
    "ps-product-overview",
    "ps-first-tenant",
    "ps-knowledge-transfer",
    "ps-msa-adjacency",
    "ps-support-sla",
    "ps-liability-adjacency",
    "ps-br-onboarding",
    "ps-plan-honesty",
    "ps-sow-remaining",
    "ps-delivery-remaining",
}
REQUIRED_CATEGORIES = {"sow", "services", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_professional_services_sow_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "48"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    assert mapping["signed_sow_claimed"] is False
    assert mapping["professional_services_live"] is False
    assert mapping["implementation_delivery_claimed"] is False
    assert mapping["data_migration_complete_claimed"] is False
    assert mapping["custom_workflow_delivery_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/PROFESSIONAL_SERVICES_SOW_MVP.md"
    assert "stage48_p1_professional_services_sow.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ps-sow-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ps-delivery-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "sow" in d.lower() or "implementation" in d.lower() or "migration" in d.lower() or "services" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["first_tenant_onboarding"],
        mapping["first_tenant_onboarding_doc"],
        mapping["knowledge_transfer"],
        mapping["knowledge_transfer_doc"],
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["support_sla"],
        mapping["support_sla_doc"],
        mapping["liability_indemnity"],
        mapping["liability_indemnity_doc"],
        mapping["business_requirements"],
        mapping["stage48_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_professional_services_sow_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    kt = json.loads(KT.read_text(encoding="utf-8"))
    assert mapping["signed_sow_claimed"] is False
    assert mapping["professional_services_live"] is False
    assert first.get("packaging_complete") is True or "steps" in first
    assert kt.get("live_training_claimed") is False or kt.get("packaging_complete") is True
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "Implementation" in po or "Onboarding" in po or "training" in po.lower()
    ft = _read("docs/FIRST_TENANT_ONBOARDING_MVP.md")
    assert "tenant" in ft.lower() or "onboarding" in ft.lower()


def test_professional_services_sow_doc_and_readme():
    doc = _read("docs/PROFESSIONAL_SERVICES_SOW_MVP.md")
    assert "Stage 48 P1" in doc
    assert "test_professional_services_sow_p1.py" in doc
    assert "professional-services-sow.json" in doc
    assert "stage48_p1_professional_services_sow.json" in doc
    assert "signed_sow_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "SOW" in doc or "services" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 48 P1" in readme
    assert "PROFESSIONAL_SERVICES_SOW_MVP.md" in readme
    assert "professional-services-sow.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_48_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_professional_services_sow_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H48x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_professional_services_sow_p1.py" in launch
    assert "Stage 48 P1" in launch
    assert "PROFESSIONAL_SERVICES_SOW_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 48 P1" in roadmap
    assert "test_professional_services_sow_p1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 48 P1" in pr
    assert "test_professional_services_sow_p1.py" in pr or "PROFESSIONAL_SERVICES_SOW_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "48",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/PROFESSIONAL_SERVICES_SOW_MVP.md",
        "register": "ops/mvp/professional-services-sow.json",
        "packaging_complete": True,
        "signed_sow_claimed": False,
        "professional_services_live": False,
        "implementation_delivery_claimed": False,
        "data_migration_complete_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["signed_sow_claimed"] is False
    assert loaded["professional_services_live"] is False
    assert loaded["step_count"] >= 10
