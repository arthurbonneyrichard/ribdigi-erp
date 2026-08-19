"""Stage 29 X1 — production cutover pack (not forged §7 / live cutover Complete)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "ops" / "launch" / "cutover-checklist.json"
EVIDENCE_EXAMPLE = ROOT / "ops" / "launch" / "cutover-evidence.example.json"
GHA = ROOT / "ops" / "k8s" / "deploy-production.example.yml"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage29_x1_cutover_pack.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _section_body(checklist: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in checklist, heading
    rest = checklist.split(marker, 1)[1]
    if "\n## " in rest:
        rest = rest.split("\n## ", 1)[0]
    return rest


def test_cutover_checklist_honest():
    assert CHECKLIST.is_file()
    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    assert mapping["stage"] == "29"
    assert mapping["workstream"] == "X1"
    assert mapping["production_cutover_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["gha_prod_wired_into_main_ci"] is False
    assert mapping["doc"] == "docs/CUTOVER_PACK_MVP.md"
    assert mapping["launch_cert_mvp"] == "docs/LAUNCH_CERT_MVP.md"
    assert mapping["staging_gha_mvp"] == "docs/STAGING_GHA_MVP.md"
    assert mapping["checklist"] == "docs/LAUNCH_CHECKLIST.md"
    assert mapping["gha_template"] == "ops/k8s/deploy-production.example.yml"
    assert mapping["launch_sections_mapped"] == ["1", "2", "3", "7"]
    assert len(mapping["phases"]) >= 5
    for phase in mapping["phases"]:
        assert phase["class"] == "operator_required"
    assert any(p.get("maps_to") == ["7"] or "7" in p.get("maps_to", []) for p in mapping["phases"])
    assert any("1" in p.get("maps_to", []) for p in mapping["phases"])
    assert "stage29_x1_cutover_pack.json" in mapping["evidence_artifact"]
    assert any(
        "§7" in d or "sign-off" in d.lower() or "ci.yml" in d or "cutover" in d.lower()
        for d in mapping["deferred"]
    )


def test_cutover_evidence_schema_not_forged():
    assert EVIDENCE_EXAMPLE.is_file()
    example = json.loads(EVIDENCE_EXAMPLE.read_text(encoding="utf-8"))
    assert example["passed"] is False
    assert example["production_cutover_claimed"] is False
    assert example["section_7_signed"] is False
    assert example["sections_1_3_verified"] is False
    for field in (
        "cutover_id",
        "started_at",
        "finished_at",
        "image_tag",
        "production_base_url",
        "helm_revision_before",
        "helm_revision_after",
        "secrets_handoff_recorded",
        "health_ready_ok",
        "rollback_plan_documented",
        "operator",
        "notes",
    ):
        assert field in example, field
    assert "forged" in example["notes"].lower() or "schema example" in example["notes"].lower()
    assert "CUTOVER_PACK_MVP" in example["notes"] or "Stage 29 X1" in example["notes"]


def test_production_gha_template_outside_main_ci():
    assert GHA.is_file()
    text = GHA.read_text(encoding="utf-8")
    assert "NOT wired" in text or "not wired" in text.lower()
    assert "Stage 29 X1" in text or "29 X1" in text or "29-x1" in text.lower()
    assert "CUTOVER_PACK_MVP" in text or "cutover-checklist" in text
    assert "values-production" in text or "production" in text.lower()
    assert "rollback" in text.lower()
    assert "deploy-production-example-disabled" in text
    assert "CUTOVER" in text

    ci = _read(".github/workflows/ci.yml")
    assert "deploy-production" not in ci.lower() or "example" in ci.lower()
    # Main CI must remain deploy-free
    assert "helm upgrade" not in ci.lower()
    assert "kubectl apply" not in ci.lower()


def test_launch_sections_remain_unsigned_and_pack_docs():
    checklist = _read("docs/LAUNCH_CHECKLIST.md")
    for title in (
        "1. Configuration & secrets",
        "2. Identity & security",
        "3. Integrations (Stage 6–7)",
    ):
        body = _section_body(checklist, title)
        assert re.findall(r"^- \[ \] .+$", body, flags=re.M), title

    signoff = _section_body(checklist, "7. Sign-off")
    assert "| Engineering |" in signoff
    assert re.search(r"\| Engineering \| \| \|", signoff) or "| Engineering | |" in signoff

    doc = _read("docs/CUTOVER_PACK_MVP.md")
    assert "Stage 29 X1" in doc
    assert "test_cutover_pack_x1.py" in doc
    assert "cutover-checklist.json" in doc
    assert "cutover-evidence.example.json" in doc
    assert "deploy-production.example.yml" in doc
    assert "LAUNCH_CERT_MVP.md" in doc
    assert "STAGING_GHA_MVP.md" in doc
    assert "not" in doc.lower()
    assert "§7" in doc or "Sign-off" in doc
    assert "stage29_x1_cutover_pack.json" in doc

    launch_cert = _read("docs/LAUNCH_CERT_MVP.md")
    assert "Stage 29 X1" in launch_cert or "CUTOVER_PACK_MVP.md" in launch_cert

    staging = _read("docs/STAGING_GHA_MVP.md")
    assert "Stage 29 X1" in staging or "CUTOVER_PACK_MVP.md" in staging or "deploy-production" in staging


def test_x1_plan_launch_roadmap_deploy_readiness():
    plan = _read("docs/STAGE_29_PLAN.md")
    x1_line = [ln for ln in plan.splitlines() if "| **X1** |" in ln][0]
    assert "COMPLETE" in x1_line
    assert "test_cutover_pack_x1.py" in plan
    assert (
        "X1 next" in plan
        or "X1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H29x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_cutover_pack_x1.py" in launch
    assert "Stage 29 X1" in launch
    assert "CUTOVER_PACK_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 29 X1" in roadmap
    assert "test_cutover_pack_x1.py" in roadmap

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 29 X1" in deploy or "CUTOVER_PACK_MVP.md" in deploy
    assert "deploy-production.example.yml" in deploy or "test_cutover_pack_x1.py" in deploy

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 29 X1" in pr
    assert "test_cutover_pack_x1.py" in pr or "CUTOVER_PACK_MVP.md" in pr
    k8s_gate = pr.split("- [x] Kubernetes production deployment reviewed.")[1].split("- [x]")[0]
    assert "Stage 29 X1" in k8s_gate or "CUTOVER" in k8s_gate or "cutover" in k8s_gate.lower()
    assert (
        "Remaining" in k8s_gate
        or "§7" in k8s_gate
        or "sign-off" in k8s_gate.lower()
        or "live" in k8s_gate.lower()
    )

    ops = _read("ops/launch/README.md")
    assert "Stage 29 X1" in ops
    assert "cutover-checklist.json" in ops
    assert "CUTOVER_PACK_MVP.md" in ops

    k8s_readme = _read("ops/k8s/README.md")
    assert "deploy-production.example.yml" in k8s_readme
    assert "Stage 29 X1" in k8s_readme or "CUTOVER" in k8s_readme

    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "29",
        "workstream": "X1",
        "passed": True,
        "doc": "docs/CUTOVER_PACK_MVP.md",
        "checklist": "ops/launch/cutover-checklist.json",
        "evidence_schema": "ops/launch/cutover-evidence.example.json",
        "gha_template": "ops/k8s/deploy-production.example.yml",
        "launch_cert_mvp": "docs/LAUNCH_CERT_MVP.md",
        "staging_gha_mvp": "docs/STAGING_GHA_MVP.md",
        "production_cutover_claimed": False,
        "section_7_signed": False,
        "gha_prod_wired_into_main_ci": False,
        "packaging_complete": True,
        "phases": mapping["phases"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["production_cutover_claimed"] is False
    assert loaded["section_7_signed"] is False
    assert loaded["packaging_complete"] is True
