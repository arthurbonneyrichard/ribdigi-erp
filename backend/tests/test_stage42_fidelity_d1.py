"""Stage 42 D1 — documentation fidelity for Commercial AI Transparency."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage42_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_42_FIDELITY.md")
    assert (
        "AI Transparency" in fidelity
        or "AI Use" in fidelity
        or "provider" in fidelity.lower()
        or "AI" in fidelity
    )
    for name in (
        "test_ai_use_disclosure_a1.py",
        "test_ai_provider_boundary_p1.py",
        "test_stage42_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-089" in fidelity or "ADR_089" in fidelity
    assert "H42x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "LLM" in fidelity
        or "certification" in fidelity.lower()
    )

    plan = _read("docs/STAGE_42_PLAN.md")
    assert "STAGE_42_FIDELITY.md" in plan
    for ws in ("A1", "P1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h42 = [ln for ln in plan.splitlines() if "| **H42x** |" in ln][0]
    assert "PENDING" in h42 or "COMPLETE" in h42
    assert "ADR-089" in plan or "ADR_089" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H42x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage42_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_42_FIDELITY.md" in br
    assert "Stage 42 D1" in br or "test_stage42_fidelity_d1.py" in br
    assert (
        "Stage 42 A1" in br
        or "AI_USE_DISCLOSURE_MVP.md" in br
        or "Stage 42 P1" in br
        or "AI_PROVIDER_BOUNDARY_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_42_FIDELITY.md" in fidelity_tail or "Stage 42 D1" in fidelity_tail

    for rel in (
        "docs/AI_USE_DISCLOSURE_MVP.md",
        "docs/AI_PROVIDER_BOUNDARY_MVP.md",
    ):
        assert _read(rel)


def test_stage42_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 42 D1" in api or "STAGE_42_FIDELITY.md" in api
    assert "test_stage42_fidelity_d1.py" in api or "STAGE_42_FIDELITY.md" in api
    assert (
        "AI_USE_DISCLOSURE_MVP.md" in api
        or "test_ai_use_disclosure_a1.py" in api
        or "Stage 42 A1" in api
    )
    assert (
        "AI_PROVIDER_BOUNDARY_MVP.md" in api
        or "test_ai_provider_boundary_p1.py" in api
        or "Stage 42 P1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 42 D1" in deploy or "STAGE_42_FIDELITY.md" in deploy
    assert (
        "AI_USE_DISCLOSURE_MVP.md" in deploy
        or "Stage 42 A1" in deploy
        or "AI_PROVIDER_BOUNDARY_MVP.md" in deploy
        or "Stage 42 P1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 42 D1" in sec or "STAGE_42_FIDELITY.md" in sec
    assert "test_ai_use_disclosure_a1.py" in sec or "AI_USE_DISCLOSURE_MVP.md" in sec
    assert "test_ai_provider_boundary_p1.py" in sec or "AI_PROVIDER_BOUNDARY_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ai_use_disclosure_a1.py" in launch
    assert "test_ai_provider_boundary_p1.py" in launch
    assert "test_stage42_fidelity_d1.py" in launch
    assert "STAGE_42_FIDELITY.md" in launch
    assert "ADR-089" in launch or "ADR_089" in launch or "STAGE_42_PLAN.md" in launch


def test_stage42_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_42_FIDELITY.md" in pr
    assert "test_stage42_fidelity_d1.py" in pr
    assert "Stage 42 D1" in pr
    assert "Stage 42 A1" in pr
    assert "Stage 42 P1" in pr
    assert (
        "ai_certification_claimed" in pr
        or "external_llm_claimed" in pr
        or "prophet_claimed" in pr
        or "output_pii_scanner_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_42_FIDELITY.md" in roadmap
    assert "Stage 42 D1" in roadmap
    assert "ADR_089_STAGE42_OPEN.md" in roadmap
    assert "STAGE_42_PLAN.md" in roadmap
    assert "test_stage42_fidelity_d1.py" in roadmap
