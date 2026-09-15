"""GET /reports/export Query category_id / department_id / warehouse_id ∈ UuidIdValue (BR-14)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)
_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_report_export_uuid_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_report_export_uuid_query_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Report export category_id Query OpenAPI" in agents
    assert "Report export department_id Query OpenAPI" in agents
    assert "Report export warehouse_id Query OpenAPI" in agents
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "params.set('department_id', departmentTrim)" in reports


@pytest.mark.asyncio
async def test_report_export_uuid_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    base = "/api/v1/reports/export?report_type=profit_loss&format=csv"
    for key, bad_token in (
        ("category_id", "cat_001"),
        ("department_id", "dept_001"),
        ("warehouse_id", "wh_001"),
    ):
        for bad in ("", "!!!", "http://evil", "not-a-uuid", bad_token):
            resp = await ac.get(f"{base}&{key}={bad}", headers=headers)
            assert resp.status_code == 422, (key, bad, resp.text)

        missing = await ac.get(
            f"{base}&{key}={str(uuid4()).upper()}",
            headers=headers,
        )
        # Valid UUID shape: export may succeed (ignore unknown filter) or 404/400.
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422
