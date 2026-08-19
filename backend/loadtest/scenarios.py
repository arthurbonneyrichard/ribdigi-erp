"""Named HTTP scenarios for baseline load tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

ScenarioFn = Callable[[httpx.AsyncClient, dict[str, Any]], Awaitable[None]]


@dataclass
class Scenario:
    name: str
    requires_auth: bool = False
    run: ScenarioFn | None = None
    tags: list[str] = field(default_factory=list)


async def scenario_health(client: httpx.AsyncClient, _ctx: dict[str, Any]) -> None:
    r = await client.get("/api/v1/health")
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError("health success=false")


async def scenario_health_ready(client: httpx.AsyncClient, _ctx: dict[str, Any]) -> None:
    r = await client.get("/api/v1/health/ready")
    if r.status_code >= 500:
        r.raise_for_status()
    # degraded (200) is acceptable under load; hard error is not


async def scenario_login(client: httpx.AsyncClient, ctx: dict[str, Any]) -> None:
    email = ctx.get("email") or ""
    password = ctx.get("password") or ""
    tenant = ctx.get("tenant_slug") or ""
    if not (email and password and tenant):
        raise RuntimeError("login scenario requires email, password, tenant_slug")
    payload: dict[str, Any] = {
        "email": email,
        "password": password,
        "tenant_id": tenant,
    }
    if ctx.get("totp_code"):
        payload["totp_code"] = ctx["totp_code"]
    r = await client.post("/api/v1/auth/login", json=payload)
    r.raise_for_status()
    data = r.json().get("data") or {}
    if data.get("requires_2fa") and not ctx.get("totp_code"):
        raise RuntimeError("login requires TOTP (set LOADTEST_TOTP)")
    token = data.get("access_token")
    if not token:
        raise RuntimeError("login missing access_token")
    tenant_id = (data.get("user") or {}).get("tenant_id") or tenant
    ctx["access_token"] = token
    ctx["tenant_id"] = tenant_id
    ctx["auth_headers"] = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


async def scenario_products(client: httpx.AsyncClient, ctx: dict[str, Any]) -> None:
    headers = ctx.get("auth_headers") or {}
    if not headers:
        await scenario_login(client, ctx)
        headers = ctx["auth_headers"]
    r = await client.get("/api/v1/products", headers=headers, params={"limit": 50})
    r.raise_for_status()


async def scenario_dashboard(client: httpx.AsyncClient, ctx: dict[str, Any]) -> None:
    headers = ctx.get("auth_headers") or {}
    if not headers:
        await scenario_login(client, ctx)
        headers = ctx["auth_headers"]
    # Executive dashboard summary (exists as /dashboard)
    r = await client.get("/api/v1/dashboard", headers=headers)
    r.raise_for_status()


SCENARIOS: dict[str, Scenario] = {
    "health": Scenario(name="health", run=scenario_health, tags=["public"]),
    "health_ready": Scenario(name="health_ready", run=scenario_health_ready, tags=["public"]),
    "login": Scenario(name="login", requires_auth=True, run=scenario_login, tags=["auth"]),
    "products": Scenario(
        name="products", requires_auth=True, run=scenario_products, tags=["auth", "catalog"]
    ),
    "dashboard": Scenario(
        name="dashboard", requires_auth=True, run=scenario_dashboard, tags=["auth", "reports"]
    ),
}


def resolve_scenarios(names: str | list[str]) -> list[Scenario]:
    if isinstance(names, str):
        keys = [x.strip() for x in names.split(",") if x.strip()]
    else:
        keys = list(names)
    out: list[Scenario] = []
    for key in keys:
        if key not in SCENARIOS:
            raise ValueError(f"Unknown scenario '{key}'. Known: {', '.join(sorted(SCENARIOS))}")
        out.append(SCENARIOS[key])
    return out
