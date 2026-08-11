"""Stage 68 H1 — Ribdigi House console honesty (not paid billing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ribdigi-house-console.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
SUB = ROOT / "ops" / "mvp" / "subscription-renewal.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage68_h1_ribdigi_house_console.json"

REQUIRED_IDS = {
    "rh-owner-outline",
    "rh-adr137",
    "rh-tenants-users",
    "rh-plans-metadata",
    "rh-billing-deferred",
    "rh-subscription-renewal",
    "rh-security-audit-health-settings",
    "rh-plan-honesty",
    "rh-billing-remaining",
    "rh-subscriptions-remaining",
}
REQUIRED_CATEGORIES = {"house", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ribdigi_house_console_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "68"
    assert mapping["workstream"] == "H1"
    assert mapping["packaging_complete"] is True
    assert mapping["billing_complete_claimed"] is False
    assert mapping["payment_provider_claimed"] is False
    assert mapping["checkout_success_claimed"] is False
    assert mapping["subscriptions_live_claimed"] is False
    assert mapping["mrr_fabricated_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/RIBDIGI_HOUSE_CONSOLE_MVP.md"
    assert "stage68_h1_ribdigi_house_console.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "rh-billing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "rh-subscriptions-remaining" and s["status"] == "remaining" for s in steps)
    assert any("billing" in d.lower() or "subscription" in d.lower() or "mrr" in d.lower() for d in mapping["deferred"])
    for rel in (
        mapping["stage68_plan"],
        mapping["adr137"],
        mapping["adr002"],
        mapping["billing_deferred_doc"],
        mapping["billing_deferred"],
        mapping["subscription_renewal_doc"],
        mapping["subscription_renewal"],
        mapping["platform_shell"],
        mapping["platform_api"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_ribdigi_house_console_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    sub = json.loads(SUB.read_text(encoding="utf-8"))
    assert mapping["billing_complete_claimed"] is False
    for key in ("billing_complete_claimed", "payment_provider_claimed", "checkout_success_claimed"):
        if key in billing:
            assert billing[key] is False
    for key in ("auto_renewal_billing_live", "upgrade_downgrade_live", "renewal_program_live"):
        if key in sub:
            assert sub[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_68_PLAN.md")
    assert "RIBDIGI HOUSE" in plan or "Ribdigi House" in plan
    assert "TENANT COMPANY" in plan or "Tenant Company" in plan
    shell = _read("frontend/components/PlatformShell.tsx")
    assert "Tenants" in shell or "tenants" in shell
    assert "Billing" in shell or "billing" in shell


def test_ribdigi_house_console_doc_and_readme():
    doc = _read("docs/RIBDIGI_HOUSE_CONSOLE_MVP.md")
    assert "Stage 68 H1" in doc
    assert "test_ribdigi_house_console_h1.py" in doc
    assert "ribdigi-house-console.json" in doc
    assert "billing_complete_claimed" in doc or "done: false" in doc
    assert "ADR-002" in doc or "billing" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 68 H1" in readme
    assert "RIBDIGI_HOUSE_CONSOLE_MVP.md" in readme
    assert "ribdigi-house-console.json" in readme


def test_h1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_68_PLAN.md")
    h1_line = [ln for ln in plan.splitlines() if "| **H1** |" in ln][0]
    assert "COMPLETE" in h1_line
    assert "test_ribdigi_house_console_h1.py" in plan
    assert (
        "H1 next" in plan
        or "H1 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ribdigi_house_console_h1.py" in launch
    assert "Stage 68 H1" in launch
    assert "RIBDIGI_HOUSE_CONSOLE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 68 H1" in roadmap
    assert "test_ribdigi_house_console_h1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 68 H1" in pr
    assert "test_ribdigi_house_console_h1.py" in pr or "RIBDIGI_HOUSE_CONSOLE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "68",
        "workstream": "H1",
        "passed": True,
        "doc": "docs/RIBDIGI_HOUSE_CONSOLE_MVP.md",
        "register": "ops/mvp/ribdigi-house-console.json",
        "packaging_complete": True,
        "billing_complete_claimed": False,
        "payment_provider_claimed": False,
        "subscriptions_live_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["billing_complete_claimed"] is False
    assert loaded["step_count"] >= 10
