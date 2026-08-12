"""CSV export for early-pay, expense approval, and purchasing approval settings (Stage 138)."""

from __future__ import annotations

import csv
import io
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app import credit as credit_svc
from app import expenses as expenses_svc
from app import purchasing as purchasing_svc
from app import tenants as tenants_svc
from app.session_passkey_doc_export import _cell

EARLY_PAY_EXPORT_COLUMNS = [
    "early_pay_discount_pct",
    "early_pay_discount_days",
    "enabled",
    "source",
]

EXPENSE_SETTINGS_EXPORT_COLUMNS = [
    "expense_approval_threshold",
    "expense_l2_threshold",
    "max_levels",
    "levels_count",
    "levels_json",
]

PURCHASING_SETTINGS_EXPORT_COLUMNS = [
    "l1_threshold",
    "l2_threshold",
    "max_levels",
    "levels_count",
    "levels_json",
]


def _levels_json(levels) -> str:
    return json.dumps(levels or [], separators=(",", ":"), default=str)


async def export_early_pay_settings_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> str:
    tenant = await tenants_svc.get_tenant(db, tenant_id)
    data = credit_svc.early_pay_settings(tenant)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EARLY_PAY_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(data.get(k)) for k in EARLY_PAY_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_expense_approval_settings_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> str:
    data = await expenses_svc.get_approval_settings(db, tenant_id)
    levels = data.get("levels") or []
    row = {
        "expense_approval_threshold": data.get("expense_approval_threshold"),
        "expense_l2_threshold": data.get("expense_l2_threshold"),
        "max_levels": data.get("max_levels"),
        "levels_count": len(levels),
        "levels_json": _levels_json(levels),
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPENSE_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(row.get(k)) for k in EXPENSE_SETTINGS_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_purchasing_approval_settings_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> str:
    data = await purchasing_svc.get_pr_approval_settings(db, tenant_id)
    levels = data.get("levels") or []
    row = {
        "l1_threshold": data.get("l1_threshold"),
        "l2_threshold": data.get("l2_threshold"),
        "max_levels": data.get("max_levels"),
        "levels_count": len(levels),
        "levels_json": _levels_json(levels),
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PURCHASING_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(row.get(k)) for k in PURCHASING_SETTINGS_EXPORT_COLUMNS})
    return buf.getvalue()
