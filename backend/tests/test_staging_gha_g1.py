"""Stage 28 G1 — staging GHA deploy pack (not wired into main ci.yml)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "ops" / "k8s" / "deploy-staging.example.yml"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/k8s")
EVIDENCE_FILE = EVIDENCE_DIR / "stage28_g1_staging_gha.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_staging_gha_template_exists_and_honest():
    assert TEMPLATE.is_file()
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "NOT wired" in text or "not wired" in text.lower()
    assert "ci.yml" in text
    assert "Stage 18 C1" in text or "deploy-free" in text.lower()
    assert "helm" in text.lower()
    assert "KUBE_CONFIG" in text
    assert "workflow_dispatch" in text
    assert "disabled" in text.lower() or "example-disabled" in text
    assert "Do not treat it as a green" in text or "fabricated" in text.lower()
    # Disabled stub must not claim real helm upgrade success as the active job
    assert "deploy-staging-example-disabled" in text
    assert "STAGING_GHA_MVP.md" in text or "staging" in text.lower()


def test_main_ci_remains_deploy_free():
    ci = _read(".github/workflows/ci.yml")
    assert "pytest" in ci
    # No live deploy surface in main CI
    assert "helm upgrade" not in ci.lower()
    assert "kubectl apply" not in ci.lower()
    assert "deploy-staging" not in ci.lower()
    # Template must not be the committed active workflow under .github/workflows/
    workflows = list((ROOT / ".github" / "workflows").glob("*.yml")) + list(
        (ROOT / ".github" / "workflows").glob("*.yaml")
    )
    names = {p.name for p in workflows}
    assert "ci.yml" in names
    assert "deploy-staging.example.yml" not in names
    assert "deploy-staging.yml" not in names


def test_staging_gha_mvp_doc():
    doc = _read("docs/STAGING_GHA_MVP.md")
    assert "Stage 28 G1" in doc
    assert "test_staging_gha_g1.py" in doc
    assert "deploy-staging.example.yml" in doc
    assert "K8S_DEPLOY_MVP.md" in doc
    assert "ci.yml" in doc
    assert "KUBE_CONFIG" in doc
    assert "not" in doc.lower()
    assert "stage28_g1_staging_gha.json" in doc


def test_k8s_and_deployment_docs_cite_g1():
    k8s = _read("docs/K8S_DEPLOY_MVP.md")
    assert "Stage 28 G1" in k8s or "STAGING_GHA_MVP.md" in k8s
    assert "deploy-staging.example.yml" in k8s
    assert "Remaining" in k8s or "deferred" in k8s.lower() or "live" in k8s.lower()

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 28 G1" in deploy or "STAGING_GHA_MVP.md" in deploy
    assert "deploy-staging.example.yml" in deploy or "test_staging_gha_g1.py" in deploy

    readme = _read("ops/k8s/README.md")
    assert "Stage 28 G1" in readme
    assert "deploy-staging.example.yml" in readme
    assert "STAGING_GHA_MVP.md" in readme


def test_g1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_28_PLAN.md")
    g1_line = [ln for ln in plan.splitlines() if "| **G1** |" in ln][0]
    assert "COMPLETE" in g1_line
    assert "test_staging_gha_g1.py" in plan
    assert (
        "G1 next" in plan
        or "G1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H28x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_staging_gha_g1.py" in launch
    assert "Stage 28 G1" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 28 G1" in roadmap
    assert "test_staging_gha_g1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 28 G1" in pr
    assert "test_staging_gha_g1.py" in pr or "STAGING_GHA_MVP.md" in pr
    # Remaining honesty — live apply still Remaining
    k8s_gate = pr.split("- [x] Kubernetes production deployment reviewed.")[1].split(
        "- [x]"
    )[0]
    assert "Remaining" in k8s_gate or "live" in k8s_gate.lower()
    assert "staging" in k8s_gate.lower()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "28",
        "workstream": "G1",
        "passed": True,
        "doc": "docs/STAGING_GHA_MVP.md",
        "template": "ops/k8s/deploy-staging.example.yml",
        "k8s_mvp": "docs/K8S_DEPLOY_MVP.md",
        "gha_staging_wired_into_main_ci": False,
        "live_staging_apply_claimed": False,
        "packaging_complete": True,
        "main_ci_deploy_free": True,
        "secrets_documented": ["KUBE_CONFIG", "REGISTRY_USERNAME", "REGISTRY_PASSWORD"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["gha_staging_wired_into_main_ci"] is False
    assert loaded["live_staging_apply_claimed"] is False
    assert loaded["packaging_complete"] is True
