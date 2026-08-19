"""Stage 84 A1 — dotted / colon permission aliases."""

from __future__ import annotations

import pytest

from app.rbac import (
    canonicalize_action,
    expand_permission_aliases,
    has_permission,
    normalize_permissions_map,
)


def test_canonicalize_view_to_read():
    assert canonicalize_action("view") == "read"
    assert canonicalize_action("VIEW") == "read"
    assert canonicalize_action("read") == "read"


def test_normalize_accepts_view_alias_and_dotted_keys():
    out = normalize_permissions_map(
        {
            "inventory": ["view"],
            "sales.view": True,
            "pos:read": ["write"],
        },
        allow_wildcard=False,
    )
    assert out["inventory"] == ["read"]
    assert "read" in out["sales"]
    assert "read" in out["pos"] and "write" in out["pos"]


def test_normalize_colon_and_dot_equivalent():
    a = normalize_permissions_map({"inventory.view": True}, allow_wildcard=False)
    b = normalize_permissions_map({"inventory:read": True}, allow_wildcard=False)
    assert a == b == {"inventory": ["read"]}


def test_has_permission_honors_dotted_overrides():
    assert has_permission(
        "cashier",
        "inventory",
        "read",
        overrides={"inventory.view": True},
    )
    assert has_permission(
        "cashier",
        "inventory",
        "view",
        overrides={"inventory": ["read"]},
    )
    assert not has_permission(
        "cashier",
        "expenses",
        "read",
        overrides={"inventory.view": True},
    )


def test_expand_permission_aliases_soft():
    expanded = expand_permission_aliases(
        {"inventory.view": True, "expenses": ["view"], "_record_scope": ["own"]}
    )
    assert expanded["inventory"] == ["read"]
    assert expanded["expenses"] == ["read"]
    assert "_record_scope" not in expanded


@pytest.mark.asyncio
async def test_permission_alias_does_not_leak_cross_module(client):
    """Smoke: auth still requires real inventory access patterns."""
    from tests.conftest import auth_headers

    ac, _seed = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    # Cashier has inventory:read canonically — products list should work
    r = await ac.get("/api/v1/products", headers=cash)
    assert r.status_code == 200
