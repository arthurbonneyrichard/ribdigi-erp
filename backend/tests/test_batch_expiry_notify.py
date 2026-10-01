"""Batch expiry notifications on scan-due (inventory lots, not quotations)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app import notifications as notifications_svc
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_scan_batch_expiry_notifies_and_dedupes(client, db_session):
    ac, seed = client
    batch = m.ProductBatch(
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        batch_number="LOT-EXP-1",
        quantity=4,
        expiry_date=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(batch)
    await db_session.commit()

    first = await notifications_svc.scan_batch_expiry(db_session, seed["t1"].id, within_days=30)
    await db_session.commit()
    assert first == 1

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "batch_expiry",
                m.Notification.entity_id == batch.id,
            )
        )
    ).scalars().all()
    assert len(notes) == 1
    assert "LOT-EXP-1" in notes[0].message

    second = await notifications_svc.scan_batch_expiry(db_session, seed["t1"].id, within_days=30)
    await db_session.commit()
    assert second == 0

    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    scanned = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scanned.status_code == 200, scanned.text
    assert "batch_expiry" in scanned.json()["data"]
