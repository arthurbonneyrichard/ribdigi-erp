"""OpenAPI honesty tips #486–#492: entity/barcode/notes Query + nid/role/tenant_ref Path."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AuditEntityValue,
    BankStatementNotesValue,
    ProductBarcodeValue,
    RoleKeyValue,
    TenantRefValue,
    UuidIdValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_entity = TypeAdapter(AuditEntityValue)
_barcode = TypeAdapter(ProductBarcodeValue)
_notes = TypeAdapter(BankStatementNotesValue)
_role = TypeAdapter(RoleKeyValue)
_tenant = TypeAdapter(TenantRefValue)
_uuid = TypeAdapter(UuidIdValue)


def test_audit_entity_barcode_notes_path_schema():
    assert _entity.validate_python("  Invoice  ") == "invoice"
    for bad in ("", "!!!", "Invoice!", "2fa"):
        with pytest.raises(ValidationError):
            _entity.validate_python(bad)
    assert _entity.validate_python("A") == "a"

    assert _barcode.validate_python("  abcd  ") == "ABCD"
    for bad in ("", "!!!", "ab", "http://evil"):
        with pytest.raises(ValidationError):
            _barcode.validate_python(bad)

    assert _notes.validate_python("  Month end  ") == "Month end"
    for bad in ("", "!!!", "http://evil"):
        with pytest.raises(ValidationError):
            _notes.validate_python(bad)

    assert _role.validate_python("  Cashier  ") == "cashier"
    for bad in ("", "A", "Cashier!"):
        with pytest.raises(ValidationError):
            _role.validate_python(bad)

    assert _tenant.validate_python("  Alpha  ") == "alpha"
    assert _tenant.validate_python(str(uuid4()).upper()).islower()
    for bad in ("", "!!!", "http://evil", "a b"):
        with pytest.raises(ValidationError):
            _tenant.validate_python(bad)


def test_audit_entity_barcode_notes_path_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Audit entity Query OpenAPI",
        "Product lookup barcode Query OpenAPI",
        "POS search barcode Query OpenAPI",
        "Bank statement import notes OpenAPI",
        "Notification path nid OpenAPI",
        "Role path role OpenAPI",
        "Tenant path tenant_ref OpenAPI",
    ):
        assert title in agents, title
    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Audit entity filter"' in audit
    assert "params.set('entity', entityQ)" in audit
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product lookup barcode"' in inv
    acct = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "qs.set('notes', notesTrim)" in acct


@pytest.mark.asyncio
async def test_audit_entity_and_barcode_query_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    for path in ("/api/v1/audit-logs", "/api/v1/audit-logs/export"):
        for bad in ("", "!!!", "Invoice!", "2fa"):
            resp = await ac.get(f"{path}?entity={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)
        ok = await ac.get(f"{path}?entity=invoice", headers=headers)
        assert ok.status_code == 200, ok.text

    for path in ("/api/v1/inventory/products/lookup", "/api/v1/pos/products/search"):
        for bad in ("", "!!!", "ab", "http://evil"):
            resp = await ac.get(f"{path}?barcode={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)
        ok = await ac.get(f"{path}?barcode=ABCD1234", headers=headers)
        assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_import_notes_and_path_honesty_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    # import notes — need multipart file; empty notes query should 422
    files = {"file": ("stmt.csv", b"Date,Amount,Description\n2024-01-01,1.00,x\n", "text/csv")}
    account = str(uuid4())
    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            f"/api/v1/accounting/bank-statements/import?account_id={account}&notes={bad}",
            headers=headers,
            files=files,
        )
        assert resp.status_code == 422, (bad, resp.text)

    for bad in ("not-a-uuid", "!!!", "note_001"):
        resp = await ac.patch(f"/api/v1/notifications/{bad}/read", headers=headers)
        assert resp.status_code == 422, resp.text

    for bad in ("A", "Cashier!", "!!!"):
        resp = await ac.get(f"/api/v1/roles/{bad}", headers=headers)
        assert resp.status_code == 422, resp.text
    ok_role = await ac.get("/api/v1/roles/cashier", headers=headers)
    assert ok_role.status_code in (200, 404), ok_role.text

    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert api.count("tenant_ref: TenantRefValue,") >= 6
