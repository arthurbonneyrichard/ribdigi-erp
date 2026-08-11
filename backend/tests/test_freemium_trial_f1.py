"""Stage 50 F1 — freemium trial honesty (not live freemium conversion Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "freemium-trial.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
REFERRAL = ROOT / "ops" / "mvp" / "referral-program.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage50_f1_freemium_trial.json"

REQUIRED_IDS = {
    "ft-product-overview",
    "ft-stage21-trial",
    "ft-billing-deferred",
    "ft-referral-adjacency",
    "ft-pricing-adjacency",
    "ft-deferred-adr",
    "ft-roadmap-backlog",
    "ft-plan-honesty",
    "ft-conversion-remaining",
    "ft-billing-remaining",
}
REQUIRED_CATEGORIES = {"freemium", "trial", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_freemium_trial_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "50"
    assert mapping["workstream"] == "F1"
    assert mapping["packaging_complete"] is True
    assert mapping["freemium_trial_live"] is False
    assert mapping["freemium_conversion_claimed"] is False
    assert mapping["paid_trial_billing_claimed"] is False
    assert mapping["no_cc_trial_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/FREEMIUM_TRIAL_MVP.md"
    assert "stage50_f1_freemium_trial.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ft-conversion-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ft-billing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "freemium" in d.lower() or "trial" in d.lower() or "billing" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["stage21_fidelity"],
        mapping["stage21_plan"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["referral_program"],
        mapping["referral_program_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage50_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_freemium_trial_aligns_billing_and_referral():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    referral = json.loads(REFERRAL.read_text(encoding="utf-8"))
    assert mapping["freemium_trial_live"] is False
    assert mapping["freemium_conversion_claimed"] is False
    assert mapping["paid_trial_billing_claimed"] is False
    assert billing.get("billing_complete_claimed") is False
    assert billing.get("payment_provider_claimed") is False
    assert billing.get("checkout_success_claimed") is False
    assert referral.get("referral_program_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "trial" in po.lower() or "Freemium" in po or "freemium" in po.lower()
    s21 = _read("docs/STAGE_21_FIDELITY.md")
    assert "trial" in s21.lower() or "grace" in s21.lower()


def test_freemium_trial_doc_and_readme():
    doc = _read("docs/FREEMIUM_TRIAL_MVP.md")
    assert "Stage 50 F1" in doc
    assert "test_freemium_trial_f1.py" in doc
    assert "freemium-trial.json" in doc
    assert "stage50_f1_freemium_trial.json" in doc
    assert "freemium_trial_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "trial" in doc.lower() or "freemium" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 50 F1" in readme
    assert "FREEMIUM_TRIAL_MVP.md" in readme
    assert "freemium-trial.json" in readme


def test_f1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_50_PLAN.md")
    f1_line = [ln for ln in plan.splitlines() if "| **F1** |" in ln][0]
    assert "COMPLETE" in f1_line
    assert "test_freemium_trial_f1.py" in plan
    assert (
        "F1 next" in plan
        or "F1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H50x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_freemium_trial_f1.py" in launch
    assert "Stage 50 F1" in launch
    assert "FREEMIUM_TRIAL_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 50 F1" in roadmap
    assert "test_freemium_trial_f1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 50 F1" in pr
    assert "test_freemium_trial_f1.py" in pr or "FREEMIUM_TRIAL_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "50",
        "workstream": "F1",
        "passed": True,
        "doc": "docs/FREEMIUM_TRIAL_MVP.md",
        "register": "ops/mvp/freemium-trial.json",
        "packaging_complete": True,
        "freemium_trial_live": False,
        "freemium_conversion_claimed": False,
        "paid_trial_billing_claimed": False,
        "no_cc_trial_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["freemium_conversion_claimed"] is False
    assert loaded["paid_trial_billing_claimed"] is False
    assert loaded["step_count"] >= 10
