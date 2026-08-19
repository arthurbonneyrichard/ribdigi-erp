"""Stage 39 D1 — documentation fidelity for Commercial Contract Evidence."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage39_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_39_FIDELITY.md")
    assert (
        "Contract Evidence" in fidelity
        or "DPA" in fidelity
        or "MSA" in fidelity
        or "subprocessor" in fidelity.lower()
    )
    for name in (
        "test_dpa_subprocessor_p1.py",
        "test_msa_addendum_a1.py",
        "test_stage39_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-083" in fidelity or "ADR_083" in fidelity
    assert "H39x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "DPA" in fidelity
        or "MSA" in fidelity
    )

    plan = _read("docs/STAGE_39_PLAN.md")
    assert "STAGE_39_FIDELITY.md" in plan
    for ws in ("P1", "A1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h39 = [ln for ln in plan.splitlines() if "| **H39x** |" in ln][0]
    assert "PENDING" in h39 or "COMPLETE" in h39
    assert "ADR-083" in plan or "ADR_083" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H39x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage39_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_39_FIDELITY.md" in br
    assert "Stage 39 D1" in br or "test_stage39_fidelity_d1.py" in br
    assert (
        "Stage 39 P1" in br
        or "DPA_SUBPROCESSOR_MVP.md" in br
        or "Stage 39 A1" in br
        or "MSA_ADDENDUM_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_39_FIDELITY.md" in fidelity_tail or "Stage 39 D1" in fidelity_tail

    for rel in (
        "docs/DPA_SUBPROCESSOR_MVP.md",
        "docs/MSA_ADDENDUM_MVP.md",
    ):
        assert _read(rel)


def test_stage39_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 39 D1" in api or "STAGE_39_FIDELITY.md" in api
    assert "test_stage39_fidelity_d1.py" in api or "STAGE_39_FIDELITY.md" in api
    assert (
        "DPA_SUBPROCESSOR_MVP.md" in api
        or "test_dpa_subprocessor_p1.py" in api
        or "Stage 39 P1" in api
    )
    assert (
        "MSA_ADDENDUM_MVP.md" in api
        or "test_msa_addendum_a1.py" in api
        or "Stage 39 A1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 39 D1" in deploy or "STAGE_39_FIDELITY.md" in deploy
    assert (
        "DPA_SUBPROCESSOR_MVP.md" in deploy
        or "Stage 39 P1" in deploy
        or "MSA_ADDENDUM_MVP.md" in deploy
        or "Stage 39 A1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 39 D1" in sec or "STAGE_39_FIDELITY.md" in sec
    assert "test_dpa_subprocessor_p1.py" in sec or "DPA_SUBPROCESSOR_MVP.md" in sec
    assert "test_msa_addendum_a1.py" in sec or "MSA_ADDENDUM_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_dpa_subprocessor_p1.py" in launch
    assert "test_msa_addendum_a1.py" in launch
    assert "test_stage39_fidelity_d1.py" in launch
    assert "STAGE_39_FIDELITY.md" in launch
    assert "ADR-083" in launch or "ADR_083" in launch or "STAGE_39_PLAN.md" in launch


def test_stage39_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_39_FIDELITY.md" in pr
    assert "test_stage39_fidelity_d1.py" in pr
    assert "Stage 39 D1" in pr
    assert "Stage 39 P1" in pr
    assert "Stage 39 A1" in pr
    assert (
        "dpa_signed_claimed" in pr
        or "msa_signed_claimed" in pr
        or "legal_counsel_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_39_FIDELITY.md" in roadmap
    assert "Stage 39 D1" in roadmap
    assert "ADR_083_STAGE39_OPEN.md" in roadmap
    assert "STAGE_39_PLAN.md" in roadmap
    assert "test_stage39_fidelity_d1.py" in roadmap
