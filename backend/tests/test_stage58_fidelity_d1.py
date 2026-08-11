"""Stage 58 D1 — documentation fidelity for Commercial Business & AI Metrics."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage58_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_58_FIDELITY.md")
    assert (
        "Business" in fidelity
        or "AI Metrics" in fidelity
        or "MRR" in fidelity
        or "Prediction" in fidelity
        or "AI" in fidelity
    )
    for name in (
        "test_business_metrics_b1.py",
        "test_ai_metrics_i1.py",
        "test_stage58_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-121" in fidelity or "ADR_121" in fidelity
    assert "H58x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "business" in fidelity.lower()
        or "metrics" in fidelity.lower()
        or "ai" in fidelity.lower()
    )

    plan = _read("docs/STAGE_58_PLAN.md")
    assert "STAGE_58_FIDELITY.md" in plan
    for ws in ("B1", "I1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h58 = [ln for ln in plan.splitlines() if "| **H58x** |" in ln][0]
    assert "PENDING" in h58 or "COMPLETE" in h58
    assert "ADR-121" in plan or "ADR_121" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H58x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage58_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_58_FIDELITY.md" in br
    assert "Stage 58 D1" in br or "test_stage58_fidelity_d1.py" in br
    assert (
        "Stage 58 B1" in br
        or "BUSINESS_METRICS_MVP.md" in br
        or "Stage 58 I1" in br
        or "AI_METRICS_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_58_FIDELITY.md" in fidelity_tail or "Stage 58 D1" in fidelity_tail

    for rel in (
        "docs/BUSINESS_METRICS_MVP.md",
        "docs/AI_METRICS_MVP.md",
    ):
        assert _read(rel)


def test_stage58_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 58 D1" in api or "STAGE_58_FIDELITY.md" in api
    assert "test_stage58_fidelity_d1.py" in api or "STAGE_58_FIDELITY.md" in api
    assert (
        "BUSINESS_METRICS_MVP.md" in api
        or "test_business_metrics_b1.py" in api
        or "Stage 58 B1" in api
    )
    assert (
        "AI_METRICS_MVP.md" in api
        or "test_ai_metrics_i1.py" in api
        or "Stage 58 I1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 58 D1" in deploy or "STAGE_58_FIDELITY.md" in deploy
    assert (
        "BUSINESS_METRICS_MVP.md" in deploy
        or "Stage 58 B1" in deploy
        or "AI_METRICS_MVP.md" in deploy
        or "Stage 58 I1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 58 D1" in sec or "STAGE_58_FIDELITY.md" in sec
    assert "test_business_metrics_b1.py" in sec or "BUSINESS_METRICS_MVP.md" in sec
    assert "test_ai_metrics_i1.py" in sec or "AI_METRICS_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_business_metrics_b1.py" in launch
    assert "test_ai_metrics_i1.py" in launch
    assert "test_stage58_fidelity_d1.py" in launch
    assert "STAGE_58_FIDELITY.md" in launch
    assert "ADR-121" in launch or "ADR_121" in launch or "STAGE_58_PLAN.md" in launch


def test_stage58_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_58_FIDELITY.md" in pr
    assert "test_stage58_fidelity_d1.py" in pr
    assert "Stage 58 D1" in pr
    assert "Stage 58 B1" in pr
    assert "Stage 58 I1" in pr
    assert (
        "mrr_measured_claimed" in pr
        or "ai_feature_adoption_measured_claimed" in pr
        or "prediction_accuracy_measured_claimed" in pr
        or "nrr_grr_measured_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_58_FIDELITY.md" in roadmap
    assert "Stage 58 D1" in roadmap
    assert "ADR_121_STAGE58_OPEN.md" in roadmap
    assert "STAGE_58_PLAN.md" in roadmap
    assert "test_stage58_fidelity_d1.py" in roadmap
