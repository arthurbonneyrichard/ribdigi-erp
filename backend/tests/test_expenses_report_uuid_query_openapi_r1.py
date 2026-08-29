"""Expenses report Query category/branch/department/store ∈ UuidIdValue (BR-14.4)."""

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
_PATHS = (
    "/api/v1/reports/expenses/summary",
    "/api/v1/reports/expenses/budget-vs-actual",
)
_KEYS = (
    ("category_id", "cat_001"),
    ("branch_id", "branch_001"),
    ("department_id", "dept_001"),
    ("store_id", "store_001"),
)


def test_expenses_report_uuid_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_expenses_report_uuid_query_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Expenses report UUID Query OpenAPI" in agents
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report financial store filter"' in reports
    assert 'aria-label="Report department filter"' in reports


@pytest.mark.asyncio
async def test_expenses_report_uuid_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in _PATHS:
        for key, token in _KEYS:
            for bad in ("", "!!!", "http://evil", "not-a-uuid", token):
                resp = await ac.get(f"{path}?{key}={bad}", headers=headers)
                assert resp.status_code == 422, (path, key, bad, resp.text)

            missing = await ac.get(
                f"{path}?{key}={str(uuid4()).upper()}",
                headers=headers,
            )
            assert missing.status_code in (200, 400, 404), missing.text
            assert missing.status_code != 422
