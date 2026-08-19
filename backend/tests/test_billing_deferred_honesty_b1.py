"""Stage 36 B1 — Billing-deferred honesty (not paid billing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
DEFERRED = ROOT / "ops" / "mvp" / "deferred-adr-register.json"
SLA = ROOT / "ops" / "mvp" / "support-sla-boundary.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage36_b1_billing_deferred_honesty.json"

REQUIRED_IDS = {
    "bd-adr002-indexed",
    "bd-plan-code-metadata",
    "bd-serialize-flags",
    "bd-no-fake-payment",
    "bd-plan-audit",
    "bd-lifecycle-gate",
    "bd-deferred-register",
    "bd-post-mvp-backlog",
    "bd-br13-partial",
    "bd-live-billing-remaining",
}
REQUIRED_CATEGORIES = {"adr", "billing", "audit", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_billing_deferred_honesty_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "36"
    assert mapping["workstream"] == "B1"
    assert mapping["packaging_complete"] is True
    assert mapping["billing_complete_claimed"] is False
    assert mapping["payment_provider_claimed"] is False
    assert mapping["checkout_success_claimed"] is False
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/BILLING_DEFERRED_HONESTY_MVP.md"
    assert "stage36_b1_billing_deferred_honesty.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "bd-live-billing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "bd-adr002-indexed" for s in steps)
    assert any(
        "billing" in d.lower() or "payment" in d.lower() or "checkout" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["adr_002"],
        mapping["deferred_adr_register"],
        mapping["post_mvp_backlog"],
        mapping["support_sla_boundary"],
        mapping["plan_billing_test"],
        mapping["stage36_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_billing_deferred_honesty_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    deferred = json.loads(DEFERRED.read_text(encoding="utf-8"))
    sla = json.loads(SLA.read_text(encoding="utf-8"))
    assert deferred.get("billing_complete_claimed") is False
    assert sla.get("support_sla_claimed") is False
    assert mapping["billing_complete_claimed"] is False
    assert mapping["payment_provider_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    adr = _read("docs/ADR_002_BILLING_DEFERRED.md")
    assert "billing_deferred" in adr
    assert "post-MVP" in adr or "post-mvp" in adr.lower() or "Paid" in adr


def test_billing_deferred_honesty_doc_and_readme():
    doc = _read("docs/BILLING_DEFERRED_HONESTY_MVP.md")
    assert "Stage 36 B1" in doc
    assert "test_billing_deferred_honesty_b1.py" in doc
    assert "billing-deferred-honesty.json" in doc
    assert "stage36_b1_billing_deferred_honesty.json" in doc
    assert "billing_complete_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "ADR-002" in doc or "ADR_002" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 36 B1" in readme
    assert "BILLING_DEFERRED_HONESTY_MVP.md" in readme
    assert "billing-deferred-honesty.json" in readme


def test_b1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_36_PLAN.md")
    b1_line = [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_billing_deferred_honesty_b1.py" in plan
    assert (
        "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H36x" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_billing_deferred_honesty_b1.py" in launch
    assert "Stage 36 B1" in launch
    assert "BILLING_DEFERRED_HONESTY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 36 B1" in roadmap
    assert "test_billing_deferred_honesty_b1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 36 B1" in pr
    assert "test_billing_deferred_honesty_b1.py" in pr or "BILLING_DEFERRED_HONESTY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "36",
        "workstream": "B1",
        "passed": True,
        "doc": "docs/BILLING_DEFERRED_HONESTY_MVP.md",
        "register": "ops/mvp/billing-deferred-honesty.json",
        "packaging_complete": True,
        "billing_complete_claimed": False,
        "payment_provider_claimed": False,
        "checkout_success_claimed": False,
        "deferred_implemented_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["billing_complete_claimed"] is False
    assert loaded["payment_provider_claimed"] is False
    assert loaded["checkout_success_claimed"] is False
    assert loaded["step_count"] >= 10
