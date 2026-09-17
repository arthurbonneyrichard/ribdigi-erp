"""Living store-scoped RBAC test matrix (indexed suite + CI marker ``store_scope``).

Documents/enforces: cross-store deny, membership-on soak, cashier fail-closed,
manager union, intentional ALLOWs (logo GET, sessions, notification settings).
Breadth cases index deep modules without re-running the full continuum file.

Honesty: store-scoped RBAC Complete is claimed (flag default OFF) when residual
empty + product-accepted ALLOWs + this matrix + automated/local soak. Do not
claim Offline / 7-day / go-live / paid billing / overall RBAC Completes.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import dashboard_scope as dashboard_scope_svc
from app import models as m
from app import store_memberships as store_memberships_svc
from app.config import Settings
from app.rbac import permissions_for_role
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "ops" / "mvp" / "store-scope-rbac-matrix.json"
DOC = ROOT / "docs" / "STORE_SCOPED_RBAC_TEST_MATRIX.md"
REMAINING = ROOT / "docs" / "STORE_SCOPED_RBAC_COMPLETE_REMAINING.md"
ALLOWS = ROOT / "docs" / "STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md"

pytestmark = pytest.mark.store_scope

REQUIRED_CLASSES = {
    "cross_store_deny",
    "membership_on_soak",
    "cashier_fail_closed",
    "manager_union",
    "intentional_allow",
    "breadth_index",
}

REQUIRED_CASE_IDS = {
    "ss-cross-sales-list-deny",
    "ss-cross-sales-query-deny",
    "ss-mgr-union-flag-on",
    "ss-membership-soak-honesty",
    "ss-cashier-empty-fail-closed",
    "ss-cashier-assigned-foreign-deny",
    "ss-allow-logo-binary-get",
    "ss-allow-own-sessions",
    "ss-allow-notification-settings",
    "ss-breadth-ops-hardening",
    "ss-breadth-adr005-soak",
}


def _matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def _enable_membership_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )
    monkeypatch.setattr(
        "app.dashboard_scope.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )
    monkeypatch.setattr(
        "app.store_memberships.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )


async def _grant_cashier_stores_read(db_session, cashier, company_id: str) -> None:
    perms = dict(permissions_for_role("cashier"))
    perms["stores"] = ["read"]
    user_row = await db_session.get(m.User, cashier.id)
    assert user_row is not None
    user_row.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == cashier.id,
                m.UserCompanyMembership.company_id == company_id,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()


def _assert_scope_denied(response) -> None:
    assert response.status_code == 403, response.text
    detail = response.json().get("detail") or {}
    assert isinstance(detail, dict)
    assert detail.get("code") == "STORE_SCOPE_DENIED"


# ---------------------------------------------------------------------------
# Index / honesty / CI wiring
# ---------------------------------------------------------------------------


def test_matrix_json_structure_and_honesty():
    assert MATRIX.is_file()
    mapping = _matrix()
    assert mapping["id"] == "store-scope-rbac-matrix"
    assert mapping["version"] >= 1
    assert mapping["store_scoped_rbac_complete_claimed"] is True
    assert mapping["adr005_complete_claimed"] is True
    assert mapping["overall_rbac_complete_claimed"] is False
    assert mapping["ci_marker"] == "store_scope"
    assert "test_store_scope_rbac_matrix.py" in mapping["ci_target"]
    assert "store_scope" in (mapping.get("ci_marker_pass") or mapping["ci_target"])
    assert mapping["suite"] == "backend/tests/test_store_scope_rbac_matrix.py"
    assert mapping["doc"] == "docs/STORE_SCOPED_RBAC_TEST_MATRIX.md"
    assert set(mapping["classes"]) == REQUIRED_CLASSES
    cases = mapping["cases"]
    assert len(cases) >= 12
    ids = {c["id"] for c in cases}
    assert REQUIRED_CASE_IDS.issubset(ids)
    living = [c for c in cases if c.get("living")]
    assert len(living) >= 9
    for case in cases:
        assert case["class"] in REQUIRED_CLASSES
        assert case["expected"]
        assert case["evidence_tests"]
        for ref in case["evidence_tests"]:
            path = ROOT / ref.split("::", 1)[0]
            assert path.is_file(), ref
    never = {x.lower() for x in mapping["never_claim_from_matrix_alone"]}
    assert "overall rbac complete" in never
    assert "offline complete" in never
    assert mapping.get("complete_criteria_not_met") == []
    met = mapping.get("complete_criteria_met") or []
    assert any("ALLOW" in x or "allow" in x.lower() for x in met)
    assert any("residual" in x.lower() or "NONE" in x for x in met)


def test_matrix_docs_and_remaining_checklist_aligned():
    assert DOC.is_file()
    doc = DOC.read_text(encoding="utf-8")
    assert "store_scope" in doc
    assert "store-scope-rbac-matrix.json" in doc
    assert "Complete" in doc
    assert "intentional" in doc.lower() or "ALLOW" in doc

    assert REMAINING.is_file()
    remaining = REMAINING.read_text(encoding="utf-8")
    assert "**Complete**" in remaining
    assert "EMPTY" in remaining or "empty" in remaining.lower()
    assert "store-scope-rbac-matrix" in remaining or "Living store-scope test matrix" in remaining
    assert "test_store_scope_rbac_matrix.py" in remaining
    assert ALLOWS.is_file()
    allows = ALLOWS.read_text(encoding="utf-8")
    assert "ACCEPT" in allows
    assert "logo" in allows.lower()


def test_matrix_honesty_payloads_complete_true():
    honesty = store_memberships_svc.honesty_payload()
    assert honesty["adr005_complete_claimed"] is True
    assert honesty["store_scoped_rbac_complete_claimed"] is True
    assert store_memberships_svc.STORE_SCOPED_RBAC_COMPLETE_CLAIMED is True
    mapping = _matrix()
    assert mapping["store_scoped_rbac_complete_claimed"] is True


def test_matrix_ci_marker_wired():
    ini = (ROOT / "backend" / "pytest.ini").read_text(encoding="utf-8")
    assert "store_scope:" in ini

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "store_scope" in ci
    assert "test_store_scope_rbac_matrix.py" in ci
    assert "security or isolation or store_scope" in ci or (
        "security or isolation" in ci and "store_scope" in ci
    )


def test_matrix_flag_defaults_off():
    cfg = Settings(APP_ENV="development")
    assert cfg.STORE_MEMBERSHIP_SCOPE_ENABLED is False
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED=false" in example


def test_matrix_breadth_evidence_files_present():
    mapping = _matrix()
    for case in mapping["cases"]:
        if case["class"] != "breadth_index":
            continue
        for ref in case["evidence_tests"]:
            path = ROOT / ref.split("::", 1)[0]
            assert path.is_file(), f"{case['id']}: missing {ref}"


# ---------------------------------------------------------------------------
# Living behavioral cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matrix_cross_store_sales_deny(client, db_session):
    """ss-cross-sales-list-deny + ss-cross-sales-query-deny."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Mgr Main",
        code="MX-MAIN",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Mgr Other",
        code="MX-OTHER",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-MX-MINE",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        store_id=store.id,
        posted_at=datetime.utcnow(),
        created_by=mgr.id,
    )
    theirs = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-MX-THEIRS",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=99,
        tax_amount=0,
        total_amount=99,
        store_id=other.id,
        posted_at=datetime.utcnow(),
        created_by=seed["admin1"].id,
    )
    null_inv = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-MX-NULL",
        customer_id=seed["party1"].id,
        status="draft",
        subtotal=5,
        tax_amount=0,
        total_amount=5,
        store_id=None,
        created_by=seed["admin1"].id,
    )
    db_session.add_all([mine, theirs, null_inv])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/sales/invoices", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["invoice_number"] for row in listed.json()["data"]}
    assert "INV-MX-MINE" in numbers
    assert "INV-MX-THEIRS" not in numbers
    assert "INV-MX-NULL" not in numbers

    _assert_scope_denied(await ac.get(f"/api/v1/sales/invoices/{theirs.id}", headers=headers))
    _assert_scope_denied(await ac.get(f"/api/v1/sales/invoices/{null_inv.id}", headers=headers))
    ok = await ac.get(f"/api/v1/sales/invoices/{mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    cross = await ac.get(
        "/api/v1/sales/invoices",
        headers=headers,
        params={"store_id": other.id},
    )
    _assert_scope_denied(cross)


@pytest.mark.asyncio
async def test_matrix_manager_union_flag_on(client, db_session, monkeypatch):
    """ss-mgr-union-flag-on."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    managed_store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Union Managed",
        code="MX-UN-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    membership_only = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Union Mem",
        code="MX-UN-MEM",
        manager_id=None,
        is_active=True,
    )
    foreign = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Union Foreign",
        code="MX-UN-X",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([managed_store, membership_only, foreign])
    await db_session.flush()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=tid,
            company_id=cid,
            user_id=mgr.id,
            store_id=membership_only.id,
            is_active=True,
        )
    )
    await db_session.commit()

    claims = {
        "sub": mgr.id,
        "tenant_id": tid,
        "role": "store_manager",
        "company_id": cid,
    }
    managed = await dashboard_scope_svc.managed_store_ids(db_session, claims)
    assert managed is not None
    assert set(managed) >= {managed_store.id, membership_only.id}
    assert foreign.id not in managed

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert managed_store.id in ids
    assert membership_only.id in ids
    assert foreign.id not in ids


@pytest.mark.asyncio
async def test_matrix_membership_soak_honesty(client, monkeypatch):
    """ss-membership-soak-honesty."""
    _enable_membership_scope(monkeypatch)
    honesty = store_memberships_svc.honesty_payload()
    assert honesty["adr005_complete_claimed"] is True
    assert honesty["store_scoped_rbac_complete_claimed"] is True
    assert honesty["store_membership_scope_enabled"] is True
    assert honesty["cashier_membership_fail_closed"] is True
    assert "user_store_memberships" in honesty["operational_scope"]

    # Flag default OFF remains the production/example posture.
    cfg = Settings(APP_ENV="development")
    assert cfg.STORE_MEMBERSHIP_SCOPE_ENABLED is False

    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me/store-memberships", headers=headers)
    assert me.status_code == 200, me.text
    payload = me.json()["data"]
    assert payload["adr005_complete_claimed"] is True
    assert payload["store_scoped_rbac_complete_claimed"] is True


@pytest.mark.asyncio
async def test_matrix_cashier_empty_fail_closed(client, db_session, monkeypatch):
    """ss-cashier-empty-fail-closed."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    orphan = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Cash Orphan",
        code="MX-CASH-ORPH",
        manager_id=None,
        is_active=True,
    )
    db_session.add(orphan)
    await db_session.commit()
    await _grant_cashier_stores_read(db_session, cashier, cid)

    claims = {
        "sub": cashier.id,
        "tenant_id": tid,
        "role": "cashier",
        "company_id": cid,
    }
    assert await dashboard_scope_svc.managed_store_ids(db_session, claims) is None
    assert await dashboard_scope_svc.store_visibility_ids(db_session, claims) == []

    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"] == []

    denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": orphan.id, "opening_cash": 10},
    )
    _assert_scope_denied(denied)


@pytest.mark.asyncio
async def test_matrix_cashier_assigned_foreign_deny(client, db_session, monkeypatch):
    """ss-cashier-assigned-foreign-deny."""
    _enable_membership_scope(monkeypatch)
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cashier = seed["u1"]

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Cash Mine",
        code="MX-CASH-MINE",
        manager_id=None,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Matrix Cash Other",
        code="MX-CASH-OTHER",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=tid,
            company_id=cid,
            user_id=cashier.id,
            store_id=mine.id,
            is_active=True,
        )
    )
    await db_session.commit()
    await _grant_cashier_stores_read(db_session, cashier, cid)

    claims = {
        "sub": cashier.id,
        "tenant_id": tid,
        "role": "cashier",
        "company_id": cid,
    }
    visible = await dashboard_scope_svc.store_visibility_ids(db_session, claims)
    assert set(visible or []) == {mine.id}

    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()["data"]} == {mine.id}

    ok = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": mine.id, "opening_cash": 15},
    )
    assert ok.status_code == 200, ok.text
    await ac.post(
        f"/api/v1/pos/sessions/{ok.json()['data']['session_id']}/close",
        headers=headers,
        json={"actual_cash": 15},
    )

    denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": other.id, "opening_cash": 10},
    )
    _assert_scope_denied(denied)


@pytest.mark.asyncio
async def test_matrix_intentional_allow_logo_binary_get(
    client, db_session, tmp_path, monkeypatch
):
    """ss-allow-logo-binary-get."""
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, seed = client
    cid = seed["c1"].id
    png = b"\x89PNG\r\n\x1a\n" + b"matrix-logo-chrome"

    admin_headers = await auth_headers(
        ac,
        email="super@alpha.example.com",
        tenant_slug="alpha",
        totp_code=pyotp.TOTP(seed["super_totp_secret"]).now(),
    )
    admin_headers["X-Workspace-Kind"] = "tenant"

    ok_co = await ac.post(
        f"/api/v1/companies/{cid}/logo",
        headers=admin_headers,
        files={"file": ("co.png", io.BytesIO(png), "image/png")},
    )
    assert ok_co.status_code == 200, ok_co.text

    ok_tenant = await ac.post(
        "/api/v1/tenants/me/logo",
        headers=admin_headers,
        files={"file": ("tenant.png", io.BytesIO(png), "image/png")},
    )
    assert ok_tenant.status_code == 200, ok_tenant.text

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    mgr_co = await ac.get(f"/api/v1/companies/{cid}/logo", headers=headers)
    assert mgr_co.status_code == 200, mgr_co.text
    assert mgr_co.content.startswith(b"\x89PNG")

    mgr_tenant = await ac.get("/api/v1/tenants/me/logo", headers=headers)
    assert mgr_tenant.status_code == 200, mgr_tenant.text
    assert mgr_tenant.content.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_matrix_intentional_allow_sessions_and_notification_settings(
    client, db_session
):
    """ss-allow-own-sessions + ss-allow-notification-settings."""
    ac, seed = client
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    login2 = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login2.status_code == 200, login2.text

    sessions = await ac.get("/api/v1/auth/sessions?status=active", headers=headers)
    assert sessions.status_code == 200, sessions.text
    rows = sessions.json()["data"]
    assert len(rows) >= 1
    for row in rows:
        assert "user_email" not in row
        assert "user_id" not in row

    exported = await ac.get("/api/v1/auth/sessions/export?status=active", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")

    denied_tenant = await ac.get("/api/v1/auth/tenant-sessions", headers=headers)
    _assert_scope_denied(denied_tenant)

    prefs = await ac.get("/api/v1/notifications/settings", headers=headers)
    assert prefs.status_code == 200, prefs.text
    assert isinstance(prefs.json()["data"], dict)

    patched = await ac.patch(
        "/api/v1/notifications/settings",
        headers=headers,
        json={
            "preferences": {
                "system": {"dashboard": True, "email": False, "sms": False}
            }
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["system"]["email"] is False

    prefs_export = await ac.get(
        "/api/v1/notifications/settings/export", headers=headers
    )
    assert prefs_export.status_code == 200, prefs_export.text

    row = (
        await db_session.execute(
            select(m.NotificationPreference).where(
                m.NotificationPreference.tenant_id == seed["t1"].id,
                m.NotificationPreference.user_id == mgr.id,
            )
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.preferences.get("system", {}).get("email") is False
