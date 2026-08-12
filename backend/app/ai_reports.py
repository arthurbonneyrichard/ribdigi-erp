"""Rule-based AI Report Generator (BR-21.7) — constrained NL → existing reports.

No LLM. Maps phrases like "monthly sales for Q2" onto EXPORTABLE types
and reuses report_export.build_report_payload / export_report.
"""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai as ai_svc
from app import models as m
from app import report_export as report_export_svc

# Ordered: first match wins (more specific phrases before generic "sales")
_REPORT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("sales_monthly", re.compile(r"\b(monthly\s+sales|sales\s+monthly|sales\s+by\s+month)\b", re.I)),
    ("sales_daily", re.compile(r"\b(daily\s+sales|sales\s+daily|today'?s?\s+sales)\b", re.I)),
    ("sales_by_store", re.compile(r"\b(sales\s+by\s+store|store\s+sales|sales\s+per\s+store)\b", re.I)),
    ("sales_salesperson", re.compile(r"\b(sales\s*person|salesperson|by\s+rep)\b", re.I)),
    ("sales_products", re.compile(r"\b(sales\s+by\s+product|product\s+sales|top\s+products)\b", re.I)),
    ("inventory_low_stock", re.compile(r"\b(low[\s-]?stock|reorder|stockout)\b", re.I)),
    ("inventory_movements", re.compile(r"\b(stock\s+movements?|inventory\s+movements?)\b", re.I)),
    ("inventory_balance", re.compile(r"\b(inventory\s+balance|stock\s+balance|stock\s+on\s+hand)\b", re.I)),
    ("expenses_summary", re.compile(r"\b(expense|expenses|spend|spending|costs?)\b", re.I)),
    ("purchases_suppliers", re.compile(r"\b(purchases?\s+by\s+supplier|supplier\s+purchases?)\b", re.I)),
    ("purchases_summary", re.compile(r"\b(purchase|purchases|buying)\b", re.I)),
    ("cash_flow", re.compile(r"\b(cash\s*flow)\b", re.I)),
    ("profit_loss", re.compile(r"\b(profit\s*(and|&)?\s*loss|p\s*&\s*l|pnl)\b", re.I)),
    ("trial_balance", re.compile(r"\b(trial\s+balance)\b", re.I)),
    ("balance_sheet", re.compile(r"\b(balance\s+sheet)\b", re.I)),
    ("tax_filing_gh", re.compile(r"\b(ghana|gra)\b.*\b(vat|tax\s+filing)|tax\s+filing\s+gh\b", re.I)),
    ("tax_filing", re.compile(r"\b(tax\s+filing)\b", re.I)),
    ("tax", re.compile(r"\b(tax\s+report|vat\s+report|\btax\b)\b", re.I)),
    ("summary", re.compile(r"\b(executive\s+summary|dashboard\s+summary|overview)\b", re.I)),
    # generic fallbacks last
    ("sales_monthly", re.compile(r"\bsales\b", re.I)),
]

_QUARTER = re.compile(r"\bq([1-4])\b(?:\s*(?:of\s*)?(20\d{2}))?", re.I)
_YEAR_MONTH = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b")
_LAST_MONTH = re.compile(r"\b(last\s+month|previous\s+month)\b", re.I)
_THIS_MONTH = re.compile(r"\b(this\s+month|current\s+month)\b", re.I)
_LAST_YEAR = re.compile(r"\b(last\s+year|previous\s+year)\b", re.I)
_FORMAT = re.compile(r"\b(as\s+)?(csv|pdf|xlsx|excel)\b", re.I)


def _quarter_bounds(q: int, year: int) -> tuple[datetime, datetime, int, int]:
    start_month = (q - 1) * 3 + 1
    end_month = start_month + 2
    start = datetime(year, start_month, 1)
    end = datetime(year, end_month, monthrange(year, end_month)[1], 23, 59, 59)
    # For sales_monthly pick last month of quarter as representative year/month
    return start, end, year, end_month


def parse_prompt(prompt: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Map NL prompt → report_type + params. Raises 400 on unknown intent."""
    text = (prompt or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="prompt must not be empty")
    limit = ai_svc.max_message_chars()
    if len(text) > limit:
        raise HTTPException(status_code=400, detail=f"prompt exceeds maximum length of {limit}")
    injection = ai_svc.find_injection(text)
    if injection:
        raise HTTPException(status_code=400, detail="Prompt rejected by AI prompt safety controls")

    report_type = None
    for rtype, pat in _REPORT_PATTERNS:
        if pat.search(text):
            report_type = rtype
            break
    if not report_type:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Could not map prompt to a supported report",
                "hint": "Try e.g. 'monthly sales for Q2', 'low stock', 'expense summary'",
                "supported": sorted(report_export_svc.EXPORTABLE),
            },
        )

    now = now or datetime.utcnow()
    params: dict[str, Any] = {}
    matched_period = None

    qm = _QUARTER.search(text)
    if qm:
        q = int(qm.group(1))
        year = int(qm.group(2) or now.year)
        start, end, y, mo = _quarter_bounds(q, year)
        params["from_date"] = start.strftime("%Y-%m-%d")
        params["to_date"] = end.strftime("%Y-%m-%d")
        params["year"] = y
        params["month"] = mo
        matched_period = f"Q{q} {year}"
    elif _LAST_MONTH.search(text):
        y, mo = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
        params["year"] = y
        params["month"] = mo
        params["from_date"] = datetime(y, mo, 1).strftime("%Y-%m-%d")
        params["to_date"] = datetime(y, mo, monthrange(y, mo)[1]).strftime("%Y-%m-%d")
        matched_period = "last_month"
    elif _THIS_MONTH.search(text):
        params["year"] = now.year
        params["month"] = now.month
        params["from_date"] = datetime(now.year, now.month, 1).strftime("%Y-%m-%d")
        params["to_date"] = now.strftime("%Y-%m-%d")
        matched_period = "this_month"
    elif _LAST_YEAR.search(text):
        y = now.year - 1
        params["year"] = y
        params["month"] = 12
        params["from_date"] = f"{y}-01-01"
        params["to_date"] = f"{y}-12-31"
        matched_period = str(y)
    else:
        ym = _YEAR_MONTH.search(text)
        if ym:
            y, mo = int(ym.group(1)), int(ym.group(2))
            params["year"] = y
            params["month"] = mo
            params["from_date"] = datetime(y, mo, 1).strftime("%Y-%m-%d")
            params["to_date"] = datetime(y, mo, monthrange(y, mo)[1]).strftime("%Y-%m-%d")
            matched_period = f"{y}-{mo:02d}"

    # Defaults for monthly sales when no period given
    if report_type == "sales_monthly" and "year" not in params:
        params["year"] = now.year
        params["month"] = now.month
        matched_period = matched_period or "this_month"

    fmt = None
    fm = _FORMAT.search(text)
    if fm:
        fmt = fm.group(2).lower()
        if fmt == "excel":
            fmt = "xlsx"

    return {
        "report_type": report_type,
        "params": params,
        "format": fmt,
        "period_label": matched_period,
        "prompt": text,
        "method": "constrained_nl",
    }


def serialize_template(row: m.AiReportTemplate) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "prompt": row.prompt,
        "report_type": row.report_type,
        "params": row.params or {},
        "format": row.format,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def list_templates(
    db: AsyncSession, *, tenant_id: str, limit: int = 50
) -> list[m.AiReportTemplate]:
    lim = max(1, min(int(limit or 50), 200))
    rows = (
        await db.execute(
            select(m.AiReportTemplate)
            .where(m.AiReportTemplate.tenant_id == tenant_id)
            .order_by(m.AiReportTemplate.updated_at.desc())
            .limit(lim)
        )
    ).scalars().all()
    return list(rows)


async def get_template(
    db: AsyncSession, *, tenant_id: str, template_id: str
) -> m.AiReportTemplate:
    row = (
        await db.execute(
            select(m.AiReportTemplate).where(
                m.AiReportTemplate.tenant_id == tenant_id,
                m.AiReportTemplate.id == template_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Report template not found")
    return row


async def create_template(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    name: str,
    prompt: str,
    format: str | None = None,
) -> m.AiReportTemplate:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    intent = parse_prompt(prompt)
    fmt = (format or intent.get("format") or "csv").lower()
    if fmt not in report_export_svc.EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {sorted(report_export_svc.EXPORT_FORMATS)}")
    row = m.AiReportTemplate(
        tenant_id=tenant_id,
        name=name[:120],
        prompt=prompt.strip(),
        report_type=intent["report_type"],
        params=intent.get("params") or {},
        format=fmt,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_template(db: AsyncSession, *, tenant_id: str, template_id: str) -> None:
    row = await get_template(db, tenant_id=tenant_id, template_id=template_id)
    await db.delete(row)
    await db.flush()


async def generate_report(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    prompt: str | None = None,
    format: str | None = None,
    template_id: str | None = None,
    report_type: str | None = None,
    period: str | None = None,
    filters: dict | None = None,
) -> dict[str, Any]:
    """Return JSON preview of generated report (+ export metadata)."""
    if template_id:
        tmpl = await get_template(db, tenant_id=tenant_id, template_id=template_id)
        intent = {
            "report_type": tmpl.report_type,
            "params": dict(tmpl.params or {}),
            "format": format or tmpl.format or "csv",
            "period_label": None,
            "prompt": tmpl.prompt,
            "method": "template",
            "template_id": tmpl.id,
        }
    elif prompt:
        intent = parse_prompt(prompt)
        if format:
            intent["format"] = format
    elif report_type:
        # Structured path from API docs
        if report_type not in report_export_svc.EXPORTABLE:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")
        params = dict(filters or {})
        # map period shorthand
        if period:
            intent = parse_prompt(f"{report_type.replace('_', ' ')} {period}")
            intent["report_type"] = report_type
            intent["params"].update(params)
        else:
            intent = {
                "report_type": report_type,
                "params": params,
                "format": format or "csv",
                "period_label": period,
                "prompt": None,
                "method": "structured",
            }
        if format:
            intent["format"] = format
    else:
        raise HTTPException(status_code=422, detail="Provide prompt, template_id, or report_type")

    rtype = intent["report_type"]
    params = intent.get("params") or {}
    payload = await report_export_svc.build_report_payload(
        db,
        tenant_id,
        rtype,
        from_date=params.get("from_date"),
        to_date=params.get("to_date"),
        date=params.get("date"),
        year=params.get("year"),
        month=params.get("month"),
        warehouse_id=params.get("warehouse_id"),
        jurisdiction=params.get("jurisdiction"),
    )
    rows, _pdf_lines, title = report_export_svc.flatten_report(rtype, payload)
    fmt = (intent.get("format") or format or "csv").lower()
    if fmt not in report_export_svc.EXPORT_FORMATS:
        fmt = "csv"

    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="reports_generate",
        status="ok",
        message=intent.get("prompt"),
        details={
            "report_type": rtype,
            "format": fmt,
            "method": intent.get("method"),
            "row_count": len(rows),
            "template_id": intent.get("template_id"),
        },
    )
    await db.commit()

    # Preview: trim large payloads
    preview_rows = rows[:50]
    return {
        "method": intent.get("method"),
        "title": title,
        "report_type": rtype,
        "params": params,
        "period_label": intent.get("period_label"),
        "format": fmt,
        "prompt": intent.get("prompt"),
        "template_id": intent.get("template_id"),
        "row_count": len(rows),
        "preview_rows": preview_rows,
        "data": payload if not isinstance(payload, list) else payload[:50],
        "export_hint": {
            "endpoint": "/api/v1/ai/reports/export",
            "body": {
                "prompt": intent.get("prompt"),
                "template_id": intent.get("template_id"),
                "report_type": rtype,
                "format": fmt,
                "params": params,
            },
        },
        "supported_formats": sorted(report_export_svc.EXPORT_FORMATS),
    }


async def export_from_intent(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    prompt: str | None = None,
    format: str | None = None,
    template_id: str | None = None,
    report_type: str | None = None,
    params: dict | None = None,
) -> tuple[bytes, str, str, dict[str, Any]]:
    """Return (content, media_type, filename, intent_meta)."""
    generated = await generate_report(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        prompt=prompt,
        format=format,
        template_id=template_id,
        report_type=report_type,
        filters=params,
    )
    # generate_report already committed; build export bytes again without re-audit noise
    rtype = generated["report_type"]
    p = generated.get("params") or {}
    fmt = (format or generated.get("format") or "csv").lower()
    content, media, filename = await report_export_svc.export_report(
        db,
        tenant_id,
        rtype,
        fmt,
        from_date=p.get("from_date"),
        to_date=p.get("to_date"),
        date=p.get("date"),
        year=p.get("year"),
        month=p.get("month"),
        warehouse_id=p.get("warehouse_id"),
        jurisdiction=p.get("jurisdiction"),
    )
    return content, media, filename, generated
