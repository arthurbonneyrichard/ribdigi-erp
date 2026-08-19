"""Stage 24 D1 — documentation fidelity for commerce & ops gates (BR-20.4 + readiness)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage24_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_24_FIDELITY.md")
    assert "BR-20.4" in fidelity or "document numbering" in fidelity.lower()
    assert "test_document_numbering_n1.py" in fidelity
    assert "test_commerce_gate_closure_g1.py" in fidelity
    assert "test_ops_ai_gate_closure_o1.py" in fidelity
    assert "test_stage24_fidelity_d1.py" in fidelity
    assert "ADR-053" in fidelity or "ADR_053" in fidelity
    assert "DOC_KEYS" in fidelity or "sales_order" in fidelity
    assert "WAL" in fidelity or "PITR" in fidelity or "PgBouncer" in fidelity
    assert "H24x" in fidelity

    plan = _read("docs/STAGE_24_PLAN.md")
    assert "STAGE_24_FIDELITY.md" in plan
    for ws in ("N1", "G1", "O1", "D1", "H24x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    assert "ADR-053" in plan or "ADR_053" in plan
    assert "ADR-054" in plan or "ADR_054" in plan
    assert "Closed" in plan or "exit met" in plan.lower()
    assert "ADR-054" in fidelity or "ADR_054" in fidelity or "exit met" in fidelity.lower()


def test_stage24_br_20_4_and_gate_cites():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 24 N1" in br
    assert "Stage 24 D1" in br
    assert "STAGE_24_FIDELITY.md" in br
    s204 = br.split("#### BR-20.4 Numbering & Templates")[1].split("### 4.21")[0]
    assert "[x] Configure invoice numbering prefix and series" in s204
    assert "[x] Configure PO, GRN, quotation numbering" in s204
    assert "sales_order" in s204
    assert "sales_credit_note" in s204 or "credit note" in s204.lower()
    assert "test_document_numbering_n1.py" in s204


def test_stage24_api_user_manual_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 24 D1" in api or "STAGE_24_FIDELITY.md" in api
    assert "test_stage24_fidelity_d1.py" in api or "STAGE_24_FIDELITY.md" in api
    assert "document_numbering" in api
    assert "test_document_numbering_n1.py" in api

    manual = _read("docs/USER_MANUAL.md")
    assert "Stage 24" in manual or "STAGE_24_FIDELITY" in manual
    assert "numbering" in manual.lower()
    assert "STAGE_24_FIDELITY" in manual or "Stage 24 D1" in manual

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_document_numbering_n1.py" in launch
    assert "test_commerce_gate_closure_g1.py" in launch
    assert "test_ops_ai_gate_closure_o1.py" in launch
    assert "test_stage24_fidelity_d1.py" in launch
    assert "STAGE_24_FIDELITY.md" in launch


def test_stage24_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_24_FIDELITY.md" in pr
    assert "test_stage24_fidelity_d1.py" in pr
    assert "Stage 24 D1" in pr
    assert "Stage 24 G1" in pr or "test_commerce_gate_closure_g1.py" in pr
    assert "Stage 24 O1" in pr or "test_ops_ai_gate_closure_o1.py" in pr
    assert "- [x] Inventory catalog" in pr
    assert "- [x] Redis/Celery/RabbitMQ used for intended production workloads." in pr
    assert "- [x] AI functions use real tenant data" in pr
    # Monitoring/WAL may be Complete (MVP) after Stage 26 M1/W1.
    assert (
        "- [ ] Point-in-time recovery/WAL strategy complete." in pr
        or (
            "- [x] Point-in-time recovery/WAL strategy complete." in pr
            and "Stage 26 W1" in pr
        )
    )
    assert (
        "- [ ] Monitoring, metrics, logging and alerting complete." in pr
        or (
            "- [x] Monitoring, metrics, logging and alerting complete." in pr
            and "Stage 26 M1" in pr
        )
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_24_FIDELITY.md" in roadmap
    assert "Stage 24 D1" in roadmap
    assert "ADR_053_STAGE24_OPEN.md" in roadmap
    assert "STAGE_24_PLAN.md" in roadmap
