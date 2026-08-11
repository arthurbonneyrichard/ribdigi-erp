"""Stage 29 D1 — documentation fidelity for Operator Hardening & Cutover."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage29_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_29_FIDELITY.md")
    assert "Hardening" in fidelity or "Cutover" in fidelity or "Pen-Test" in fidelity
    assert "test_pentest_pack_v1.py" in fidelity
    assert "test_pgbouncer_soak_b2.py" in fidelity
    assert "test_tls_ingress_t1.py" in fidelity
    assert "test_cutover_pack_x1.py" in fidelity
    assert "test_stage29_fidelity_d1.py" in fidelity
    assert "ADR-063" in fidelity or "ADR_063" in fidelity
    assert "H29x" in fidelity
    assert (
        "vendor" in fidelity.lower()
        or "§7" in fidelity
        or "ACME" in fidelity
        or "soak" in fidelity.lower()
        or "execution" in fidelity.lower()
    )

    plan = _read("docs/STAGE_29_PLAN.md")
    assert "STAGE_29_FIDELITY.md" in plan
    for ws in ("V1", "B2", "T1", "X1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h29 = [ln for ln in plan.splitlines() if "| **H29x** |" in ln][0]
    assert "PENDING" in h29 or "COMPLETE" in h29
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H29x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage29_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_29_FIDELITY.md" in br
    assert "Stage 29 D1" in br or "test_stage29_fidelity_d1.py" in br
    assert (
        "Stage 29 V1" in br
        or "PENTEST_PACK_MVP.md" in br
        or "Stage 29 X1" in br
        or "CUTOVER_PACK_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    # Fidelity sync paragraph after BR-16.3 cites Stage 29 D1
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_29_FIDELITY.md" in fidelity_tail or "Stage 29 D1" in fidelity_tail

    assert _read("docs/PENTEST_PACK_MVP.md")
    assert _read("docs/PGBOUNCER_SOAK_PACK_MVP.md")
    assert _read("docs/TLS_INGRESS_PACK_MVP.md")
    assert _read("docs/CUTOVER_PACK_MVP.md")


def test_stage29_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 29 D1" in api or "STAGE_29_FIDELITY.md" in api
    assert "test_stage29_fidelity_d1.py" in api or "STAGE_29_FIDELITY.md" in api
    assert "PENTEST_PACK_MVP.md" in api or "test_pentest_pack_v1.py" in api or "Stage 29 V1" in api
    assert (
        "PGBOUNCER_SOAK_PACK_MVP.md" in api
        or "test_pgbouncer_soak_b2.py" in api
        or "Stage 29 B2" in api
    )
    assert "TLS_INGRESS_PACK_MVP.md" in api or "test_tls_ingress_t1.py" in api or "Stage 29 T1" in api
    assert "CUTOVER_PACK_MVP.md" in api or "test_cutover_pack_x1.py" in api or "Stage 29 X1" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 29 D1" in deploy or "STAGE_29_FIDELITY.md" in deploy
    assert "CUTOVER_PACK_MVP.md" in deploy or "Stage 29 X1" in deploy
    assert (
        "TLS_INGRESS_PACK_MVP.md" in deploy
        or "Stage 29 T1" in deploy
        or "PGBOUNCER_SOAK_PACK_MVP.md" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 29 D1" in sec or "STAGE_29_FIDELITY.md" in sec
    assert "test_pentest_pack_v1.py" in sec or "PENTEST_PACK_MVP.md" in sec
    assert "test_pgbouncer_soak_b2.py" in sec or "PGBOUNCER_SOAK_PACK_MVP.md" in sec
    assert "test_tls_ingress_t1.py" in sec or "TLS_INGRESS_PACK_MVP.md" in sec
    assert "test_cutover_pack_x1.py" in sec or "CUTOVER_PACK_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_pentest_pack_v1.py" in launch
    assert "test_pgbouncer_soak_b2.py" in launch
    assert "test_tls_ingress_t1.py" in launch
    assert "test_cutover_pack_x1.py" in launch
    assert "test_stage29_fidelity_d1.py" in launch
    assert "STAGE_29_FIDELITY.md" in launch


def test_stage29_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_29_FIDELITY.md" in pr
    assert "test_stage29_fidelity_d1.py" in pr
    assert "Stage 29 D1" in pr
    assert "Stage 29 V1" in pr
    assert "Stage 29 B2" in pr
    assert "Stage 29 T1" in pr
    assert "Stage 29 X1" in pr
    assert (
        "vendor" in pr.lower()
        or "cutover" in pr.lower()
        or "§7" in pr
        or "soak" in pr.lower()
        or "ACME" in pr
        or "execution" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_29_FIDELITY.md" in roadmap
    assert "Stage 29 D1" in roadmap
    assert "ADR_063_STAGE29_OPEN.md" in roadmap
    assert "STAGE_29_PLAN.md" in roadmap
    assert "test_stage29_fidelity_d1.py" in roadmap
