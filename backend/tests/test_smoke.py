from app.rbac import has_permission, permissions_for_role
from app.security import validate_password_strength
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
import pytest


def test_root():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "RIBDIGI BUSINESS ERP"


def test_health():
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_rbac_admin_has_all():
    assert has_permission("company_admin", "inventory", "write")
    assert has_permission("company_admin", "audit", "read")


def test_rbac_cashier_denied_inventory_write():
    assert has_permission("cashier", "pos", "write")
    assert not has_permission("cashier", "inventory", "write")
    assert not has_permission("cashier", "accounting", "write")


def test_rbac_inventory_officer():
    assert has_permission("inventory_officer", "purchasing", "write")
    assert not has_permission("inventory_officer", "pos", "write")


def test_password_strength_rejects_weak():
    with pytest.raises(HTTPException):
        validate_password_strength("password")


def test_password_strength_accepts_strong():
    validate_password_strength("SecurePass123!")


def test_role_permission_seed_shape():
    perms = permissions_for_role("accountant")
    assert "accounting" in perms
    assert "write" in perms["accounting"]
