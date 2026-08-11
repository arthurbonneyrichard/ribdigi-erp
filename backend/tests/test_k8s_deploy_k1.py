"""Stage 26 K1 — Kubernetes / Helm production deploy fidelity."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/k8s")
EVIDENCE_FILE = EVIDENCE_DIR / "stage26_k1_deploy_fidelity.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_helm_chart_and_probe_contract():
    chart = _read("helm/ribdigi/Chart.yaml")
    assert "name: ribdigi" in chart
    assert "Stage 26 K1" in chart or "1.0.0" in chart

    values = _read("helm/ribdigi/values.yaml")
    assert "secretName: ribdigi-secrets" in values
    assert "JWT_SECRET_KEY" in values
    assert "DATABASE_URL" in values

    backend = _read("helm/ribdigi/templates/backend-deployment.yaml")
    assert "path: /api/v1/health" in backend
    assert "path: /api/v1/health/ready" in backend
    assert "livenessProbe" in backend
    assert "readinessProbe" in backend
    assert "secretRef" in backend
    assert "resources:" in backend

    assert (ROOT / "helm/ribdigi/templates/frontend-deployment.yaml").is_file()
    assert (ROOT / "helm/ribdigi/templates/celery-worker-deployment.yaml").is_file()
    assert (ROOT / "helm/ribdigi/templates/celery-beat-deployment.yaml").is_file()
    assert (ROOT / "helm/ribdigi/templates/migration-job.yaml").is_file()
    assert "alembic" in _read("helm/ribdigi/templates/migration-job.yaml")
    assert "celery" in _read("helm/ribdigi/templates/celery-worker-deployment.yaml")

    secrets = _read("helm/ribdigi/templates/secrets.example.yaml")
    assert "JWT_SECRET_KEY" in secrets
    assert "DATABASE_URL" in secrets
    assert "REDIS_URL" in secrets
    assert "EXAMPLE" in secrets.upper() or "REPLACE" in secrets


def test_k8s_flat_manifests_hardened():
    backend = _read("k8s/backend.yaml")
    assert "/api/v1/health/ready" in backend
    assert "/api/v1/health" in backend
    assert "readinessProbe" in backend
    assert "ribdigi-secrets" in backend
    assert "resources:" in backend

    for rel in (
        "k8s/frontend.yaml",
        "k8s/celery-worker.yaml",
        "k8s/celery-beat.yaml",
        "k8s/migration-job.yaml",
        "k8s/namespace.yaml",
        "k8s/README.md",
    ):
        assert (ROOT / rel).is_file(), rel
    assert "Stage 26 K1" in _read("k8s/README.md")
    assert "alembic" in _read("k8s/migration-job.yaml")


def test_ops_k8s_smoke_scripts():
    install = _read("ops/k8s/helm-install-staging.sh.example")
    assert "helm upgrade --install" in install
    assert "values-staging.yaml" in install
    assert "ribdigi-secrets" in install

    smoke = _read("ops/k8s/staging-smoke.sh.example")
    assert "/api/v1/health/ready" in smoke
    assert "/api/v1/metrics" in smoke
    assert "ribdigi_up" in smoke
    assert "Stage 26 K1" in smoke


def test_k8s_deploy_mvp_doc():
    doc = _read("docs/K8S_DEPLOY_MVP.md")
    assert "Stage 26 K1" in doc
    assert "test_k8s_deploy_k1.py" in doc
    assert "helm/ribdigi" in doc
    assert "/api/v1/health/ready" in doc
    assert "gha" in doc.lower() or "CI" in doc or "deferred" in doc.lower()
    assert "test_ci_prod_config_c1.py" in doc or "Stage 18 C1" in doc
    assert "stage26_k1_deploy_fidelity.json" in doc


def test_kubernetes_gate_complete_mvp_and_evidence():
    pr = _read("PRODUCTION_READINESS.md")
    assert "- [x] Kubernetes production deployment reviewed." in pr
    assert "- [ ] Kubernetes production deployment reviewed." not in pr
    assert "Stage 26 K1" in pr
    assert "test_k8s_deploy_k1.py" in pr
    assert "helm/ribdigi" in pr or "K8S_DEPLOY_MVP.md" in pr
    assert "GHA" in pr or "staging" in pr.lower() or "Remaining" in pr
    # Load remains open
    assert "- [ ] Load/performance tests meet documented targets." in pr
    # Prior Stage 26 gates stay Complete
    assert "- [x] Monitoring, metrics, logging and alerting complete." in pr
    assert "- [x] Point-in-time recovery/WAL strategy complete." in pr

    # Main CI remains deploy-free (Stage 18 C1)
    ci = _read(".github/workflows/ci.yml")
    assert "deploy:" not in ci
    assert "kubectl" not in ci.lower()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "26",
        "workstream": "K1",
        "passed": True,
        "chart_documented": True,
        "manifests": ["helm/ribdigi/", "k8s/"],
        "smoke_script": "ops/k8s/staging-smoke.sh.example",
        "operator_staging_apply_required": True,
        "gha_staging_deploy_deferred": True,
        "probe_readiness": "/api/v1/health/ready",
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["gha_staging_deploy_deferred"] is True
    assert loaded["probe_readiness"] == "/api/v1/health/ready"


def test_k1_plan_launch_roadmap_cite():
    plan = _read("docs/STAGE_26_PLAN.md")
    k1_line = [ln for ln in plan.splitlines() if "| **K1** |" in ln][0]
    assert "COMPLETE" in k1_line
    assert "test_k8s_deploy_k1.py" in plan
    assert (
        "K1 next" in plan
        or "K1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_k8s_deploy_k1.py" in launch
    assert "Stage 26 K1" in launch or "helm/ribdigi" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 26 K1" in roadmap
    assert "test_k8s_deploy_k1.py" in roadmap
    assert "K8S_DEPLOY_MVP.md" in roadmap or "helm/ribdigi" in roadmap
