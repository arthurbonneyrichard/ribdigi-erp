"""Deterministic AI expense analysis (Phase 4 / BR-21.6).

Budget variance, unusual pattern detection, cost optimization suggestions,
and receipt-text category suggestions (OCR companion) — no external ML.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, median, pstdev

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import expenses as expenses_svc
from app.reports import apply_company_filter

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Rent": ("rent", "lease", "landlord", "premises"),
    "Utilities": (
        "electric",
        "electricity",
        "water",
        "utility",
        "utilities",
        "internet",
        "wifi",
        "gas bill",
        "power",
    ),
    "Salaries": ("salary", "salaries", "payroll", "wage", "wages", "stipend"),
    "Transportation": (
        "fuel",
        "petrol",
        "diesel",
        "transport",
        "uber",
        "taxi",
        "freight",
        "shipping",
        "delivery",
        "logistics",
    ),
    "Marketing": (
        "ads",
        "advert",
        "marketing",
        "promo",
        "promotion",
        "facebook",
        "google ads",
        "campaign",
    ),
    "Supplies": (
        "supply",
        "supplies",
        "stationery",
        "office",
        "toner",
        "paper",
        "packaging",
    ),
    "Miscellaneous": ("misc", "other", "general"),
}


def _parse_bound(value: datetime | str | None, *, end: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text[:19], fmt)
            if end and fmt == "%Y-%m-%d":
                return dt.replace(hour=23, minute=59, second=59)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def suggest_category_from_text(
    text: str,
    categories: list[m.ExpenseCategory] | list[dict],
) -> dict | None:
    """Map receipt/description text to a tenant expense category via keywords."""
    hay = (text or "").lower()
    if not hay.strip():
        return None
    best = None
    best_hits = 0
    name_by_norm = {}
    for cat in categories:
        if isinstance(cat, dict):
            name = cat.get("name") or ""
            cid = cat.get("id")
            code = cat.get("code")
        else:
            name = cat.name or ""
            cid = cat.id
            code = cat.code
        name_by_norm[name.lower()] = {"id": cid, "name": name, "code": code}

    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in hay)
        # Prefer exact category name mention
        if cat_name.lower() in hay:
            hits += 3
        if hits > best_hits and cat_name.lower() in name_by_norm:
            best_hits = hits
            best = {**name_by_norm[cat_name.lower()], "matched_keywords": hits}

    if best is None:
        # fuzzy: any tenant category name appearing in text
        for norm, meta in name_by_norm.items():
            if len(norm) >= 3 and norm in hay:
                return {**meta, "matched_keywords": 1, "confidence": 0.55}
        return None

    confidence = min(0.95, 0.4 + 0.15 * best_hits)
    return {**best, "confidence": round(confidence, 2)}


async def analyze_expenses(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | str | None = None,
    to_date: datetime | str | None = None,
    company_id: str | None = None,
) -> dict:
    now = datetime.utcnow()
    try:
        start = _parse_bound(from_date) or datetime(now.year, now.month, 1)
        end = _parse_bound(to_date, end=True) or now
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if end < start:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="to_date must be on or after from_date")

    budgets = await expenses_svc.category_budget_variance(
        db, tenant_id, from_date=start, to_date=end, company_id=company_id
    )

    exp_stmt = select(m.Expense).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.expense_date >= start,
        m.Expense.expense_date <= end,
    )
    exp_stmt = apply_company_filter(exp_stmt, m.Expense.company_id, company_id)
    expenses = (await db.execute(exp_stmt)).scalars().all()

    cat_stmt = select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id)
    cat_stmt = apply_company_filter(cat_stmt, m.ExpenseCategory.company_id, company_id)
    cats = (await db.execute(cat_stmt)).scalars().all()
    cat_by_id = {c.id: c for c in cats}

    approved = [e for e in expenses if e.status == "approved"]
    pending = [e for e in expenses if e.status == "pending"]
    amounts = [float(e.amount or 0) for e in approved]
    total_approved = round(sum(amounts), 2)
    avg_amt = round(mean(amounts), 2) if amounts else 0.0
    std_amt = pstdev(amounts) if len(amounts) >= 2 else 0.0
    threshold = avg_amt + (2 * std_amt if std_amt > 0 else avg_amt) if amounts else 0.0

    # Unusual: high vs category peers + overall spike
    by_cat_amounts: dict[str, list[float]] = defaultdict(list)
    for e in approved:
        key = e.category_id or e.category or "Uncategorized"
        by_cat_amounts[key].append(float(e.amount or 0))

    anomalies: list[dict] = []
    for e in approved:
        amt = float(e.amount or 0)
        key = e.category_id or e.category or "Uncategorized"
        peers = by_cat_amounts.get(key) or []
        cat_mean = mean(peers) if peers else avg_amt
        cat_std = pstdev(peers) if len(peers) >= 2 else 0.0
        cat_thresh = cat_mean + (2 * cat_std if cat_std > 0 else cat_mean)
        others = list(peers)
        if amt in others:
            others.remove(amt)
        baseline = median(others) if others else cat_mean
        reasons = []
        if threshold > 0 and amt >= max(threshold, avg_amt * 2 if avg_amt else threshold):
            reasons.append("above_overall_2sigma")
        if cat_thresh > 0 and amt >= max(cat_thresh, cat_mean * 2 if cat_mean else cat_thresh):
            reasons.append("above_category_2sigma")
        if baseline > 0 and amt >= baseline * 2.5:
            reasons.append("outlier_vs_category_median")
        if avg_amt > 0 and amt >= avg_amt * 2.5:
            reasons.append("outlier_vs_overall_average")
        if not reasons:
            continue
        cat = cat_by_id.get(e.category_id) if e.category_id else None
        anomalies.append(
            {
                "expense_id": e.id,
                "category": cat.name if cat else e.category,
                "description": e.description,
                "amount": amt,
                "expense_date": e.expense_date,
                "reasons": reasons,
                "severity": "high" if amt >= (avg_amt * 3 if avg_amt else amt) else "medium",
            }
        )
    anomalies.sort(key=lambda x: -x["amount"])

    # Week-over-week spend spike
    week_ago = end - timedelta(days=7)
    two_weeks = end - timedelta(days=14)
    this_week = sum(
        float(e.amount or 0)
        for e in approved
        if e.expense_date and week_ago <= e.expense_date <= end
    )
    prev_week = sum(
        float(e.amount or 0)
        for e in approved
        if e.expense_date and two_weeks <= e.expense_date < week_ago
    )
    wow_pct = None
    if prev_week > 0:
        wow_pct = round(((this_week - prev_week) / prev_week) * 100, 1)
        if wow_pct >= 40:
            anomalies.insert(
                0,
                {
                    "expense_id": None,
                    "category": None,
                    "description": "Approved expenses up sharply week-over-week",
                    "amount": round(this_week, 2),
                    "expense_date": end,
                    "reasons": ["week_over_week_spike"],
                    "severity": "high",
                    "metrics": {
                        "this_week": round(this_week, 2),
                        "prior_week": round(prev_week, 2),
                        "change_pct": wow_pct,
                    },
                },
            )

    # Cost optimization suggestions
    suggestions: list[dict] = []
    over = [c for c in budgets["categories"] if c.get("over_budget")]
    for row in over[:10]:
        suggestions.append(
            {
                "kind": "over_budget",
                "category_id": row.get("id"),
                "category": row.get("name"),
                "summary": (
                    f"{row.get('name')} is over budget by "
                    f"{abs(float(row.get('variance') or 0)):.2f} "
                    f"(spent {row.get('spent')}, budget {row.get('budget_amount')})."
                ),
                "action": "Pause discretionary spend in this category or raise the budget after review.",
            }
        )

    misc = next((c for c in budgets["categories"] if (c.get("name") or "").lower() == "miscellaneous"), None)
    if misc and float(misc.get("spent") or 0) > 0 and total_approved > 0:
        share = float(misc["spent"]) / total_approved
        if share >= 0.25:
            suggestions.append(
                {
                    "kind": "misc_concentration",
                    "category_id": misc.get("id"),
                    "category": "Miscellaneous",
                    "summary": (
                        f"Miscellaneous is {share:.0%} of approved spend "
                        f"({misc.get('spent'):.2f}). Reclassify recurring items."
                    ),
                    "action": "Map frequent Misc payees to specific categories.",
                }
            )

    # High pending backlog
    pending_total = round(sum(float(e.amount or 0) for e in pending), 2)
    if pending_total > 0 and (total_approved == 0 or pending_total >= total_approved * 0.5):
        suggestions.append(
            {
                "kind": "pending_backlog",
                "category_id": None,
                "category": None,
                "summary": f"{len(pending)} pending expense(s) totaling {pending_total:.2f} await approval.",
                "action": "Clear the approval queue to keep budgets accurate.",
            }
        )

    # OCR / categorization companion stats
    with_attachment = sum(1 for e in expenses if e.attachment_url)
    uncategorized = [
        e
        for e in expenses
        if not e.category_id
        and (not e.category or e.category.lower() in {"miscellaneous", "misc", "uncategorized", ""})
    ]
    sample_suggestions = []
    for e in expenses[:30]:
        text = " ".join(filter(None, [e.description, e.payee, e.category, e.reference]))
        sug = suggest_category_from_text(text, cats)
        if sug and (not e.category_id or (cat_by_id.get(e.category_id) and cat_by_id[e.category_id].name != sug["name"])):
            sample_suggestions.append(
                {
                    "expense_id": e.id,
                    "current_category": e.category,
                    "suggested_category": sug["name"],
                    "suggested_category_id": sug["id"],
                    "confidence": sug["confidence"],
                }
            )

    return {
        "generated_at": now,
        "from_date": start,
        "to_date": end,
        "method": "rules_v1",
        "summary": {
            "expense_count": len(expenses),
            "approved_count": len(approved),
            "pending_count": len(pending),
            "total_approved": total_approved,
            "total_pending": pending_total,
            "avg_approved_amount": avg_amt,
            "with_attachment": with_attachment,
            "wow_change_pct": wow_pct,
        },
        "budget_variance": {
            "categories": budgets["categories"],
            "totals": budgets["totals"],
            "over_budget_count": len(over),
        },
        "anomalies": anomalies[:50],
        "optimization_suggestions": suggestions,
        "categorization": {
            "uncategorized_or_misc_count": len(uncategorized),
            "ocr_endpoint": "POST /expenses/{id}/ocr-suggest",
            "ocr_apply_endpoint": "POST /expenses/{id}/ocr-apply",
            "text_category_suggestions": sample_suggestions[:20],
            "note": (
                "Receipt OCR extracts amount/date/payee; category is suggested from "
                "receipt/description keywords against tenant expense categories. "
                "Apply reviewed fields with confirm=true (Stage 10 A1) — no silent auto-write."
            ),
        },
    }
