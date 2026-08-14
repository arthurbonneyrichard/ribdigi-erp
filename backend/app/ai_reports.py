"""Natural-language report generator (Phase 4 / BR-21.7).

Parses text prompts into existing exportable report types, builds a preview,
exports via report_export, and persists reusable templates — no LLM required.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.report_export import (
    EXPORT_FORMATS,
    EXPORTABLE,
    build_report_payload,
    export_report,
    flatten_report,
)
from app.reports import apply_company_filter

# Ordered: first match wins for specificity
REPORT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("sales_by_store", re.compile(r"\b(sales?\s+by\s+store|store\s+sales|by\s+store)\b", re.I)),
    ("sales_salesperson", re.compile(r"\b(salesperson|sales\s+person|by\s+staff|by\s+cashier)\b", re.I)),
    ("sales_products", re.compile(r"\b(product\s+sales|sales\s+by\s+product|top\s+products?|best\s+sellers?)\b", re.I)),
    ("sales_monthly", re.compile(r"\b(monthly\s+sales|sales\s+monthly|sales\s+this\s+month|month(?:ly)?\s+revenue)\b", re.I)),
    ("sales_daily", re.compile(r"\b(daily\s+sales|sales\s+today|today'?s?\s+sales)\b", re.I)),
    ("inventory_low_stock", re.compile(r"\b(low\s+stock|reorder|stockout)\b", re.I)),
    ("inventory_movements", re.compile(r"\b(stock\s+movements?|inventory\s+movements?)\b", re.I)),
    ("inventory_balance", re.compile(r"\b(inventory|stock\s+balance|stock\s+on\s+hand|warehouse\s+stock)\b", re.I)),
    ("purchases_suppliers", re.compile(r"\b(purchases?\s+by\s+supplier|supplier\s+purchases?)\b", re.I)),
    ("purchases_summary", re.compile(r"\b(purchase|purchases|buying)\b", re.I)),
    ("expenses_summary", re.compile(r"\b(expense|expenses|spending|costs?)\b", re.I)),
    ("cash_flow", re.compile(r"\b(cash\s*flow)\b", re.I)),
    ("profit_loss", re.compile(r"\b(profit\s*(and|&)?\s*loss|p\s*&\s*l|pnl)\b", re.I)),
    ("trial_balance", re.compile(r"\b(trial\s+balance)\b", re.I)),
    ("balance_sheet", re.compile(r"\b(balance\s+sheet)\b", re.I)),
    ("tax_filing_gh", re.compile(r"\b(ghana|gra)\b.*\b(tax|vat|filing)\b|\b(tax|vat|filing)\b.*\b(ghana|gra)\b", re.I)),
    ("tax_filing_ng", re.compile(r"\b(nigeria|firs)\b.*\b(tax|vat|filing)\b|\b(tax|vat|filing)\b.*\b(nigeria|firs)\b", re.I)),
    ("tax_filing", re.compile(r"\b(tax\s+filing|vat\s+return|filing\s+pack)\b", re.I)),
    ("tax", re.compile(r"\b(tax|vat)\b", re.I)),
    ("summary", re.compile(r"\b(summary|overview|dashboard\s+report)\b", re.I)),
    # generic sales fallback
    ("sales_products", re.compile(r"\b(sales|revenue)\b", re.I)),
]

MONTH_NAMES = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


def _quarter_bounds(year: int, quarter: int) -> tuple[datetime, datetime]:
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    start = datetime(year, start_month, 1)
    last_day = calendar.monthrange(year, end_month)[1]
    end = datetime(year, end_month, last_day, 23, 59, 59)
    return start, end


def detect_report_type(prompt: str) -> str:
    text = (prompt or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="prompt is required")
    for report_type, pattern in REPORT_PATTERNS:
        if pattern.search(text):
            return report_type
    raise HTTPException(
        status_code=400,
        detail=(
            "Could not map prompt to a report. Try e.g. "
            "'Show me monthly sales for Q2', 'low stock', or 'expense summary'."
        ),
    )


def parse_period(prompt: str, *, now: datetime | None = None) -> dict:
    """Extract date filters / year-month from natural language."""
    now = now or datetime.utcnow()
    text = (prompt or "").lower()
    params: dict = {}
    period_label = "current"

    # Q1–Q4
    m_q = re.search(r"\bq([1-4])\b(?:\s*(?:of\s+)?(20\d{2}))?", text)
    if m_q:
        q = int(m_q.group(1))
        year = int(m_q.group(2) or now.year)
        start, end = _quarter_bounds(year, q)
        params["from_date"] = start.strftime("%Y-%m-%d")
        params["to_date"] = end.strftime("%Y-%m-%d")
        params["year"] = year
        params["month"] = end.month  # last month of quarter for monthly reports
        period_label = f"Q{q} {year}"
        return {**params, "period_label": period_label}

    if "last month" in text:
        if now.month == 1:
            y, mo = now.year - 1, 12
        else:
            y, mo = now.year, now.month - 1
        start = datetime(y, mo, 1)
        end = datetime(y, mo, calendar.monthrange(y, mo)[1], 23, 59, 59)
        params.update(
            {
                "from_date": start.strftime("%Y-%m-%d"),
                "to_date": end.strftime("%Y-%m-%d"),
                "year": y,
                "month": mo,
                "period_label": start.strftime("%B %Y"),
            }
        )
        return params

    if "this month" in text or "current month" in text:
        start = datetime(now.year, now.month, 1)
        end = now
        params.update(
            {
                "from_date": start.strftime("%Y-%m-%d"),
                "to_date": end.strftime("%Y-%m-%d"),
                "year": now.year,
                "month": now.month,
                "period_label": start.strftime("%B %Y"),
            }
        )
        return params

    if "last year" in text:
        y = now.year - 1
        params.update(
            {
                "from_date": f"{y}-01-01",
                "to_date": f"{y}-12-31",
                "year": y,
                "month": 12,
                "period_label": str(y),
            }
        )
        return params

    if "this year" in text or "ytd" in text or "year to date" in text:
        params.update(
            {
                "from_date": f"{now.year}-01-01",
                "to_date": now.strftime("%Y-%m-%d"),
                "year": now.year,
                "month": now.month,
                "period_label": f"YTD {now.year}",
            }
        )
        return params

    m_days = re.search(r"\blast\s+(\d{1,3})\s+days?\b", text)
    if m_days:
        days = max(1, min(int(m_days.group(1)), 365))
        start = now - timedelta(days=days)
        params.update(
            {
                "from_date": start.strftime("%Y-%m-%d"),
                "to_date": now.strftime("%Y-%m-%d"),
                "period_label": f"last {days} days",
            }
        )
        return params

    # Month name (+ optional year)
    for name, mo in MONTH_NAMES.items():
        if re.search(rf"\b{name}\b", text):
            ym = re.search(rf"\b{name}\b\s*(20\d{{2}})?", text)
            year = int(ym.group(1)) if ym and ym.group(1) else now.year
            start = datetime(year, mo, 1)
            end = datetime(year, mo, calendar.monthrange(year, mo)[1], 23, 59, 59)
            params.update(
                {
                    "from_date": start.strftime("%Y-%m-%d"),
                    "to_date": end.strftime("%Y-%m-%d"),
                    "year": year,
                    "month": mo,
                    "period_label": start.strftime("%B %Y"),
                }
            )
            return params

    # Default: current month
    start = datetime(now.year, now.month, 1)
    params.update(
        {
            "from_date": start.strftime("%Y-%m-%d"),
            "to_date": now.strftime("%Y-%m-%d"),
            "year": now.year,
            "month": now.month,
            "period_label": start.strftime("%B %Y"),
        }
    )
    return params


def detect_format(prompt: str, explicit: str | None = None) -> str:
    if explicit:
        fmt = explicit.lower().strip()
        if fmt not in EXPORT_FORMATS:
            raise HTTPException(status_code=400, detail=f"format must be one of {sorted(EXPORT_FORMATS)}")
        return fmt
    text = (prompt or "").lower()
    if re.search(r"\bpdf\b", text):
        return "pdf"
    if re.search(r"\b(excel|xlsx|spreadsheet)\b", text):
        return "xlsx"
    if re.search(r"\bcsv\b", text):
        return "csv"
    return "xlsx"


def parse_prompt(prompt: str, *, format: str | None = None, now: datetime | None = None) -> dict:
    report_type = detect_report_type(prompt)
    period = parse_period(prompt, now=now)
    fmt = detect_format(prompt, format)

    # Multi-month quarters don't fit a single sales_monthly well — use product sales range
    if report_type == "sales_monthly" and period.get("period_label", "").startswith("Q"):
        report_type = "sales_products"

    return {
        "prompt": (prompt or "").strip(),
        "report_type": report_type,
        "format": fmt,
        "params": {
            k: v
            for k, v in period.items()
            if k in {"from_date", "to_date", "year", "month", "date", "warehouse_id", "jurisdiction"}
        },
        "period_label": period.get("period_label"),
        "method": "rules_v1",
    }


def serialize_template(row: m.AiReportTemplate) -> dict:
    out = {
        "id": row.id,
        "name": row.name,
        "prompt": row.prompt,
        "report_type": row.report_type,
        "format": row.format,
        "params": row.params or {},
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "user_id": row.user_id,
    }
    if getattr(row, "company_id", None):
        out["company_id"] = row.company_id
    return out


def _preview_rows(rows: list[dict], limit: int = 25) -> list[dict]:
    out = []
    for row in rows[:limit]:
        clean = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                clean[k] = v.isoformat()
            else:
                clean[k] = v
        out.append(clean)
    return out


async def generate_from_prompt(
    db: AsyncSession,
    tenant_id: str,
    *,
    prompt: str,
    format: str | None = None,
    template_id: str | None = None,
    company_id: str | None = None,
) -> dict:
    if template_id:
        tmpl = await get_template(db, tenant_id, template_id, company_id=company_id)
        prompt = tmpl.prompt
        format = format or tmpl.format

    parsed = parse_prompt(prompt, format=format)
    report_type = parsed["report_type"]
    if report_type not in EXPORTABLE:
        raise HTTPException(status_code=400, detail=f"Unsupported report type: {report_type}")

    kwargs = dict(parsed["params"])
    payload = await build_report_payload(
        db, tenant_id, report_type, company_id=company_id, **kwargs
    )
    rows, lines, title = flatten_report(report_type, payload)

    return {
        "generated_at": datetime.utcnow(),
        "title": title,
        "report_type": report_type,
        "format": parsed["format"],
        "period_label": parsed["period_label"],
        "prompt": parsed["prompt"],
        "params": kwargs,
        "row_count": len(rows),
        "preview_rows": _preview_rows(rows),
        "preview_lines": lines[:40],
        "export_ready": True,
        "method": "rules_v1",
        "note": "Export with the same prompt via POST /ai/reports/generate?export=true or /ai/reports/export.",
    }


async def export_from_prompt(
    db: AsyncSession,
    tenant_id: str,
    *,
    prompt: str,
    format: str | None = None,
    template_id: str | None = None,
    company_id: str | None = None,
) -> tuple[bytes, str, str]:
    if template_id:
        tmpl = await get_template(db, tenant_id, template_id, company_id=company_id)
        prompt = tmpl.prompt
        format = format or tmpl.format
    parsed = parse_prompt(prompt, format=format)
    return await export_report(
        db,
        tenant_id,
        parsed["report_type"],
        parsed["format"],
        company_id=company_id,
        **parsed["params"],
    )


async def list_templates(
    db: AsyncSession,
    tenant_id: str,
    *,
    user_id: str | None = None,
    company_id: str | None = None,
) -> list[m.AiReportTemplate]:
    q = select(m.AiReportTemplate).where(m.AiReportTemplate.tenant_id == tenant_id)
    q = apply_company_filter(q, m.AiReportTemplate.company_id, company_id)
    if user_id:
        q = q.where(
            (m.AiReportTemplate.user_id == user_id) | (m.AiReportTemplate.user_id.is_(None))
        )
    q = q.order_by(m.AiReportTemplate.updated_at.desc())
    return list((await db.execute(q)).scalars().all())


async def get_template(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    *,
    company_id: str | None = None,
) -> m.AiReportTemplate:
    stmt = select(m.AiReportTemplate).where(
        m.AiReportTemplate.id == template_id,
        m.AiReportTemplate.tenant_id == tenant_id,
    )
    stmt = apply_company_filter(stmt, m.AiReportTemplate.company_id, company_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Report template not found")
    return row


async def save_template(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    name: str,
    prompt: str,
    format: str | None = None,
    company_id: str | None = None,
) -> m.AiReportTemplate:
    name = (name or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="name is required")
    parsed = parse_prompt(prompt, format=format)
    row = m.AiReportTemplate(
        tenant_id=tenant_id,
        company_id=company_id,
        user_id=user_id,
        name=name[:120],
        prompt=parsed["prompt"],
        report_type=parsed["report_type"],
        format=parsed["format"],
        params={**parsed["params"], "period_label": parsed["period_label"]},
    )
    db.add(row)
    await db.flush()
    return row


async def delete_template(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    *,
    company_id: str | None = None,
) -> None:
    row = await get_template(db, tenant_id, template_id, company_id=company_id)
    await db.delete(row)
    await db.flush()
