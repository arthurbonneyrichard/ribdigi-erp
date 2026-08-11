"""Stage 33 K1 — residual risk register (not risks closed / go-live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "residual-risk-register.json"
REMAINING = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
DEFERRED = ROOT / "ops" / "mvp" / "deferred-adr-register.json"
BACKLOG = ROOT / "ops" / "mvp" / "post-mvp-backlog.json"
DECLARATION = ROOT / "ops" / "mvp" / "mvp-declaration.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage33_k1_residual_risk.json"

REQUIRED_IDS = {
    "rr-go-live-unsigned",
    "rr-live-drills",
    "rr-hosted-saas",
    "rr-vendor-pentest",
    "rr-billing-deferred",
    "rr-schema-per-tenant",
    "rr-i18n-packs",
    "rr-main-ci-deploy",
    "rr-packaging-vs-live",
    "rr-open-banking-tax",
}
REQUIRED_CATEGORIES = {
    "go_live",
    "operations",
    "security",
    "deferred_adr",
    "ci_cd",
    "honesty",
    "product_deferred",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_residual_risk_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "33"
    assert mapping["workstream"] == "K1"
    assert mapping["register_complete"] is True
    assert mapping["risks_closed_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["doc"] == "docs/RESIDUAL_RISK_MVP.md"
    assert "stage33_k1_residual_risk.json" in mapping["evidence_artifact"]
    risks = mapping["risks"]
    assert len(risks) >= 10
    ids = {r["id"] for r in risks}
    assert REQUIRED_IDS.issubset(ids)
    cats = {r["category"] for r in risks}
    assert REQUIRED_CATEGORIES.issubset(cats)
    for risk in risks:
        assert risk["closed"] is False
        assert risk["status"] in ("open", "accepted")
        assert risk["title"]
        assert risk["source"]
        assert risk["severity"] in ("high", "medium", "low")
    assert any(r["id"] == "rr-go-live-unsigned" and r["status"] == "open" for r in risks)
    assert any(r["category"] == "deferred_adr" and r["status"] == "accepted" for r in risks)
    assert any("closed" in d.lower() or "§7" in d or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (
        mapping["operator_remaining_register"],
        mapping["deferred_adr_register"],
        mapping["post_mvp_backlog"],
        mapping["mvp_declaration"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_residual_risk_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    remaining = json.loads(REMAINING.read_text(encoding="utf-8"))
    deferred = json.loads(DEFERRED.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))

    assert remaining["live_runs_certified"] is False
    assert remaining["attestation_claimed"] is False
    assert remaining["section_7_signed"] is False
    assert deferred["deferred_implemented_claimed"] is False
    assert backlog["deferred_implemented_claimed"] is False
    assert declaration["go_live_claimed"] is False
    assert declaration["packaging_complete"] is True
    assert mapping["risks_closed_claimed"] is False
    assert mapping["go_live_claimed"] is False
    for risk in mapping["risks"]:
        assert risk["closed"] is False


def test_residual_risk_doc_and_readme():
    doc = _read("docs/RESIDUAL_RISK_MVP.md")
    assert "Stage 33 K1" in doc
    assert "test_residual_risk_k1.py" in doc
    assert "residual-risk-register.json" in doc
    assert "stage33_k1_residual_risk.json" in doc
    assert "OPERATOR_REMAINING_MVP.md" in doc
    assert "risks_closed_claimed" in doc or "closed: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 33 K1" in readme
    assert "RESIDUAL_RISK_MVP.md" in readme
    assert "residual-risk-register.json" in readme


def test_k1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_33_PLAN.md")
    k1_line = [ln for ln in plan.splitlines() if "| **K1** |" in ln][0]
    assert "COMPLETE" in k1_line
    assert "test_residual_risk_k1.py" in plan
    assert (
        "K1 next" in plan
        or "K1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "F1 next" in plan
        or "T1 next" in plan
        or "D1 next" in plan
        or "H33x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_residual_risk_k1.py" in launch
    assert "Stage 33 K1" in launch
    assert "RESIDUAL_RISK_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 33 K1" in roadmap
    assert "test_residual_risk_k1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 33 K1" in pr
    assert "test_residual_risk_k1.py" in pr or "RESIDUAL_RISK_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 33 K1" in sec or "RESIDUAL_RISK_MVP.md" in sec

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "33",
        "workstream": "K1",
        "passed": True,
        "doc": "docs/RESIDUAL_RISK_MVP.md",
        "register": "ops/mvp/residual-risk-register.json",
        "register_complete": True,
        "risks_closed_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "risk_count": len(mapping["risks"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["risks_closed_claimed"] is False
    assert loaded["go_live_claimed"] is False
    assert loaded["risk_count"] >= 10
