"""Stage 50 R1 — referral program honesty (not live referral credits Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "referral-program.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
PARTNER = ROOT / "ops" / "mvp" / "partner-reseller.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage50_r1_referral_program.json"

REQUIRED_IDS = {
    "rf-product-overview",
    "rf-billing-deferred",
    "rf-partner-adjacency",
    "rf-pricing-adjacency",
    "rf-tos-adjacency",
    "rf-deferred-adr",
    "rf-roadmap-backlog",
    "rf-plan-honesty",
    "rf-credits-remaining",
    "rf-payout-remaining",
}
REQUIRED_CATEGORIES = {"referral", "acquisition", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_referral_program_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "50"
    assert mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    assert mapping["referral_program_live"] is False
    assert mapping["referral_credits_claimed"] is False
    assert mapping["referral_payout_claimed"] is False
    assert mapping["free_month_credit_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/REFERRAL_PROGRAM_MVP.md"
    assert "stage50_r1_referral_program.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "rf-credits-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "rf-payout-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "referral" in d.lower() or "credit" in d.lower() or "payout" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["tos_aup"],
        mapping["tos_aup_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage50_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_referral_program_aligns_billing_deferred():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    partner = json.loads(PARTNER.read_text(encoding="utf-8"))
    assert mapping["referral_program_live"] is False
    assert mapping["referral_credits_claimed"] is False
    assert billing.get("billing_complete_claimed") is False
    assert billing.get("checkout_success_claimed") is False
    assert partner.get("partner_program_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "referral" in po.lower() or "Referral" in po
    bd = _read("docs/BILLING_DEFERRED_HONESTY_MVP.md")
    assert "billing" in bd.lower() or "ADR-002" in bd or "deferred" in bd.lower()


def test_referral_program_doc_and_readme():
    doc = _read("docs/REFERRAL_PROGRAM_MVP.md")
    assert "Stage 50 R1" in doc
    assert "test_referral_program_r1.py" in doc
    assert "referral-program.json" in doc
    assert "stage50_r1_referral_program.json" in doc
    assert "referral_program_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "referral" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 50 R1" in readme
    assert "REFERRAL_PROGRAM_MVP.md" in readme
    assert "referral-program.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_50_PLAN.md")
    r1_line = [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_referral_program_r1.py" in plan
    assert (
        "R1 next" in plan
        or "R1 complete" in plan
        or "F1 next" in plan
        or "F1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H50x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_referral_program_r1.py" in launch
    assert "Stage 50 R1" in launch
    assert "REFERRAL_PROGRAM_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 50 R1" in roadmap
    assert "test_referral_program_r1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 50 R1" in pr
    assert "test_referral_program_r1.py" in pr or "REFERRAL_PROGRAM_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "50",
        "workstream": "R1",
        "passed": True,
        "doc": "docs/REFERRAL_PROGRAM_MVP.md",
        "register": "ops/mvp/referral-program.json",
        "packaging_complete": True,
        "referral_program_live": False,
        "referral_credits_claimed": False,
        "referral_payout_claimed": False,
        "free_month_credit_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["referral_program_live"] is False
    assert loaded["referral_credits_claimed"] is False
    assert loaded["step_count"] >= 10
