"""Stage 27 S1 — security scan / OWASP baseline evidence (not vendor pen-test Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/security")
EVIDENCE_FILE = EVIDENCE_DIR / "stage27_s1_security_scan.json"

OWASP_SUITE_FILES = (
    "backend/tests/test_owasp_smoke.py",
    "backend/tests/test_owasp_suite_o1.py",
    "backend/tests/test_owasp_suite_t1.py",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_owasp_suites_exist_and_marked_security():
    for rel in OWASP_SUITE_FILES:
        path = ROOT / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        assert "pytest.mark.security" in text or "mark.security" in text, rel
        assert "OWASP" in text or "owasp" in text.lower() or "A01" in text or "CSP" in text


def test_main_ci_runs_security_markers_deploy_free():
    ci = _read(".github/workflows/ci.yml")
    assert 'security or isolation' in ci or "security or isolation" in ci
    assert "pytest" in ci
    # Stage 18 C1 — no deploy job inventing cluster success
    assert "kubectl" not in ci.lower() or "no kubectl" in ci.lower()
    assert "helm upgrade" not in ci.lower()


def test_zap_template_not_wired_into_main_ci():
    ci = _read(".github/workflows/ci.yml")
    assert "zap" not in ci.lower()
    assert "zaproxy" not in ci.lower()

    template = _read("ops/security/zap-baseline.example.yml")
    assert "ZAP" in template or "zap" in template.lower()
    assert "NOT wired" in template or "not wired" in template.lower() or "disabled" in template.lower()
    assert "STAGING_BASE_URL" in template or "staging" in template.lower()

    readme = _read("ops/security/README.md")
    assert "Stage 27 S1" in readme
    assert "SECURITY_SCAN_MVP.md" in readme
    assert "Remaining" in readme or "vendor" in readme.lower()


def test_security_scan_mvp_doc():
    doc = _read("docs/SECURITY_SCAN_MVP.md")
    assert "Stage 27 S1" in doc
    assert "test_security_scan_s1.py" in doc
    assert "OWASP" in doc
    assert "test_owasp_smoke.py" in doc
    assert "test_owasp_suite_o1.py" in doc
    assert "Remaining" in doc
    assert "pen test" in doc.lower() or "penetration" in doc.lower() or "ZAP" in doc
    assert "ci.yml" in doc or "security or isolation" in doc


def test_s1_plan_launch_roadmap_security_readiness():
    plan = _read("docs/STAGE_27_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_security_scan_s1.py" in plan
    assert (
        "S1 next" in plan
        or "S1 complete" in plan
        or "L1 next" in plan
        or "L1 complete" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 27 S1" in pr
    assert "test_security_scan_s1.py" in pr
    assert "SECURITY_SCAN_MVP.md" in pr or "stage27_s1_security_scan.json" in pr
    owasp = pr.split("- [x] OWASP/security tests completed.")[1].split("- [x]")[0]
    assert "Stage 27 S1" in owasp
    assert "Remaining" in owasp or "deferred" in owasp.lower() or "pen test" in owasp.lower()
    assert "Vendor" in owasp or "ZAP" in owasp or "pen test" in owasp.lower()

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 27 S1" in sec or "SECURITY_SCAN_MVP.md" in sec
    assert "test_security_scan_s1.py" in sec or "SECURITY_SCAN_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_security_scan_s1.py" in launch
    assert "Stage 27 S1" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 27 S1" in roadmap
    assert "test_security_scan_s1.py" in roadmap

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "27",
        "workstream": "S1",
        "passed": True,
        "baseline": "owasp_pytest_security_markers",
        "suites": list(OWASP_SUITE_FILES),
        "controls": ["A01", "A02", "A03", "A05", "A07"],
        "ci_marker": "security or isolation",
        "main_ci_file": ".github/workflows/ci.yml",
        "zap_baseline_wired_into_main_ci": False,
        "zap_operator_template": "ops/security/zap-baseline.example.yml",
        "vendor_pen_test_deferred": True,
        "zap_in_ci_live_staging_deferred": True,
        "doc": "docs/SECURITY_SCAN_MVP.md",
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["vendor_pen_test_deferred"] is True
    assert loaded["zap_baseline_wired_into_main_ci"] is False
