"""Stage 78 D1 — documentation fidelity for Commercial Procurement Boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage78_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_78_FIDELITY.md")
    assert "Pricing" in fidelity or "Professional Services" in fidelity or "Procurement" in fidelity
    for name in ("test_commercial_pricing_p1.py", "test_commercial_professional_services_s1.py", "test_stage78_fidelity_d1.py"):
        assert name in fidelity, name
    assert "ADR-162" in fidelity or "ADR_162" in fidelity
    assert "H78x" in fidelity
    plan = _read("docs/STAGE_78_PLAN.md")
    assert "STAGE_78_FIDELITY.md" in plan
    for ws in ("P1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h78 = [ln for ln in plan.splitlines() if "| **H78x** |" in ln][0]
    assert "PENDING" in h78 or "COMPLETE" in h78
    assert any(x in plan for x in ("D1 next", "D1 complete", "H78x next", "Closed", "exit met"))


def test_stage78_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_78_FIDELITY.md" in br
    assert "Stage 78 D1" in br or "test_stage78_fidelity_d1.py" in br
    assert ("Stage 78 P1" in br or "COMMERCIAL_PRICING_MVP.md" in br or "Stage 78 S1" in br or "COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md" in br)
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_78_FIDELITY.md" in fidelity_tail or "Stage 78 D1" in fidelity_tail
    for rel in ("docs/COMMERCIAL_PRICING_MVP.md", "docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md"):
        assert _read(rel)


def test_stage78_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 78 D1" in api or "STAGE_78_FIDELITY.md" in api
    assert "test_stage78_fidelity_d1.py" in api or "STAGE_78_FIDELITY.md" in api
    assert "Stage 78 P1" in api or "COMMERCIAL_PRICING_MVP.md" in api
    assert "Stage 78 S1" in api or "COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 78 D1" in deploy or "STAGE_78_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 78 D1" in sec or "STAGE_78_FIDELITY.md" in sec
    assert "test_commercial_pricing_p1.py" in sec or "COMMERCIAL_PRICING_MVP.md" in sec
    assert "test_commercial_professional_services_s1.py" in sec or "COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_pricing_p1.py" in launch
    assert "test_commercial_professional_services_s1.py" in launch
    assert "test_stage78_fidelity_d1.py" in launch
    assert "STAGE_78_FIDELITY.md" in launch
    assert "ADR-162" in launch or "ADR_162" in launch or "STAGE_78_PLAN.md" in launch


def test_stage78_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_78_FIDELITY.md" in pr and "test_stage78_fidelity_d1.py" in pr
    assert "Stage 78 D1" in pr and "Stage 78 P1" in pr and "Stage 78 S1" in pr
    assert ("public_pricing_portal_claimed" in pr or "signed_sow_claimed" in pr or "go_live_claimed" in pr or "Remaining" in pr or "packaging" in pr.lower())
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_78_FIDELITY.md" in roadmap and "Stage 78 D1" in roadmap
    assert "ADR_162_STAGE78_OPEN.md" in roadmap and "STAGE_78_PLAN.md" in roadmap
    assert "test_stage78_fidelity_d1.py" in roadmap
