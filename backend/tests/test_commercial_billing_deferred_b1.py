"""Stage 76 B1 — Commercial billing deferred honesty (not paid billing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-billing-deferred.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
TERMS = ROOT / "ops" / "mvp" / "commercial-terms.json"
TOS = ROOT / "ops" / "mvp" / "tos-aup.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage76_b1_commercial_billing_deferred.json"

REQUIRED_IDS = {
    "cbd-owner-outline", "cbd-adr002", "cbd-stage36", "cbd-terms", "cbd-tos-aup",
    "cbd-deferred-register", "cbd-plan-honesty", "cbd-provider-ownership",
    "cbd-billing-remaining", "cbd-golive-remaining",
}
REQUIRED_CATEGORIES = {"billing", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_billing_deferred_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "76" and mapping["workstream"] == "B1"
    assert mapping["packaging_complete"] is True
    for k in ("billing_complete_claimed", "payment_provider_claimed", "checkout_success_claimed",
              "deferred_implemented_claimed", "tos_signed_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_BILLING_DEFERRED_MVP.md"
    assert "stage76_b1_commercial_billing_deferred.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cbd-billing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cbd-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("billing" in d.lower() or "payment" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage76_plan"], mapping["adr_002"], mapping["billing_deferred_doc"],
                mapping["billing_deferred"], mapping["terms_doc"], mapping["terms"],
                mapping["tos_aup_doc"], mapping["tos_aup"], mapping["deferred_adr_doc"],
                mapping["deferred_adr"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_billing_deferred_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    tos = json.loads(TOS.read_text(encoding="utf-8"))
    assert mapping["billing_complete_claimed"] is False
    for key in ("billing_complete_claimed", "payment_provider_claimed", "checkout_success_claimed", "go_live_claimed"):
        if key in billing:
            assert billing[key] is False
    for key in ("tos_signed_claimed", "go_live_claimed"):
        if key in terms:
            assert terms[key] is False
    for key in ("tos_signed_claimed", "go_live_claimed"):
        if key in tos:
            assert tos[key] is False
    plan = _read("docs/STAGE_76_PLAN.md")
    assert "Billing" in plan and "Terms" in plan
    adr = _read("docs/ADR_002_BILLING_DEFERRED.md")
    assert "ADR-002" in adr or "billing" in adr.lower()


def test_commercial_billing_deferred_doc_and_readme():
    doc = _read("docs/COMMERCIAL_BILLING_DEFERRED_MVP.md")
    assert "Stage 76 B1" in doc and "test_commercial_billing_deferred_b1.py" in doc
    assert "commercial-billing-deferred.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 76 B1" in readme and "COMMERCIAL_BILLING_DEFERRED_MVP.md" in readme and "commercial-billing-deferred.json" in readme


def test_b1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_76_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "test_commercial_billing_deferred_b1.py" in plan
    assert any(x in plan for x in ("B1 next", "B1 complete", "D1 next", "D1 complete", "H76x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_billing_deferred_b1.py" in launch and "Stage 76 B1" in launch and "COMMERCIAL_BILLING_DEFERRED_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 76 B1" in roadmap and "test_commercial_billing_deferred_b1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 76 B1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "76", "workstream": "B1", "passed": True, "doc": "docs/COMMERCIAL_BILLING_DEFERRED_MVP.md",
               "register": "ops/mvp/commercial-billing-deferred.json", "packaging_complete": True,
               "billing_complete_claimed": False, "payment_provider_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["billing_complete_claimed"] is False and loaded["step_count"] >= 10
