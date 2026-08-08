"""Expense receipt attachment API tests."""

import io

import pytest
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_expense_attachment_upload_download_delete(client, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Supplies",
            "amount": 25,
            "description": "Office paper",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    expense_id = created.json()["data"]["id"]
    assert created.json()["data"]["has_attachment"] is False

    upload = await ac.post(
        f"/api/v1/expenses/{expense_id}/attachment",
        headers=headers,
        files={"file": ("receipt.pdf", io.BytesIO(b"%PDF-1.4 receipt"), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    data = upload.json()["data"]
    assert data["has_attachment"] is True
    assert data["uploaded"]["filename"] == "receipt.pdf"

    download = await ac.get(f"/api/v1/expenses/{expense_id}/attachment", headers=headers)
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")

    removed = await ac.delete(f"/api/v1/expenses/{expense_id}/attachment", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["data"]["has_attachment"] is False

    missing = await ac.get(f"/api/v1/expenses/{expense_id}/attachment", headers=headers)
    assert missing.status_code == 404
