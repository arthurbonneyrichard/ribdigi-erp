"""Weekly tenant-scoped AI insight digest delivery (BR-21.2)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai as ai_svc
from app import emailer
from app import models as m
from app.dashboard import build_dashboard

ADMIN_RECIPIENT_ROLES = ("company_admin", "super_admin")


async def _recipient_users(
    db: AsyncSession,
    *,
    tenant_id: str,
    recipient_user_ids: list[str] | None,
) -> list[m.User]:
    stmt = select(m.User).where(
        m.User.tenant_id == tenant_id,
        m.User.is_active == True,  # noqa: E712
        m.User.email.is_not(None),
    )
    if recipient_user_ids is None:
        stmt = stmt.where(m.User.role.in_(ADMIN_RECIPIENT_ROLES))
    else:
        ids = [str(user_id) for user_id in recipient_user_ids if user_id]
        if not ids:
            return []
        stmt = stmt.where(m.User.id.in_(ids))
    return list((await db.execute(stmt.order_by(m.User.email))).scalars().all())


async def send_tenant_digest(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    recipient_user_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Generate current dashboard rules and email a digest within one tenant."""
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    dashboard = await build_dashboard(db, tenant_id)
    insights = ai_svc.build_insight_notes(dashboard)
    recipients = await _recipient_users(
        db,
        tenant_id=tenant_id,
        recipient_user_ids=recipient_user_ids,
    )

    modes: Counter[str] = Counter()
    sent = 0
    failed = 0
    for user in recipients:
        result = await emailer.send_ai_insight_digest_email(
            to=user.email,
            company_name=tenant.company_name,
            insights=insights,
            tenant=tenant,
        )
        modes[result.mode] += 1
        if result.sent:
            sent += 1
        else:
            failed += 1

    status = "ok" if recipients and failed == 0 else "partial" if sent else "disabled"
    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="insight_digest",
        status=status,
        insight_count=len(insights),
        details={
            "source": "dashboard_rules",
            "recipient_count": len(recipients),
            "sent": sent,
            "failed": failed,
            "delivery_modes": dict(modes),
        },
    )
    await db.flush()
    return {
        "insights": insights,
        "source": "rule_based",
        "recipient_count": len(recipients),
        "sent": sent,
        "failed": failed,
        "delivery_modes": dict(modes),
    }
