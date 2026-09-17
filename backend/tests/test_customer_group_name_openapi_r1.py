"""CustomerGroupCreate / CustomerGroupUpdate.name OpenAPI honesty (BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import CustomerGroupCreate, CustomerGroupUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_customer_group_name_schema():
    ok = CustomerGroupCreate.model_validate({"name": "  Wholesale  "})
    assert ok.name == "Wholesale"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            CustomerGroupCreate.model_validate({"name": bad})

    patch_omit = CustomerGroupUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = CustomerGroupUpdate.model_validate({"name": " Renamed Group "})
    assert patch_ok.name == "Renamed Group"
    with pytest.raises(ValidationError):
        CustomerGroupUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        CustomerGroupUpdate.model_validate({"name": "  "})


def test_customer_group_name_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer group name"' in sales
    assert "newGroupName.trim()" in sales
    assert 'aria-label="Add group"' in sales
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Customer group name OpenAPI" in agents
    assert "CustomerGroupNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CustomerGroupNameValue" in docs
    assert "Customer group name" in docs


@pytest.mark.asyncio
async def test_customer_group_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/customers/groups",
            headers=headers,
            json={"name": bad, "discount_percent": 0},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": f"  Tip134 Group {suffix}  ", "discount_percent": 5},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip134 Group {suffix}"
    group_id = ok.json()["data"]["id"]

    omit = await ac.patch(
        f"/api/v1/customers/groups/{group_id}",
        headers=headers,
        json={"discount_percent": 6},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["name"] == f"Tip134 Group {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/customers/groups/{group_id}",
            headers=headers,
            json={"name": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/customers/groups/{group_id}",
        headers=headers,
        json={"name": f"  Tip134 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == f"Tip134 Renamed {suffix}"
