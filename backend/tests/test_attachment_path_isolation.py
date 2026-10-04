"""Exhaustive cross-tenant isolation for document/attachment media paths (BR-1.4).

Covers expense + purchase-invoice attachments (GET/POST/DELETE + OCR), product
legacy/gallery image routes, backup download, and poisoned media keys that
point at another tenant's storage prefix.
"""

from __future__ import annotations

import io
import struct
import zlib

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import storage as storage_svc
from app.backup import create_backup
from app.expenses import create_expense, ensure_default_categories
from app.purchasing import create_purchase_invoice
from tests.conftest import auth_headers


def _png_bytes() -> bytes:
    """Minimal valid 1x1 PNG."""
    signature = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = zlib.compress(b"\x00\xff\x00\x00")
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


async def _mgr_headers(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_beta_expense_with_attachment(db_session, seed, tmp_path, monkeypatch) -> m.Expense:
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    await ensure_default_categories(db_session, seed["t2"].id)
    await db_session.commit()
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t2"].id)
        )
    ).scalars().all()
    expense = await create_expense(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        amount=42,
        description="Beta secret receipt",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    key = f"{seed['t2'].id}/expenses/beta-receipt.pdf"
    path = tmp_path / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 beta-secret")
    expense.attachment_url = key
    await db_session.commit()
    return expense


async def _seed_beta_purchase_invoice_with_attachment(
    db_session, seed, tmp_path, monkeypatch
) -> m.PurchaseInvoice:
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    inv = await create_purchase_invoice(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        supplier_id=seed["supplier2"].id,
        items=[{"product_id": seed["p2"].id, "quantity": 1, "unit_price": 3}],
    )
    key = f"{seed['t2'].id}/purchase_invoices/beta-bill.pdf"
    path = tmp_path / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 beta-purchase")
    inv.attachment_url = key
    await db_session.commit()
    return inv


@pytest.mark.asyncio
async def test_expense_attachment_routes_isolated(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    expense = await _seed_beta_expense_with_attachment(db_session, seed, tmp_path, monkeypatch)
    headers = await _mgr_headers(ac)

    download = await ac.get(f"/api/v1/expenses/{expense.id}/attachment", headers=headers)
    assert download.status_code == 404

    deleted = await ac.delete(f"/api/v1/expenses/{expense.id}/attachment", headers=headers)
    assert deleted.status_code == 404

    upload = await ac.post(
        f"/api/v1/expenses/{expense.id}/attachment",
        headers=headers,
        files={"file": ("hijack.pdf", io.BytesIO(b"%PDF-1.4 hijack"), "application/pdf")},
    )
    assert upload.status_code == 404

    ocr = await ac.post(f"/api/v1/expenses/{expense.id}/ocr-suggest", headers=headers)
    assert ocr.status_code == 404

    await db_session.refresh(expense)
    assert expense.attachment_url == f"{seed['t2'].id}/expenses/beta-receipt.pdf"
    assert (tmp_path / expense.attachment_url).read_bytes() == b"%PDF-1.4 beta-secret"


@pytest.mark.asyncio
async def test_purchase_invoice_attachment_routes_isolated(
    client, db_session, tmp_path, monkeypatch
):
    ac, seed = client
    inv = await _seed_beta_purchase_invoice_with_attachment(
        db_session, seed, tmp_path, monkeypatch
    )
    headers = await _super_headers(ac, seed)

    download = await ac.get(
        f"/api/v1/purchasing/invoices/{inv.id}/attachment", headers=headers
    )
    assert download.status_code == 404

    deleted = await ac.delete(
        f"/api/v1/purchasing/invoices/{inv.id}/attachment", headers=headers
    )
    assert deleted.status_code == 404

    upload = await ac.post(
        f"/api/v1/purchasing/invoices/{inv.id}/attachment",
        headers=headers,
        files={"file": ("hijack.pdf", io.BytesIO(b"%PDF-1.4 hijack"), "application/pdf")},
    )
    assert upload.status_code == 404

    ocr = await ac.post(
        f"/api/v1/purchasing/invoices/{inv.id}/ocr-suggest", headers=headers
    )
    assert ocr.status_code == 404

    await db_session.refresh(inv)
    assert inv.attachment_url == f"{seed['t2'].id}/purchase_invoices/beta-bill.pdf"
    assert (tmp_path / inv.attachment_url).read_bytes() == b"%PDF-1.4 beta-purchase"


@pytest.mark.asyncio
async def test_poisoned_expense_attachment_key_rejected(
    client, db_session, tmp_path, monkeypatch
):
    """Own expense row must not serve another tenant's storage key."""
    ac, seed = client
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    await ensure_default_categories(db_session, seed["t1"].id)
    await db_session.commit()
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t1"].id)
        )
    ).scalars().all()
    expense = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["u1"].id,
        amount=10,
        description="Poisoned key",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    foreign_key = f"{seed['t2'].id}/expenses/stolen.pdf"
    path = tmp_path / foreign_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 stolen")
    expense.attachment_url = foreign_key
    await db_session.commit()

    headers = await _mgr_headers(ac)
    download = await ac.get(f"/api/v1/expenses/{expense.id}/attachment", headers=headers)
    assert download.status_code == 403
    assert b"stolen" not in download.content


@pytest.mark.asyncio
async def test_product_image_mutate_routes_isolated(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    # Give beta product a primary image so GET/DELETE have something to deny.
    key = f"{seed['t2'].id}/product_images/beta.png"
    path = tmp_path / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_bytes())
    seed["p2"].image_url = key
    img = m.ProductImage(
        tenant_id=seed["t2"].id,
        product_id=seed["p2"].id,
        storage_key=key,
        content_type="image/png",
        sort_order=0,
        is_primary=True,
        original_filename="beta.png",
    )
    db_session.add(img)
    await db_session.commit()
    await db_session.refresh(img)

    headers = await _mgr_headers(ac)
    foreign_id = seed["p2"].id

    assert (await ac.get(f"/api/v1/products/{foreign_id}/image", headers=headers)).status_code in {
        404,
        400,
    }
    assert (
        await ac.delete(f"/api/v1/products/{foreign_id}/image", headers=headers)
    ).status_code == 404
    assert (
        await ac.post(
            f"/api/v1/products/{foreign_id}/image",
            headers=headers,
            files={"file": ("x.png", io.BytesIO(_png_bytes()), "image/png")},
        )
    ).status_code == 404

    assert (
        await ac.get(f"/api/v1/products/{foreign_id}/images", headers=headers)
    ).status_code == 404
    assert (
        await ac.post(
            f"/api/v1/products/{foreign_id}/images",
            headers=headers,
            files={"file": ("x.png", io.BytesIO(_png_bytes()), "image/png")},
        )
    ).status_code == 404
    assert (
        await ac.patch(
            f"/api/v1/products/{foreign_id}/images/{img.id}",
            headers=headers,
            json={"is_primary": True},
        )
    ).status_code == 404
    assert (
        await ac.delete(
            f"/api/v1/products/{foreign_id}/images/{img.id}", headers=headers
        )
    ).status_code == 404

    # IDOR: alpha product + beta image id must not mutate beta gallery.
    own = await ac.patch(
        f"/api/v1/products/{seed['p1'].id}/images/{img.id}",
        headers=headers,
        json={"is_primary": True},
    )
    assert own.status_code == 404
    steal = await ac.delete(
        f"/api/v1/products/{seed['p1'].id}/images/{img.id}", headers=headers
    )
    assert steal.status_code == 404

    await db_session.refresh(img)
    await db_session.refresh(seed["p2"])
    assert img.storage_key == key
    assert seed["p2"].image_url == key


@pytest.mark.asyncio
async def test_backup_download_isolated(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    job = await create_backup(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    missing = await ac.get(f"/api/v1/backup/{job.id}/download", headers=headers)
    assert missing.status_code == 404

    restore = await ac.post(
        f"/api/v1/backup/{job.id}/restore",
        headers=headers,
        json={"dry_run": True},
    )
    assert restore.status_code == 404
