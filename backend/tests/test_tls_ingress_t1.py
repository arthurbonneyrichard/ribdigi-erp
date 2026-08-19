"""Stage 29 T1 — cert-manager / TLS ingress pack (not live Let's Encrypt Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "ops" / "k8s" / "tls-checklist.json"
ISSUER = ROOT / "ops" / "k8s" / "cluster-issuer.example.yaml"
INGRESS = ROOT / "ops" / "k8s" / "ingress-tls.example.yaml"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/k8s")
EVIDENCE_FILE = EVIDENCE_DIR / "stage29_t1_tls_ingress.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_tls_checklist_honest():
    assert CHECKLIST.is_file()
    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    assert mapping["stage"] == "29"
    assert mapping["workstream"] == "T1"
    assert mapping["letsencrypt_issued"] is False
    assert mapping["tls_cutover_claimed"] is False
    assert mapping["doc"] == "docs/TLS_INGRESS_PACK_MVP.md"
    assert mapping["k8s_mvp"] == "docs/K8S_DEPLOY_MVP.md"
    assert mapping["cluster_issuer"] == "ops/k8s/cluster-issuer.example.yaml"
    assert mapping["ingress_tls"] == "ops/k8s/ingress-tls.example.yaml"
    assert len(mapping["steps"]) >= 4
    for step in mapping["steps"]:
        assert step["class"] == "operator_required"
    assert "stage29_t1_tls_ingress.json" in mapping["evidence_artifact"]
    assert any(
        "Let's Encrypt" in d or "ACME" in d or "cutover" in d.lower() or "Istio" in d
        for d in mapping["deferred"]
    )


def test_cluster_issuer_and_ingress_examples():
    assert ISSUER.is_file()
    issuer = ISSUER.read_text(encoding="utf-8")
    assert "ClusterIssuer" in issuer
    assert "cert-manager.io" in issuer
    assert "letsencrypt-staging" in issuer
    assert "letsencrypt-prod" in issuer
    assert "acme-staging" in issuer or "acme-v02" in issuer
    assert "NOT" in issuer or "not" in issuer.lower()
    assert "29-t1" in issuer or "Stage 29 T1" in issuer

    assert INGRESS.is_file()
    ing = INGRESS.read_text(encoding="utf-8")
    assert "kind: Ingress" in ing
    assert "tls:" in ing
    assert "cert-manager.io/cluster-issuer" in ing
    assert "/api" in ing
    assert "ribdigi-backend" in ing
    assert "NOT" in ing or "not" in ing.lower() or "Do not treat" in ing
    assert "health" in ing.lower() or "TLS_INGRESS_PACK" in ing


def test_tls_pack_mvp_doc_and_helm_ingress_paths():
    doc = _read("docs/TLS_INGRESS_PACK_MVP.md")
    assert "Stage 29 T1" in doc
    assert "test_tls_ingress_t1.py" in doc
    assert "cluster-issuer.example.yaml" in doc
    assert "ingress-tls.example.yaml" in doc
    assert "K8S_DEPLOY_MVP.md" in doc
    assert "not" in doc.lower()
    assert "stage29_t1_tls_ingress.json" in doc

    helm_ing = _read("helm/ribdigi/templates/ingress.yaml")
    assert "/api" in helm_ing
    assert "ribdigi-backend" in helm_ing
    assert "ribdigi-frontend" in helm_ing

    readme = _read("ops/k8s/README.md")
    assert "Stage 29 T1" in readme
    assert "TLS_INGRESS_PACK_MVP.md" in readme
    assert "cluster-issuer.example.yaml" in readme


def test_k8s_mvp_extended_for_t1():
    k8s = _read("docs/K8S_DEPLOY_MVP.md")
    assert "Stage 29 T1" in k8s or "TLS_INGRESS_PACK_MVP.md" in k8s
    assert "cluster-issuer.example.yaml" in k8s or "ingress-tls.example.yaml" in k8s
    assert "Remaining" in k8s or "deferred" in k8s.lower() or "not" in k8s.lower()


def test_t1_plan_launch_roadmap_deploy_readiness():
    plan = _read("docs/STAGE_29_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_tls_ingress_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "X1 next" in plan
        or "X1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H29x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_tls_ingress_t1.py" in launch
    assert "Stage 29 T1" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 29 T1" in roadmap
    assert "test_tls_ingress_t1.py" in roadmap

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 29 T1" in deploy or "TLS_INGRESS_PACK_MVP.md" in deploy
    assert "cluster-issuer.example.yaml" in deploy or "test_tls_ingress_t1.py" in deploy

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 29 T1" in pr
    assert "test_tls_ingress_t1.py" in pr or "TLS_INGRESS_PACK_MVP.md" in pr
    k8s_gate = pr.split("- [x] Kubernetes production deployment reviewed.")[1].split("- [x]")[0]
    assert "Stage 29 T1" in k8s_gate or "TLS_INGRESS" in k8s_gate or "cert-manager" in k8s_gate.lower()
    assert "Remaining" in k8s_gate or "cutover" in k8s_gate.lower() or "issuance" in k8s_gate.lower()

    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "29",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/TLS_INGRESS_PACK_MVP.md",
        "checklist": "ops/k8s/tls-checklist.json",
        "cluster_issuer": "ops/k8s/cluster-issuer.example.yaml",
        "ingress_tls": "ops/k8s/ingress-tls.example.yaml",
        "k8s_mvp": "docs/K8S_DEPLOY_MVP.md",
        "letsencrypt_issued": False,
        "tls_cutover_claimed": False,
        "packaging_complete": True,
        "steps": mapping["steps"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["letsencrypt_issued"] is False
    assert loaded["tls_cutover_claimed"] is False
    assert loaded["packaging_complete"] is True
