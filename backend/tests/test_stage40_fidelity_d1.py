"""Stage 40 D1 — documentation fidelity for Commercial Availability & Supply-Chain."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage40_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_40_FIDELITY.md")
    assert (
        "Availability" in fidelity
        or "Supply-Chain" in fidelity
        or "uptime" in fidelity.lower()
        or "SBOM" in fidelity
        or "Status" in fidelity
    )
    for name in (
        "test_status_uptime_u1.py",
        "test_sbom_disclosure_s1.py",
        "test_stage40_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-085" in fidelity or "ADR_085" in fidelity
    assert "H40x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "status" in fidelity.lower()
        or "SBOM" in fidelity
    )

    plan = _read("docs/STAGE_40_PLAN.md")
    assert "STAGE_40_FIDELITY.md" in plan
    for ws in ("U1", "S1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h40 = [ln for ln in plan.splitlines() if "| **H40x** |" in ln][0]
    assert "PENDING" in h40 or "COMPLETE" in h40
    assert "ADR-085" in plan or "ADR_085" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H40x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage40_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_40_FIDELITY.md" in br
    assert "Stage 40 D1" in br or "test_stage40_fidelity_d1.py" in br
    assert (
        "Stage 40 U1" in br
        or "STATUS_UPTIME_MVP.md" in br
        or "Stage 40 S1" in br
        or "SBOM_DISCLOSURE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_40_FIDELITY.md" in fidelity_tail or "Stage 40 D1" in fidelity_tail

    for rel in (
        "docs/STATUS_UPTIME_MVP.md",
        "docs/SBOM_DISCLOSURE_MVP.md",
    ):
        assert _read(rel)


def test_stage40_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 40 D1" in api or "STAGE_40_FIDELITY.md" in api
    assert "test_stage40_fidelity_d1.py" in api or "STAGE_40_FIDELITY.md" in api
    assert (
        "STATUS_UPTIME_MVP.md" in api
        or "test_status_uptime_u1.py" in api
        or "Stage 40 U1" in api
    )
    assert (
        "SBOM_DISCLOSURE_MVP.md" in api
        or "test_sbom_disclosure_s1.py" in api
        or "Stage 40 S1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 40 D1" in deploy or "STAGE_40_FIDELITY.md" in deploy
    assert (
        "STATUS_UPTIME_MVP.md" in deploy
        or "Stage 40 U1" in deploy
        or "SBOM_DISCLOSURE_MVP.md" in deploy
        or "Stage 40 S1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 40 D1" in sec or "STAGE_40_FIDELITY.md" in sec
    assert "test_status_uptime_u1.py" in sec or "STATUS_UPTIME_MVP.md" in sec
    assert "test_sbom_disclosure_s1.py" in sec or "SBOM_DISCLOSURE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_status_uptime_u1.py" in launch
    assert "test_sbom_disclosure_s1.py" in launch
    assert "test_stage40_fidelity_d1.py" in launch
    assert "STAGE_40_FIDELITY.md" in launch
    assert "ADR-085" in launch or "ADR_085" in launch or "STAGE_40_PLAN.md" in launch


def test_stage40_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_40_FIDELITY.md" in pr
    assert "test_stage40_fidelity_d1.py" in pr
    assert "Stage 40 D1" in pr
    assert "Stage 40 U1" in pr
    assert "Stage 40 S1" in pr
    assert (
        "status_page_live" in pr
        or "uptime_sla_claimed" in pr
        or "sbom_pipeline_live" in pr
        or "cosign_signing_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_40_FIDELITY.md" in roadmap
    assert "Stage 40 D1" in roadmap
    assert "ADR_085_STAGE40_OPEN.md" in roadmap
    assert "STAGE_40_PLAN.md" in roadmap
    assert "test_stage40_fidelity_d1.py" in roadmap
