"""Tenant-supplied outbound URLs cannot reach loopback or private addresses in production."""
import asyncio

import pytest
from fastapi import HTTPException

from app import outbound
from app.config import settings
from app.schemas import validate_webhook_url_value


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")


def test_http_localhost_rejected_in_production(production):
    for url in ("http://localhost:8000/api/v1/health", "http://127.0.0.1/x", "http://host.docker.internal:6379/"):
        with pytest.raises(ValueError):
            validate_webhook_url_value(url)


def test_http_localhost_still_allowed_outside_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    assert validate_webhook_url_value("http://localhost:9000/hook") == "http://localhost:9000/hook"


@pytest.mark.parametrize("url", ["https://127.0.0.1/hook", "https://10.1.2.3/hook", "https://169.254.169.254/latest", "https://[::1]/x"])
def test_private_destinations_refused_at_send_time(production, url):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(outbound.assert_public_destination(url))
    assert exc.value.status_code == 400


def test_public_name_resolving_to_private_address_refused(production, monkeypatch):
    async def fake_getaddrinfo(self, host, port, **kw):
        return [(None, None, None, "", ("10.0.0.5", port))]

    monkeypatch.setattr(asyncio.AbstractEventLoop, "getaddrinfo", fake_getaddrinfo, raising=False)
    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(HTTPException):
        asyncio.run(outbound.assert_public_destination("https://hooks.example.com/x"))


def test_public_address_allowed(production, monkeypatch):
    async def fake_getaddrinfo(self, host, port, **kw):
        return [(None, None, None, "", ("93.184.216.34", port))]

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", fake_getaddrinfo)
    asyncio.run(outbound.assert_public_destination("https://hooks.example.com/x"))


def test_guard_is_a_no_op_outside_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    asyncio.run(outbound.assert_public_destination("http://127.0.0.1:8000/"))
