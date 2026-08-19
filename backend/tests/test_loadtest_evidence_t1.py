"""Stage 18 T1: load-test baseline evidence artifact path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport

from app.main import app
from loadtest.config import TARGETS
from loadtest.runner import run_baseline

EVIDENCE_DIR = Path("/opt/cursor/artifacts/loadtest")
EVIDENCE_FILE = EVIDENCE_DIR / "stage18_t1_baseline_smoke.json"
DOC_EVIDENCE_HINT = Path(__file__).resolve().parents[2] / "docs" / "LOAD_TEST_BASELINE.md"


@pytest.mark.asyncio
async def test_loadtest_writes_evidence_artifact(client):
    """CI/harness smoke writes a durable JSON evidence path for Stage 18 T1."""
    _ac, _seed = client
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    report = await run_baseline(
        base_url="http://test",
        scenarios="health",
        concurrency=TARGETS.smoke_concurrency,
        iterations=TARGETS.smoke_iterations,
        transport=ASGITransport(app=app),
        max_error_rate=TARGETS.smoke_max_error_rate,
        max_p95_ms=TARGETS.smoke_p95_ms,
    )
    assert report.passed, report.failures
    payload = report.to_dict()
    payload["stage"] = "18"
    payload["workstream"] = "T1"
    payload["evidence"] = "loadtest_baseline_smoke"
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    assert EVIDENCE_FILE.is_file()
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["scenarios"]["health"]["errors"] == 0
    assert loaded["workstream"] == "T1"


def test_load_baseline_docs_declare_evidence_path():
    text = DOC_EVIDENCE_HINT.read_text(encoding="utf-8")
    assert "Stage 18 T1" in text or "evidence" in text.lower()
    assert "--output" in text
    assert "stage18_t1_baseline_smoke.json" in text or "/opt/cursor/artifacts/loadtest" in text
