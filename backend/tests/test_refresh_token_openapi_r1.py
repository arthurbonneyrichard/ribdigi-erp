"""RefreshRequest.refresh_token ∈ RefreshTokenValue OpenAPI honesty (BR-19)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import RefreshRequest, RefreshTokenValue

ROOT = Path(__file__).resolve().parents[2]
_token = TypeAdapter(RefreshTokenValue)


def test_refresh_token_value_schema():
    assert _token.validate_python("  Tip258Tok_abc-xyz  ") == "Tip258Tok_abc-xyz"
    assert _token.validate_python("a" * 200) == "a" * 200
    for bad in ("", " ", "!!!", "http://evil", "a@b", "tok en", "a" * 201):
        with pytest.raises(ValidationError):
            _token.validate_python(bad)

    ok = RefreshRequest.model_validate({"refresh_token": "  tip258-ok-token  "})
    assert ok.refresh_token == "tip258-ok-token"
    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        with pytest.raises(ValidationError):
            RefreshRequest.model_validate({"refresh_token": bad})
    with pytest.raises(ValidationError):
        RefreshRequest.model_validate({})


def test_refresh_token_ui_and_docs():
    api_ts = (ROOT / "frontend/lib/api.ts").read_text(encoding="utf-8")
    assert "trimmedRefreshToken" in api_ts
    assert "refresh_token: trimmedRefreshToken" in api_ts
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Refresh token OpenAPI" in agents
    assert "RefreshTokenValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "RefreshTokenValue" in docs
    assert "refreshSession" in docs


@pytest.mark.asyncio
async def test_refresh_token_api_blank_invalid_422(client, seeded):
    ac, seed = client

    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        resp = await ac.post("/api/v1/auth/refresh", json={"refresh_token": bad})
        assert resp.status_code == 422, (bad, resp.text)

    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    refresh = login.json()["data"]["refresh_token"]
    assert refresh

    ok = await ac.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": f"  {refresh}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("access_token")
