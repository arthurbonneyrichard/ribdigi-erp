"""Outbound HTTP guard: tenant-supplied URLs (webhooks, bank feeds, shop connectors) must reach the public internet.

The URL validators reject private hosts by name. This also resolves the name when the request is sent,
so a public-looking hostname that points at a private address (or is rebound to one) is refused too.
Outside production, localhost stays allowed for local development and tests.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

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
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Outbound URL host does not resolve") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise HTTPException(status_code=400, detail="Outbound URL must not target a private or local address")
