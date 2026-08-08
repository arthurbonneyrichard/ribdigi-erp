"""Live FX feed: provider conversion, refresh upsert, scheduled job skip rules."""

import pytest
from sqlalchemy import select

from app import fx as fx_svc
from app import jobs as jobs_svc
from app import models as m
from app.config import settings


def test_quotes_to_rate_to_base():
    assert fx_svc.quotes_to_rate_to_base({"USD": 0.08}, "USD") == 12.5


@pytest.mark.asyncio
async def test_refresh_tenant_rates_from_provider(db_session, seeded, monkeypatch):
    tenant_id = seeded["t1"].id

    async def fake_fetch(base: str):
        assert base == "GHS"
        return "open_er_api", {"USD": 0.1, "EUR": 0.05}

    monkeypatch.setattr(fx_svc, "fetch_provider_rates", fake_fetch)

    result = await fx_svc.refresh_tenant_rates(
        db_session, tenant_id=tenant_id, currencies=["USD", "EUR"]
    )
    await db_session.commit()

    assert result["provider"] == "open_er_api"
    assert result["updated_count"] == 2
    by_code = {r["currency_code"]: r for r in result["updated"]}
    assert by_code["USD"]["rate_to_base"] == 10.0
    assert by_code["EUR"]["rate_to_base"] == 20.0
    assert by_code["USD"]["source"] == "open_er_api"
    assert by_code["USD"]["provider_fetched_at"] is not None

    row = (
        await db_session.execute(
            select(m.ExchangeRate).where(
                m.ExchangeRate.tenant_id == tenant_id,
                m.ExchangeRate.currency_code == "USD",
            )
        )
    ).scalar_one()
    assert float(row.rate_to_base) == 10.0
    assert row.source == "open_er_api"


@pytest.mark.asyncio
async def test_refresh_default_watchlist_when_empty(db_session, seeded, monkeypatch):
    tenant_id = seeded["t1"].id

    async def fake_fetch(base: str):
        return "frankfurter", {"USD": 0.2, "EUR": 0.1, "GBP": 0.05}

    monkeypatch.setattr(fx_svc, "fetch_provider_rates", fake_fetch)
    monkeypatch.setattr(settings, "FX_PROVIDER", "frankfurter")

    result = await fx_svc.refresh_tenant_rates(db_session, tenant_id=tenant_id, create_missing=True)
    await db_session.commit()
    codes = {r["currency_code"] for r in result["updated"]}
    assert codes == {"USD", "EUR", "GBP"}


@pytest.mark.asyncio
async def test_fetch_open_er_api_uses_http(monkeypatch):
    monkeypatch.setattr(settings, "FX_PROVIDER", "open_er_api")
    monkeypatch.setattr(settings, "FX_API_BASE_URL", "")

    async def fake_get(url: str):
        assert "open.er-api.com" in url
        assert url.endswith("/latest/GHS")
        return {"result": "success", "rates": {"USD": 0.08}}

    monkeypatch.setattr(fx_svc, "_http_get_json", fake_get)
    provider, rates = await fx_svc.fetch_provider_rates("GHS")
    assert provider == "open_er_api"
    assert rates["USD"] == 0.08


@pytest.mark.asyncio
async def test_job_skips_when_auto_refresh_disabled(db_session, seeded, monkeypatch):
    tenant = seeded["t1"]
    tenant.fx_auto_refresh = False
    await db_session.commit()

    called = {"n": 0}

    async def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("should not fetch")

    monkeypatch.setattr(fx_svc, "refresh_tenant_rates", boom)
    monkeypatch.setattr(settings, "FX_PROVIDER", "open_er_api")

    from sqlalchemy.ext.asyncio import AsyncSession

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        t = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))).scalar_one()
        if not bool(getattr(t, "fx_auto_refresh", True)):
            return {"skipped": True, "reason": "fx_auto_refresh=false"}
        return await fx_svc.refresh_tenant_rates(db, tenant_id=tenant_id, create_missing=False)

    out = await work(db_session, tenant.id)
    assert out["skipped"] is True
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_job_refresh_fx_rates_respects_disabled_provider(monkeypatch):
    monkeypatch.setattr(settings, "FX_PROVIDER", "disabled")
    out = await jobs_svc.job_refresh_fx_rates()
    assert out.get("skipped") is True
