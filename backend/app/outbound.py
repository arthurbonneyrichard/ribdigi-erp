"""Outbound HTTP guard: tenant-supplied URLs (webhooks, bank feeds, shop connectors) must reach the public internet.

The URL validators reject private hosts by name. This also resolves the name when the request is sent,
so a public-looking hostname that points at a private address (or is rebound to one) is refused too.
`public_transport()` closes the DNS-rebind gap: the connection is made to the address that was checked,
not to a second lookup. Outside production, localhost stays allowed for local development and tests.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpcore
import httpx
from fastapi import HTTPException

from app.config import settings


def _production() -> bool:
    return (settings.APP_ENV or "").strip().lower() == "production"


async def assert_public_destination(url: str) -> None:
    """Raise 400 when a production request would go to a loopback, private, link-local or reserved address."""
    if not _production():
        return
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        raise HTTPException(status_code=400, detail="Outbound URL must be an absolute http(s) URL")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    await _resolve_public(host, port)


async def _resolve_public(host: str, port: int) -> str:
    """Resolve host and return one address, refusing the lot if any address is not public."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Outbound URL host does not resolve") from exc
    if not infos:
        raise HTTPException(status_code=400, detail="Outbound URL host does not resolve")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise HTTPException(status_code=400, detail="Outbound URL must not target a private or local address")
    return infos[0][4][0]


class _PublicOnlyBackend(httpcore.AsyncNetworkBackend):
    """Connects to the checked address. TLS still verifies the certificate against the original host name."""

    def __init__(self) -> None:
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            ip = await _resolve_public(str(host).strip().lower().rstrip("."), int(port))
        except HTTPException as exc:
            raise httpcore.ConnectError(str(exc.detail)) from exc
        return await self._inner.connect_tcp(
            ip, port, timeout=timeout, local_address=local_address, socket_options=socket_options
        )

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise httpcore.ConnectError("Outbound requests may not use unix sockets")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def public_transport() -> httpx.AsyncHTTPTransport | None:
    """Transport for tenant-supplied URLs. None outside production (default transport)."""
    if not _production():
        return None
    transport = httpx.AsyncHTTPTransport()
    transport._pool._network_backend = _PublicOnlyBackend()
    return transport
