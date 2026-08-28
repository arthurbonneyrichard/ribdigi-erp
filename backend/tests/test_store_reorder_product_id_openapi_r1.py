"""StoreReorderPolicyUpdate.product_id ∈ UuidIdValue OpenAPI honesty (BR-5.4 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StoreReorderPolicyUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_store_reorder_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = StoreReorderPolicyUpdate.model_validate(
        {"product_id": f"  {_VALID}  ", "reorder_level": 1, "reorder_qty": 2}
    )
    assert ok.product_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        with pytest.raises(ValidationError):
            StoreReorderPolicyUpdate.model_validate(
                {"product_id": bad, "reorder_level": 1, "reorder_qty": 2}
            )


def test_store_reorder_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Store reorder product"' in page
    assert "product_id: reorderProductId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store reorder product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Store reorder product" in docs
    assert "reorder-policy" in docs


@pytest.mark.asyncio
async def test_store_reorder_product_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    stores = await ac.get("/api/v1/stores", headers=headers)
    assert stores.status_code == 200, stores.text
    rows = stores.json().get("data") or []
    if isinstance(rows, dict):
        rows = rows.get("items") or []
    store_id = next((s["id"] for s in rows if s.get("is_active", True)), None)
    if not store_id:
        created = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"code": f"R{uuid4().hex[:6]}".upper(), "name": "Tip396 Store"},
        )
        assert created.status_code == 200, created.text
        store_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.put(
            f"/api/v1/stores/{store_id}/reorder-policy",
            headers=headers,
            json={"product_id": bad, "reorder_level": 1, "reorder_qty": 2},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.put(
        f"/api/v1/stores/{store_id}/reorder-policy",
        headers=headers,
        json={
            "product_id": f"  {str(uuid4()).upper()}  ",
            "reorder_level": 1,
            "reorder_qty": 2,
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
