"""Path UuidIdValue OpenAPI honesty for party/sales/expense/store/count/session (#453–#464)."""

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

_TITLES = (
    "Customer path customer_id OpenAPI",
    "Supplier path supplier_id OpenAPI",
    "Party contact path contact_id OpenAPI",
    "Customer group path group_id OpenAPI",
    "Sales invoice path invoice_id OpenAPI",
    "Quotation path quotation_id OpenAPI",
    "Sales order path order_id OpenAPI",
    "Return path return_id OpenAPI",
    "Expense path expense_id OpenAPI",
    "Store path store_id OpenAPI",
    "Stock count path count_id OpenAPI",
    "POS session path session_id OpenAPI",
)


def test_path_uuid_id_batch2_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_path_uuid_id_batch2_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in _TITLES:
        assert title in agents, title
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Path `customer_id` ∈ `UuidIdValue`" in docs
    assert "Path `supplier_id` ∈ `UuidIdValue`" in docs
    assert "Path `invoice_id` ∈ `UuidIdValue`" in docs
    assert "Path `expense_id` ∈ `UuidIdValue`" in docs
    assert "Path `session_id` ∈ `UuidIdValue`" in docs


@pytest.mark.asyncio
async def test_path_uuid_id_batch2_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    async def assert_bad(method: str, template: str, **kw):
        for bad in ("not-a-uuid", "!!!", "cust_001"):
            path = template.format(bad=bad)
            resp = await getattr(ac, method)(path, headers=headers, **kw)
            assert resp.status_code == 422, (method, path, resp.text)

        missing = template.format(bad=str(uuid4()))
        resp = await getattr(ac, method)(missing, headers=headers, **kw)
        assert resp.status_code in (200, 400, 404), (method, missing, resp.text)
        assert resp.status_code != 422

    await assert_bad("get", "/api/v1/customers/{bad}")
    await assert_bad("get", "/api/v1/suppliers/{bad}")
    await assert_bad("get", "/api/v1/sales/invoices/{bad}")
    await assert_bad("get", "/api/v1/sales/quotations/{bad}")
    await assert_bad("get", "/api/v1/sales/orders/{bad}")
    await assert_bad("get", "/api/v1/sales/returns/{bad}")
    await assert_bad("get", "/api/v1/expenses/{bad}")
    await assert_bad("get", "/api/v1/stores/{bad}")
    await assert_bad("get", "/api/v1/inventory/stock-counts/{bad}")
    await assert_bad("get", "/api/v1/pos/sessions/{bad}/report")
    await assert_bad("patch", "/api/v1/customers/groups/{bad}", json={"name": "X"})

    # Nested contact path
    cust = str(uuid4())
    for bad in ("not-a-uuid", "!!!", "contact_001"):
        resp = await ac.patch(
            f"/api/v1/customers/{cust}/contacts/{bad}",
            headers=headers,
            json={"name": "X"},
        )
        # customer_id valid shape; contact_id invalid → 422
        assert resp.status_code == 422, resp.text

    # Purchase return path
    for bad in ("not-a-uuid", "!!!", "ret_001"):
        resp = await ac.get(f"/api/v1/purchasing/returns/{bad}", headers=headers)
        assert resp.status_code == 422, resp.text
