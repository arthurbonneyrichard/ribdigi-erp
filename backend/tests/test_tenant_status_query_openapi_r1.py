"""GET /tenants status Query OpenAPI Literal (platform list filter)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import TenantStatusFilterValue
from app.tenants import VALID_STATUSES
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_status_filter_literal_covers_valid():
    lit = TenantStatusFilterValue.__args__[0]
    assert set(lit.__args__) == set(VALID_STATUSES)


def test_tenant_status_filter_literal_schema():
    adapter = TypeAdapter(TenantStatusFilterValue)
    assert adapter.validate_python("active") == "active"
    assert adapter.validate_python("  Trial ") == "trial"
    assert adapter.validate_python("SUSPENDED") == "suspended"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("deleted")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_tenant_status_filter_ui_and_docs():
    page = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tenant status"' in page
    assert "Tenant status trial" in page or 'aria-label={`Tenant status ${s}`}' in page or "Tenant status ${s}" in page
    assert "plat-filters" in page
    assert "'active'" in page and "'suspended'" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Platform tenant status Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "GET /tenants?status=" in docs
    assert "422" in docs
    assert "Tenant status" in docs


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_tenant_status_filter_api_blank_invalid_422(client):
    ac, seed = client
    headers = await _super(ac, seed)

    blank = await ac.get("/api/v1/tenants?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/tenants?status=deleted", headers=headers)
    assert bad.status_code == 422, bad.text

    ok = await ac.get("/api/v1/tenants?status=Trial", headers=headers)
    assert ok.status_code == 200, ok.text
    rows = ok.json()["data"]
    assert isinstance(rows, list)
    assert all(t["status"] == "trial" for t in rows)

    omit = await ac.get("/api/v1/tenants", headers=headers)
    assert omit.status_code == 200, omit.text
    assert isinstance(omit.json()["data"], list)
