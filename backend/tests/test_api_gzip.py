"""API responses are gzip-compressed when the browser asks, so long lists travel fast."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_large_json_is_gzipped_and_small_is_not(client):
    ac, _seed = client
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    big = await ac.get("/api/v1/roles", headers={**h, "Accept-Encoding": "gzip"})
    assert big.status_code == 200 and len(big.content) >= 1024  # httpx decodes gzip transparently
    assert big.headers.get("content-encoding") == "gzip"
    small = await ac.get("/api/v1/health", headers={"Accept-Encoding": "gzip"})
    assert small.status_code == 200 and small.headers.get("content-encoding") is None
    plain = await ac.get("/api/v1/roles", headers={**h, "Accept-Encoding": "identity"})
    assert plain.headers.get("content-encoding") is None and plain.json() == big.json()
