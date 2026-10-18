"""Read-only, secret-free platform operations settings for the software owner."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import saas_billing as billing_svc
from app.config import settings


async def build_platform_settings(db: AsyncSession) -> dict[str, Any]:
    """Environment-driven operational values. Nothing here is persisted or editable.

    Gateway fields come from the same visible-provider helper as the billing
    console (a sandbox or untested gateway is never reported as live). No keys,
    secrets, hints or webhook URLs are returned.
    """
    from app import billing_gateway_setup as gateway_setup
    from app.billing_api import _visible_provider

    provider = await _visible_provider(db)
    row = await gateway_setup._row(db)
    return {
        "trial_days": int(settings.TRIAL_DAYS),
        "grace_days": int(settings.TRIAL_GRACE_DAYS),
        "billing_grace_days": int(settings.BILLING_GRACE_DAYS),
        "billing_reminder_days": sorted(billing_svc.reminder_days(), reverse=True),
        "billing_max_attempts": int(settings.BILLING_MAX_ATTEMPTS),
        "billing": {
            "provider": provider["provider"],
            "configured": bool(provider["configured"]),
            "live_charges": bool(provider["live_charges"]),
            "gateway_mode": (row.mode if row is not None else None),
            "gateway_enabled": bool(row.enabled) if row is not None else False,
            "gateway_tested": bool(row.last_test_ok) if row is not None else False,
        },
        "live_charges": bool(provider["live_charges"]),
        "editable": False,
        "source": "environment",
    }
