"""OpenAPI honesty tips #633–#638: final aria + response-shape docs."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app import api as api_mod
from app.sales import serialize_invoice
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_final_aria_and_response_shape_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Platform staff change role aria OpenAPI",
        "PO amend unit aria OpenAPI",
        "Response envelope honesty OpenAPI",
        "List pagination honesty OpenAPI",
        "Money JSON number honesty OpenAPI",
        "Error envelope honesty OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "X-Request-ID" in docs
    assert "unpaginated" in docs
    assert "JSON **numbers**" in docs
    envelope = docs.split("### 1.2 Response Envelope")[1].split("### 1.3")[0]
    assert '"timestamp"' not in envelope
    assert '"request_id"' not in envelope
    pagination = docs.split("### 1.3 Pagination")[1].split("### 1.4")[0]
    assert "next_cursor" not in pagination
    errors = docs.split("### Error Response Format")[1].split("### Common Error Codes")[0]
    assert "`detail`" in errors
    assert "JSON number" in docs

    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "Change platform staff role for" in staff

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(
        encoding="utf-8"
    )
    assert purchasing.count('aria-label="PO unit"') >= 2

    src = inspect.getsource(api_mod.env)
    assert "timestamp" not in src
    assert "request_id" not in src
    assert "success" in src and "data" in src and "message" in src


def test_money_response_is_json_number_not_string():
    src = inspect.getsource(serialize_invoice)
    assert "money_json(invoice.subtotal)" in src
    assert "money_json(invoice.total_amount)" in src
    assert "float(invoice.subtotal)" not in src
    assert "float(invoice.total_amount)" not in src


@pytest.mark.asyncio
async def test_success_envelope_and_request_id_header(client):
    ac, _seed = client
    headers = await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )
    resp = await ac.get("/api/v1/me", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) >= {"success", "data", "message"}
    assert "timestamp" not in body
    assert "request_id" not in body
    assert resp.headers.get("X-Request-ID")
