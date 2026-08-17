"""Credit FX currency_code Path/body OpenAPI honesty (BR-2.6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CurrencyCodeValue, ExchangeRateRefresh, ExchangeRateUpsert
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_fx_currency_code_literal_schema():
    adapter = TypeAdapter(CurrencyCodeValue)
    assert adapter.validate_python("usd") == "USD"
    assert adapter.validate_python("  Eur ") == "EUR"
    assert adapter.validate_python("GHS") == "GHS"

    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("US")
    with pytest.raises(ValidationError):
        adapter.validate_python("USDD")
    with pytest.raises(ValidationError):
        adapter.validate_python("12A")
    with pytest.raises(ValidationError):
        adapter.validate_python("usd1")

    ok = ExchangeRateUpsert.model_validate(
        {"currency_code": "usd", "rate_to_base": 12.5}
    )
    assert ok.currency_code == "USD"
    with pytest.raises(ValidationError):
        ExchangeRateUpsert.model_validate(
            {"currency_code": "USD", "rate_to_base": 1, "extra": True}
        )
    with pytest.raises(ValidationError):
        ExchangeRateUpsert.model_validate({"currency_code": "", "rate_to_base": 1})

    refresh = ExchangeRateRefresh.model_validate({"currencies": [" usd ", "EUR"]})
    assert refresh.currencies == ["USD", "EUR"]
    with pytest.raises(ValidationError):
        ExchangeRateRefresh.model_validate({"currencies": ["US"]})


def test_fx_currency_code_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="FX currency code"' in page
    assert 'aria-label="FX rate to base"' in page
    assert 'aria-label="Save FX rate"' in page
    assert "maxLength={3}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "FX currency_code OpenAPI" in agents
    assert "CurrencyCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CurrencyCodeValue" in docs
    assert "GET /credit/exchange-rates" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_fx_currency_code_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    bad_path = await ac.put(
        "/api/v1/credit/exchange-rates/US",
        headers=headers,
        json={"currency_code": "USD", "rate_to_base": 10},
    )
    assert bad_path.status_code == 422, bad_path.text

    bad_body = await ac.put(
        "/api/v1/credit/exchange-rates/USD",
        headers=headers,
        json={"currency_code": "US", "rate_to_base": 10},
    )
    assert bad_body.status_code == 422, bad_body.text

    blank_body = await ac.put(
        "/api/v1/credit/exchange-rates/USD",
        headers=headers,
        json={"currency_code": "", "rate_to_base": 10},
    )
    assert blank_body.status_code == 422, blank_body.text

    ok = await ac.put(
        "/api/v1/credit/exchange-rates/usd",
        headers=headers,
        json={"currency_code": "usd", "rate_to_base": 15.25},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data.get("currency_code") == "USD"
    assert float(data.get("rate_to_base")) == 15.25

    listed = await ac.get("/api/v1/credit/exchange-rates", headers=headers)
    assert listed.status_code == 200, listed.text
    rates = (listed.json()["data"] or {}).get("rates") or []
    assert any(r.get("currency_code") == "USD" for r in rates)

    del_bad = await ac.delete("/api/v1/credit/exchange-rates/USDD", headers=headers)
    assert del_bad.status_code == 422, del_bad.text
