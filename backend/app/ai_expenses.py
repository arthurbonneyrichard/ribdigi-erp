"""Rule-based AI Expense Analysis (BR-21.6) — no LLM."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai as ai_svc
from app import expenses as expenses_svc
from app import models as m
from app import reports as reports_svc

# Keyword → default category code (suggest-only for OCR)
CATEGORY_KEYWORDS: list[tuple[str, re.Pattern[str]]] = [
    ("TRANS", re.compile(r"\b(uber|bolt|taxi|fuel|petrol|diesel|transport|parking|toll)\b", re.I)),
    ("UTIL", re.compile(r"\b(electric|electricity|water\s*bill|internet|wifi|utility|utilities|gas\s*bill)\b", re.I)),
    ("RENT", re.compile(r"\b(rent|lease|landlord)\b", re.I)),
    ("SAL", re.compile(r"\b(salary|payroll|wage)\b", re.I)),
    ("MKT", re.compile(r"\b(ads?|advertis|marketing|facebook|google\s*ads|promo)\b", re.I)),
    ("SUP", re.compile(r"\b(office\s*supplies|stationery|printer|paper|ink|supplies)\b", re.I)),
]


def suggest_category_from_text(text: str, categories: list[m.ExpenseCategory]) -> dict[str, Any] | None:
    blob = text or ""
    by_code = {c.code.upper(): c for c in categories}
    for code, pat in CATEGORY_KEYWORDS:
        if pat.search(blob) and code in by_code:
            cat = by_code[code]
            return {
                "category_id": cat.id,
                "category": cat.name,
                "category_code": cat.code,
                "matched": code,
            }
    # fallback: match category name substring
    lower = blob.lower()
    for cat in categories:
        if cat.name and cat.name.lower() in lower:
            return {
                "category_id": cat.id,
                "category": cat.name,
                "category_code": cat.code,
                "matched": "name",
            }
    return None


def _parse_range(
    from_date: str | datetime | None,
    to_date: str | datetime | None,
) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    start = reports_svc.parse_date(from_date) or (now - timedelta(days=90))
    end = reports_svc.parse_date(to_date, end_of_day=True) or now
    if end < start:
        start, end = end.replace(hour=0, minute=0, second=0, microsecond=0), start
    return start, end


def _mean_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    mean = sum(vals) / len(vals)
    if len(vals) < 2:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return mean, math.sqrt(var)


async def expense_analysis(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date: str | datetime | None = None,
    to_date: str | datetime | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    await expenses_svc.ensure_default_categories(db, tenant_id)
    start, end = _parse_range(from_date, to_date)
    period_days = max(1, (end - start).days + 1)

    categories = (
        await db.execute(
            select(m.ExpenseCategory).where(
                m.ExpenseCategory.tenant_id == tenant_id,
                m.ExpenseCategory.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    rows = (
        await db.execute(
            select(m.Expense).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.status == "approved",
                m.Expense.expense_date >= start,
                m.Expense.expense_date <= end,
            )
        )
    ).scalars().all()

    by_cat_id_amount: dict[str, float] = defaultdict(float)
    by_cat_vals: dict[str, list[float]] = defaultdict(list)
    for e in rows:
        key = e.category_id or e.category or "Uncategorized"
        by_cat_vals[key].append(float(e.amount or 0))
        if e.category_id:
            by_cat_id_amount[e.category_id] += float(e.amount or 0)
        else:
            by_cat_id_amount[e.category or "Uncategorized"] += float(e.amount or 0)

    # Budget variance (scale monthly budget to period length)
    from app.expenses import scale_monthly_budget

    budget_alerts: list[dict[str, Any]] = []
    for cat in categories:
        budget = float(cat.budget_amount or 0)
        if budget <= 0:
            continue
        scaled = scale_monthly_budget(budget, period_days)
        spent = float(by_cat_id_amount.get(cat.id, 0) or by_cat_id_amount.get(cat.name, 0) or 0)
        variance_pct = round((spent - scaled) / scaled * 100.0, 1) if scaled else 0.0
        if spent > scaled * 1.0:
            budget_alerts.append(
                {
                    "category_id": cat.id,
                    "category": cat.name,
                    "budget_monthly": budget,
                    "budget_scaled": round(scaled, 2),
                    "spent": round(spent, 2),
                    "variance_pct": variance_pct,
                    "severity": "over_budget",
                }
            )
    budget_alerts.sort(key=lambda x: -x["variance_pct"])

    # Unusual amounts: > mean + 2σ within category (min 3 samples) or > 3× category median
    unusual: list[dict[str, Any]] = []
    for e in rows:
        key = e.category_id or e.category or "Uncategorized"
        vals = by_cat_vals.get(key) or []
        amt = float(e.amount or 0)
        mean, std = _mean_std(vals)
        sorted_vals = sorted(vals)
        median = sorted_vals[len(sorted_vals) // 2] if sorted_vals else 0.0
        flag = False
        reason = None
        if len(vals) >= 3 and std > 0 and amt > mean + 2 * std:
            flag = True
            reason = "above_2_sigma"
        elif median > 0 and amt > 3 * median:
            flag = True
            reason = "above_3x_median"
        if flag:
            unusual.append(
                {
                    "expense_id": e.id,
                    "category": e.category,
                    "category_id": e.category_id,
                    "amount": amt,
                    "payee": e.payee,
                    "expense_date": e.expense_date.isoformat() if e.expense_date else None,
                    "reason": reason,
                    "category_mean": round(mean, 2),
                    "category_std": round(std, 2),
                }
            )
    unusual.sort(key=lambda x: -x["amount"])

    # Duplicate payee+amount same day
    dup_key: dict[tuple, list[m.Expense]] = defaultdict(list)
    for e in rows:
        day = e.expense_date.date().isoformat() if e.expense_date else ""
        dup_key[(e.payee or "", round(float(e.amount or 0), 2), day)].append(e)
    duplicates = [
        {
            "payee": k[0],
            "amount": k[1],
            "date": k[2],
            "count": len(vs),
            "expense_ids": [v.id for v in vs],
        }
        for k, vs in dup_key.items()
        if k[0] and len(vs) >= 2
    ]

    # MoM rising for suggestions
    mid = start + (end - start) / 2
    recent = sum(float(e.amount or 0) for e in rows if e.expense_date and e.expense_date >= mid)
    prior = sum(float(e.amount or 0) for e in rows if e.expense_date and e.expense_date < mid)

    suggestions: list[str] = []
    for alert in budget_alerts[:5]:
        suggestions.append(
            f"Reduce spend in {alert['category']}: {alert['variance_pct']}% over scaled budget "
            f"({alert['spent']} vs {alert['budget_scaled']})."
        )
    if prior > 0 and recent > prior * 1.25:
        suggestions.append(
            f"Overall approved expenses rose {round((recent / prior - 1) * 100, 1)}% vs prior half of the window."
        )
    for d in duplicates[:3]:
        suggestions.append(
            f"Review possible duplicate: {d['payee']} × {d['count']} at {d['amount']} on {d['date']}."
        )
    if unusual:
        suggestions.append(
            f"{len(unusual)} expense(s) look unusual vs category norms — review before next period."
        )
    if not suggestions:
        suggestions.append("No urgent cost-optimization signals in the selected window.")

    # OCR categorization capability note (suggest-only keywords)
    ocr_categorization = {
        "mode": "keyword_suggest",
        "supported_codes": [c[0] for c in CATEGORY_KEYWORDS],
        "apply": "OCR suggestions may include category_id; human PATCH still required",
    }

    summary = await reports_svc.expenses_summary(
        db, tenant_id, from_date=start, to_date=end
    )

    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="expense_analysis",
        status="ok",
        details={
            "count": len(rows),
            "budget_alerts": len(budget_alerts),
            "unusual": len(unusual),
            "method": "rule_based",
        },
    )
    await db.commit()
    return {
        "method": "rule_based",
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "period_days": period_days,
        "summary": summary,
        "budget_variance_alerts": budget_alerts,
        "unusual_expenses": unusual[:50],
        "duplicate_candidates": duplicates[:20],
        "cost_optimization_suggestions": suggestions,
        "ocr_categorization": ocr_categorization,
        "categories": [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "budget_amount": float(c.budget_amount or 0),
            }
            for c in categories
        ],
    }
