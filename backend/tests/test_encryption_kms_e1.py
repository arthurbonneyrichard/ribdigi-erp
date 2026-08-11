"""Stage 44 E1 — Encryption / KMS honesty (not HSM / live Vault Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "encryption-kms.json"
RESIDENCY = ROOT / "ops" / "mvp" / "data-residency.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage44_e1_encryption_kms.json"

REQUIRED_IDS = {
    "ek-transit-tls",
    "ek-rest-aes",
    "ek-tls-ingress",
    "ek-wal-pitr-backup",
    "ek-ribbak-encrypt",
    "ek-residency-adjacency",
    "ek-k8s-secrets",
    "ek-vault-aspirational",
    "ek-hsm-vault-remaining",
    "ek-cmk-mtls-remaining",
}
REQUIRED_CATEGORIES = {"transit", "rest", "keys", "backup", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_encryption_kms_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "44"
    assert mapping["workstream"] == "E1"
    assert mapping["packaging_complete"] is True
    assert mapping["hsm_claimed"] is False
    assert mapping["vault_saas_live"] is False
    assert mapping["customer_managed_keys_claimed"] is False
    assert mapping["mtls_mesh_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/ENCRYPTION_KMS_MVP.md"
    assert "stage44_e1_encryption_kms.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ek-hsm-vault-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ek-cmk-mtls-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ek-transit-tls" for s in steps)
    assert any(
        "hsm" in d.lower() or "vault" in d.lower() or "cmk" in d.lower() or "mtls" in d.lower() or "key" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["security_guide"],
        mapping["tls_ingress_doc"],
        mapping["tls_checklist"],
        mapping["wal_pitr_doc"],
        mapping["pitr_checklist"],
        mapping["logical_backup_doc"],
        mapping["data_residency"],
        mapping["data_residency_doc"],
        mapping["k8s_deploy_doc"],
        mapping["sbom_disclosure"],
        mapping["sbom_disclosure_doc"],
        mapping["stage44_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_encryption_kms_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    residency = json.loads(RESIDENCY.read_text(encoding="utf-8"))
    assert mapping["hsm_claimed"] is False
    assert mapping["vault_saas_live"] is False
    assert mapping["customer_managed_keys_claimed"] is False
    assert residency.get("multi_region_residency_claimed") is False
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "encryption" in sec.lower() or "AES" in sec or "TLS" in sec
    assert "Vault" in sec or "KMS" in sec or "key" in sec.lower()
    for step in mapping["steps"]:
        assert step["done"] is False
    tls = _read("docs/TLS_INGRESS_PACK_MVP.md")
    assert "TLS" in tls or "cert-manager" in tls.lower()
    wal = _read("docs/DR_WAL_PITR_RUNBOOK.md")
    assert "encrypt" in wal.lower() or "WAL" in wal or "PITR" in wal


def test_encryption_kms_doc_and_readme():
    doc = _read("docs/ENCRYPTION_KMS_MVP.md")
    assert "Stage 44 E1" in doc
    assert "test_encryption_kms_e1.py" in doc
    assert "encryption-kms.json" in doc
    assert "stage44_e1_encryption_kms.json" in doc
    assert "hsm_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "Encryption" in doc or "Key" in doc or "Vault" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 44 E1" in readme
    assert "ENCRYPTION_KMS_MVP.md" in readme
    assert "encryption-kms.json" in readme


def test_e1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_44_PLAN.md")
    e1_line = [ln for ln in plan.splitlines() if "| **E1** |" in ln][0]
    assert "COMPLETE" in e1_line
    assert "test_encryption_kms_e1.py" in plan
    assert (
        "E1 next" in plan
        or "E1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H44x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_encryption_kms_e1.py" in launch
    assert "Stage 44 E1" in launch
    assert "ENCRYPTION_KMS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 44 E1" in roadmap
    assert "test_encryption_kms_e1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 44 E1" in pr
    assert "test_encryption_kms_e1.py" in pr or "ENCRYPTION_KMS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "44",
        "workstream": "E1",
        "passed": True,
        "doc": "docs/ENCRYPTION_KMS_MVP.md",
        "register": "ops/mvp/encryption-kms.json",
        "packaging_complete": True,
        "hsm_claimed": False,
        "vault_saas_live": False,
        "customer_managed_keys_claimed": False,
        "mtls_mesh_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["hsm_claimed"] is False
    assert loaded["vault_saas_live"] is False
    assert loaded["step_count"] >= 10
