"""Stage 24 O1 — Ops Redis/Celery + AI MVP gate honesty.

Redis/Celery intended workloads and AI provider / tenant-safety / functions
flip to Complete (MVP) where Remaining is deferred-only (PgBouncer, external
LLM, Prophet, PO OCR). Monitoring / WAL / K8s / load remain open or Partial.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READINESS = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
PLAN = (ROOT / "docs" / "STAGE_24_PLAN.md").read_text(encoding="utf-8")


def _section(heading: str) -> str:
    start = READINESS.find(heading)
    assert start >= 0, f"missing heading {heading!r}"
    rest = READINESS[start:]
    nxt = rest.find("\n### ", 1)
    return rest if nxt < 0 else rest[:nxt]


def test_o1_plan_marks_complete() -> None:
    o1_line = [ln for ln in PLAN.splitlines() if "| **O1** |" in ln][0]
    assert "COMPLETE" in o1_line
    assert "test_ops_ai_gate_closure_o1.py" in PLAN
    assert (
        "O1 complete" in PLAN
        or "D1 next" in PLAN
        or "N1–G1–O1 complete" in PLAN
        or "N1–G1–O1–D1 complete" in PLAN
        or "H24x next" in PLAN
        or "Closed" in PLAN
        or "exit met" in PLAN.lower()
        or "ADR-054" in PLAN
    )


def test_redis_celery_mvp_complete() -> None:
    sec = _section("### Reliability & operations")
    assert "- [x] Redis/Celery/RabbitMQ used for intended production workloads." in sec
    assert "Complete (MVP): Redis for distributed API/auth rate limiting" in sec
    assert "Stage 24 O1" in sec
    assert "test_ops_ai_gate_closure_o1.py" in sec
    assert "PgBouncer" in sec
    assert "- [ ] Redis/Celery/RabbitMQ used for intended production workloads." not in sec


def test_ai_gates_mvp_complete() -> None:
    sec = _section("### AI")
    assert "- [x] AI provider configured securely." in sec
    assert "Complete (MVP): optional external LLM" in sec
    assert "- [x] Tenant-safe data access enforced." in sec
    assert "- [x] AI functions use real tenant data and satisfy documented acceptance criteria." in sec
    assert "Complete (MVP) (Phase 4 / BR-21.1–21.10)" in sec or "Complete (MVP)" in sec
    assert "Stage 24 O1" in sec
    assert "Prophet" in sec or "LLM" in sec
    for label in (
        "- [ ] AI provider configured securely.",
        "- [ ] Tenant-safe data access enforced.",
        "- [ ] AI functions use real tenant data and satisfy documented acceptance criteria.",
    ):
        assert label not in sec


def test_monitoring_wal_k8s_load_remain_open() -> None:
    # Stage 26 M1/W1 may close monitoring/WAL; O1 must not fake-close K8s / load.
    assert (
        "- [ ] Point-in-time recovery/WAL strategy complete." in READINESS
        or (
            "- [x] Point-in-time recovery/WAL strategy complete." in READINESS
            and "Stage 26 W1" in READINESS
        )
    )
    assert "- [ ] Kubernetes production deployment reviewed." in READINESS
    assert "- [ ] Load/performance tests meet documented targets." in READINESS
    assert "Partial" in READINESS  # load Partial until closed
