"""Stage 35 V1 — E2E verify financials (not live verification Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-verify-financials.json"
SALE = ROOT / "ops" / "mvp" / "e2e-sale-payment.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage35_v1_e2e_verify_financials.json"

REQUIRED_IDS = {
    "vf-verify-tax",
    "vf-verify-accounting",
    "vf-verify-credit",
    "vf-verify-reports",
    "vf-verify-audit",
    "vf-trial-balance",
    "vf-tenant-isolation",
    "vf-ar-ap-aging",
    "vf-tax-efile-deferred",
    "vf-live-verify-remaining",
}
REQUIRED_CATEGORIES = {"tax", "accounting", "credit", "reports", "audit", "security", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_e2e_verify_financials_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "35"
    assert mapping["workstream"] == "V1"
    assert mapping["packaging_complete"] is True
    assert mapping["live_verify_financials_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["tax_efile_claimed"] is False
    assert mapping["doc"] == "docs/E2E_VERIFY_FINANCIALS_MVP.md"
    assert "stage35_v1_e2e_verify_financials.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "vf-tax-efile-deferred" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "vf-verify-audit" for s in steps)
    assert any(
        "verify" in d.lower() or "e-file" in d.lower() or "banking" in d.lower() or "demo" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["e2e_sale_payment"],
        mapping["stage14_plan"],
        mapping["stage15_plan"],
        mapping["stage16_plan"],
        mapping["stage22_plan"],
        mapping["stage23_plan"],
        mapping["launch_checklist"],
        mapping["api_docs"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_e2e_verify_financials_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    sale = json.loads(SALE.read_text(encoding="utf-8"))
    assert sale["e2e_smoke_executed_claimed"] is False
    assert sale["demo_tenant_claimed"] is False
    assert mapping["live_verify_financials_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["tax_efile_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    stage35 = _read("docs/STAGE_35_PLAN.md")
    assert "Open Banking" in stage35 or "tax e-file" in stage35.lower()


def test_e2e_verify_financials_doc_and_readme():
    doc = _read("docs/E2E_VERIFY_FINANCIALS_MVP.md")
    assert "Stage 35 V1" in doc
    assert "test_e2e_verify_financials_v1.py" in doc
    assert "e2e-verify-financials.json" in doc
    assert "stage35_v1_e2e_verify_financials.json" in doc
    assert "live_verify_financials_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "e-file" in doc.lower() or "Open Banking" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 35 V1" in readme
    assert "E2E_VERIFY_FINANCIALS_MVP.md" in readme
    assert "e2e-verify-financials.json" in readme


def test_v1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_35_PLAN.md")
    v1_line = [ln for ln in plan.splitlines() if "| **V1** |" in ln][0]
    assert "COMPLETE" in v1_line
    assert "test_e2e_verify_financials_v1.py" in plan
    assert (
        "V1 next" in plan
        or "V1 complete" in plan
        or "R1 next" in plan
        or "R1 complete" in plan
        or "D1 next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_e2e_verify_financials_v1.py" in launch
    assert "Stage 35 V1" in launch
    assert "E2E_VERIFY_FINANCIALS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 35 V1" in roadmap
    assert "test_e2e_verify_financials_v1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 35 V1" in pr
    assert "test_e2e_verify_financials_v1.py" in pr or "E2E_VERIFY_FINANCIALS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "35",
        "workstream": "V1",
        "passed": True,
        "doc": "docs/E2E_VERIFY_FINANCIALS_MVP.md",
        "register": "ops/mvp/e2e-verify-financials.json",
        "packaging_complete": True,
        "live_verify_financials_claimed": False,
        "e2e_smoke_executed_claimed": False,
        "demo_tenant_claimed": False,
        "tax_efile_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_verify_financials_claimed"] is False
    assert loaded["e2e_smoke_executed_claimed"] is False
    assert loaded["tax_efile_claimed"] is False
    assert loaded["step_count"] >= 10
