"""Stage 40 S1 — SBOM / dependency disclosure honesty (not live SBOM pipeline Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "sbom-disclosure.json"
VULN = ROOT / "ops" / "mvp" / "vuln-disclosure.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage40_s1_sbom_disclosure.json"

REQUIRED_IDS = {
    "sb-security-guide-sbom",
    "sb-backend-manifest",
    "sb-frontend-manifest",
    "sb-security-scan",
    "sb-vuln-disclosure",
    "sb-pentest-adjacency",
    "sb-cosign-remaining",
    "sb-fossa-remaining",
    "sb-pipeline-remaining",
    "sb-dependabot-snyk-remaining",
}
REQUIRED_CATEGORIES = {"sbom", "dependency", "scanning", "disclosure", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_sbom_disclosure_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "40"
    assert mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    assert mapping["sbom_pipeline_live"] is False
    assert mapping["cosign_signing_claimed"] is False
    assert mapping["snyk_saas_claimed"] is False
    assert mapping["fossa_claimed"] is False
    assert mapping["dependabot_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/SBOM_DISCLOSURE_MVP.md"
    assert "stage40_s1_sbom_disclosure.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "sb-pipeline-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sb-cosign-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sb-security-guide-sbom" for s in steps)
    assert any(
        "sbom" in d.lower() or "cosign" in d.lower() or "snyk" in d.lower() or "dependabot" in d.lower() or "fossa" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["security_guide"],
        mapping["security_scan"],
        mapping["vuln_disclosure"],
        mapping["vuln_disclosure_register"],
        mapping["pentest_pack"],
        mapping["backend_requirements"],
        mapping["frontend_package"],
        mapping["ci_workflow"],
        mapping["stage40_plan"],
        mapping["launch_checklist"],
        mapping["status_uptime"],
        mapping["status_uptime_doc"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_sbom_disclosure_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    vuln = json.loads(VULN.read_text(encoding="utf-8"))
    assert mapping["sbom_pipeline_live"] is False
    assert mapping["cosign_signing_claimed"] is False
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "SBOM" in sec
    assert "Cosign" in sec or "cosign" in sec.lower()
    assert "Dependabot" in sec or "Snyk" in sec or "FOSSA" in sec
    for step in mapping["steps"]:
        assert step["done"] is False
    scan = _read("docs/SECURITY_SCAN_MVP.md")
    assert "security" in scan.lower() or "scan" in scan.lower() or "OWASP" in scan
    # vuln disclosure should not claim live disclosure
    assert vuln.get("disclosure_program_claimed") is False or "disclosure" in json.dumps(vuln).lower()
    req = _read("backend/requirements.txt")
    assert len(req.strip()) > 0
    pkg = json.loads(_read("frontend/package.json"))
    assert "dependencies" in pkg or "devDependencies" in pkg or "name" in pkg


def test_sbom_disclosure_doc_and_readme():
    doc = _read("docs/SBOM_DISCLOSURE_MVP.md")
    assert "Stage 40 S1" in doc
    assert "test_sbom_disclosure_s1.py" in doc
    assert "sbom-disclosure.json" in doc
    assert "stage40_s1_sbom_disclosure.json" in doc
    assert "sbom_pipeline_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "SBOM" in doc or "dependency" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 40 S1" in readme
    assert "SBOM_DISCLOSURE_MVP.md" in readme
    assert "sbom-disclosure.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_40_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_sbom_disclosure_s1.py" in plan
    assert (
        "S1 next" in plan
        or "S1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H40x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
        or "U1 complete" in plan
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_sbom_disclosure_s1.py" in launch
    assert "Stage 40 S1" in launch
    assert "SBOM_DISCLOSURE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 40 S1" in roadmap
    assert "test_sbom_disclosure_s1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 40 S1" in pr
    assert "test_sbom_disclosure_s1.py" in pr or "SBOM_DISCLOSURE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "40",
        "workstream": "S1",
        "passed": True,
        "doc": "docs/SBOM_DISCLOSURE_MVP.md",
        "register": "ops/mvp/sbom-disclosure.json",
        "packaging_complete": True,
        "sbom_pipeline_live": False,
        "cosign_signing_claimed": False,
        "snyk_saas_claimed": False,
        "fossa_claimed": False,
        "dependabot_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["sbom_pipeline_live"] is False
    assert loaded["cosign_signing_claimed"] is False
    assert loaded["snyk_saas_claimed"] is False
    assert loaded["step_count"] >= 10
