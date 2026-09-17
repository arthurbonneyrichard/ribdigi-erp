"""POST /jobs/{job_name}/run Path Literal OpenAPI + Jobs console aria-labels."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args, get_origin

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app import jobs as jobs_svc
from app.schemas import JobNameValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _literal_values(annotated) -> set[str]:
    """Unwrap Annotated[Literal[...], ...] to the Literal value set."""
    cur: object = annotated
    for _ in range(6):
        origin = get_origin(cur)
        args = get_args(cur)
        if origin is Literal:
            return set(args)
        if not args:
            break
        cur = args[0]
    raise AssertionError(f"Could not unwrap Literal from {annotated!r}")


def test_job_name_literal_schema_matches_handlers():
    adapter = TypeAdapter(JobNameValue)
    for name in jobs_svc.JOB_HANDLERS:
        assert adapter.validate_python(name) == name
        assert adapter.validate_python(f"  {name.upper()} ") == name

    lit_args = _literal_values(JobNameValue)
    assert lit_args == set(jobs_svc.JOB_HANDLERS.keys()), (
        f"JobNameValue {sorted(lit_args)} != JOB_HANDLERS {sorted(jobs_svc.JOB_HANDLERS)}"
    )

    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("not_a_real_job")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_job_name_ui_and_docs():
    page = (ROOT / "frontend/app/jobs/page.tsx").read_text(encoding="utf-8")
    assert "aria-label={`Run sync ${name}`}" in page
    assert "aria-label={`Enqueue ${name}`}" in page
    assert "Run sync" in page
    assert "Enqueue" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Jobs Path job_name OpenAPI" in agents
    assert "JobNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "JobNameValue" in docs
    assert "POST /jobs/{job_name}/run" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_job_name_path_unknown_422_and_run(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    unknown = await ac.post("/api/v1/jobs/not_a_real_job/run", headers=headers, json={})
    assert unknown.status_code == 422, unknown.text

    blankish = await ac.post("/api/v1/jobs/%20/run", headers=headers, json={})
    assert blankish.status_code == 422, blankish.text

    name = "scan_quotation_expiry"
    ran = await ac.post(f"/api/v1/jobs/{name}/run", headers=headers, json={})
    assert ran.status_code == 200, ran.text
    assert ran.json()["data"].get("job") == name
