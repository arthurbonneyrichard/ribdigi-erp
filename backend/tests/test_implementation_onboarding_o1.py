"""Stage 56 O1 — implementation/onboarding honesty (not live migration fee / training delivery Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "implementation-onboarding.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
TRAINING = ROOT / "ops" / "mvp" / "customer-training-cert.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage56_o1_implementation_onboarding.json"

REQUIRED_IDS = {
    "io-product-overview",
    "io-billing-deferred",
    "io-sow-adjacency",
    "io-training-adjacency",
    "io-first-tenant-adjacency",
    "io-deferred-adr",
    "io-roadmap-backlog",
    "io-plan-honesty",
    "io-migration-remaining",
    "io-training-remaining",
}
REQUIRED_CATEGORIES = {"onboarding", "implementation", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_implementation_onboarding_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "56"
    assert mapping["workstream"] == "O1"
    assert mapping["packaging_complete"] is True
    assert mapping["data_migration_fee_billing_live"] is False
    assert mapping["onsite_training_delivery_claimed"] is False
    assert mapping["custom_workflow_sold_claimed"] is False
    assert mapping["implementation_onboarding_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/IMPLEMENTATION_ONBOARDING_MVP.md"
    assert "stage56_o1_implementation_onboarding.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "io-migration-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "io-training-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "migration" in d.lower()
        or "training" in d.lower()
        or "onboarding" in d.lower()
        or "workflow" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["professional_services_sow"],
        mapping["professional_services_sow_doc"],
        mapping["customer_training_cert"],
        mapping["customer_training_cert_doc"],
        mapping["first_tenant_onboarding"],
        mapping["first_tenant_onboarding_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage56_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_implementation_onboarding_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    training = json.loads(TRAINING.read_text(encoding="utf-8"))
    assert mapping["data_migration_fee_billing_live"] is False
    assert mapping["onsite_training_delivery_claimed"] is False
    for key in ("billing_complete_claimed", "payment_provider_claimed", "checkout_success_claimed"):
        if key in billing:
            assert billing[key] is False
    for key in ("live_training_claimed", "customer_training_delivered_claimed", "training_complete_claimed"):
        if key in training:
            assert training[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Implementation" in po
        or "Onboarding" in po
        or "migration" in po.lower()
        or "training" in po.lower()
    )


def test_implementation_onboarding_doc_and_readme():
    doc = _read("docs/IMPLEMENTATION_ONBOARDING_MVP.md")
    assert "Stage 56 O1" in doc
    assert "test_implementation_onboarding_o1.py" in doc
    assert "implementation-onboarding.json" in doc
    assert "stage56_o1_implementation_onboarding.json" in doc
    assert "data_migration_fee_billing_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "onboarding" in doc.lower() or "implementation" in doc.lower() or "migration" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 56 O1" in readme
    assert "IMPLEMENTATION_ONBOARDING_MVP.md" in readme
    assert "implementation-onboarding.json" in readme


def test_o1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_56_PLAN.md")
    o1_line = [ln for ln in plan.splitlines() if "| **O1** |" in ln][0]
    assert "COMPLETE" in o1_line
    assert "test_implementation_onboarding_o1.py" in plan
    assert (
        "O1 next" in plan
        or "O1 complete" in plan
        or "G1 next" in plan
        or "G1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H56x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_implementation_onboarding_o1.py" in launch
    assert "Stage 56 O1" in launch
    assert "IMPLEMENTATION_ONBOARDING_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 56 O1" in roadmap
    assert "test_implementation_onboarding_o1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 56 O1" in pr
    assert "test_implementation_onboarding_o1.py" in pr or "IMPLEMENTATION_ONBOARDING_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "56",
        "workstream": "O1",
        "passed": True,
        "doc": "docs/IMPLEMENTATION_ONBOARDING_MVP.md",
        "register": "ops/mvp/implementation-onboarding.json",
        "packaging_complete": True,
        "data_migration_fee_billing_live": False,
        "onsite_training_delivery_claimed": False,
        "custom_workflow_sold_claimed": False,
        "implementation_onboarding_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["data_migration_fee_billing_live"] is False
    assert loaded["onsite_training_delivery_claimed"] is False
    assert loaded["step_count"] >= 10
