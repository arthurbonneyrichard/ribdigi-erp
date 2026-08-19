"""AI customer assistant (Phase 4 / BR-21.9).

Churn risk scoring, best-customer ranking, and promotion suggestions from
posted sales history — no external LLM required.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.reports import apply_company_filter

POSTED = frozenset({"posted", "sent", "partial", "paid", "overdue"})


def _churn_score(*, recency_days: int | None, frequency: int, monetary: float) -> dict:
    """0–100 risk; higher = more likely to churn."""
    if recency_days is None:
        return {"score": 90, "band": "high", "reason": "no_purchases"}
    score = 0
    reasons = []
    if recency_days >= 90:
        score += 50
        reasons.append("inactive_90d+")
    elif recency_days >= 60:
        score += 35
        reasons.append("inactive_60d+")
    elif recency_days >= 30:
        score += 20
        reasons.append("inactive_30d+")
    if frequency <= 1:
        score += 25
        reasons.append("low_frequency")
    elif frequency <= 3:
        score += 10
    if monetary < 50:
        score += 15
        reasons.append("low_spend")
    score = min(100, score)
    band = "high" if score >= 60 else "medium" if score >= 35 else "low"
    return {"score": score, "band": band, "reasons": reasons}


def _promotion_for(segment: dict) -> dict:
    band = segment["churn"]["band"]
    monetary = segment["monetary"]
    if band == "high":
        return {
            "type": "win_back",
            "label": "Win-back offer",
            "suggestion": "Offer a time-limited 10–15% discount on their usual products.",
            "discount_pct": 12,
        }
    if band == "medium":
        return {
            "type": "re_engage",
            "label": "Re-engagement",
            "suggestion": "Send a reminder with free delivery or a small loyalty bonus.",
            "discount_pct": 5,
        }
    if monetary >= 500:
        return {
            "type": "vip",
            "label": "VIP loyalty",
            "suggestion": "Invite to a VIP/wholesale tier or early-access promo.",
            "discount_pct": 0,
        }
    return {
        "type": "upsell",
        "label": "Bundle upsell",
        "suggestion": "Suggest frequently bought-together items from recent affinity.",
        "discount_pct": 0,
    }


async def customer_intelligence(
    db: AsyncSession,
    tenant_id: str,
    *,
    lookback_days: int = 180,
    company_id: str | None = None,
) -> dict:
    lookback_days = max(30, min(int(lookback_days), 730))
    now = datetime.utcnow()
    since = now - timedelta(days=lookback_days)

    party_stmt = select(m.Party).where(
        m.Party.tenant_id == tenant_id,
        m.Party.kind == "customer",
        m.Party.status == "active",
    )
    party_stmt = apply_company_filter(party_stmt, m.Party.company_id, company_id)
    customers = (await db.execute(party_stmt)).scalars().all()

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(list(POSTED)),
        m.SalesInvoice.created_at >= since,
    )
    inv_stmt = apply_company_filter(inv_stmt, m.SalesInvoice.company_id, company_id)
    invoices = (await db.execute(inv_stmt)).scalars().all()

    by_cust: dict[str, dict] = {}
    for inv in invoices:
        cid = inv.customer_id
        if not cid:
            continue
        when = inv.posted_at or inv.created_at or now
        row = by_cust.setdefault(cid, {"count": 0, "monetary": 0.0, "last": when, "open": 0.0})
        row["count"] += 1
        row["monetary"] += float(inv.total_amount or 0)
        unpaid = float(inv.total_amount or 0) - float(inv.paid_amount or 0)
        if inv.status in {"partial", "posted", "sent", "overdue"} and unpaid > 0:
            row["open"] += unpaid
        if when > row["last"]:
            row["last"] = when

    ranked = []
    for cust in customers:
        stats = by_cust.get(cust.id) or {"count": 0, "monetary": 0.0, "last": None, "open": 0.0}
        recency = (now - stats["last"]).days if stats["last"] else None
        churn = _churn_score(
            recency_days=recency,
            frequency=int(stats["count"]),
            monetary=float(stats["monetary"]),
        )
        item = {
            "customer_id": cust.id,
            "name": cust.name,
            "code": cust.code,
            "credit_limit": float(cust.credit_limit or 0),
            "balance": float(cust.balance or 0),
            "recency_days": recency,
            "frequency": int(stats["count"]),
            "monetary": round(float(stats["monetary"]), 2),
            "open_invoice_balance": round(float(stats["open"]), 2),
            "churn": churn,
            "last_purchase_at": stats["last"],
        }
        item["promotion"] = _promotion_for(item)
        ranked.append(item)

    best = sorted(ranked, key=lambda r: (-r["monetary"], -(r["frequency"])))[:20]
    at_risk = sorted(
        [r for r in ranked if r["churn"]["band"] in {"high", "medium"}],
        key=lambda r: (-r["churn"]["score"], -r["monetary"]),
    )[:20]
    promotions = [
        {
            "customer_id": r["customer_id"],
            "name": r["name"],
            **r["promotion"],
            "churn_band": r["churn"]["band"],
        }
        for r in (at_risk[:10] + [b for b in best if b["churn"]["band"] == "low"][:5])
    ]

    return {
        "generated_at": now,
        "lookback_days": lookback_days,
        "method": "rules_v1",
        "customer_count": len(ranked),
        "best_customers": best,
        "churn_risks": at_risk,
        "promotion_suggestions": promotions,
    }


async def assist_customer(
    db: AsyncSession,
    tenant_id: str,
    *,
    customer_id: str | None = None,
    query: str | None = None,
    company_id: str | None = None,
) -> dict:
    q = (query or "").strip()
    intel = await customer_intelligence(db, tenant_id, company_id=company_id)

    if customer_id:
        party_stmt = select(m.Party).where(
            m.Party.id == customer_id,
            m.Party.tenant_id == tenant_id,
            m.Party.kind == "customer",
        )
        party_stmt = apply_company_filter(party_stmt, m.Party.company_id, company_id)
        party = (await db.execute(party_stmt)).scalar_one_or_none()
        if not party:
            raise HTTPException(status_code=404, detail="Customer not found")
        profile = next((c for c in intel["best_customers"] + intel["churn_risks"] if c["customer_id"] == customer_id), None)
        if profile is None:
            # customer with no lookback sales
            profile = {
                "customer_id": party.id,
                "name": party.name,
                "balance": float(party.balance or 0),
                "credit_limit": float(party.credit_limit or 0),
                "monetary": 0,
                "frequency": 0,
                "recency_days": None,
                "churn": _churn_score(recency_days=None, frequency=0, monetary=0),
                "open_invoice_balance": float(party.balance or 0),
            }
            profile["promotion"] = _promotion_for(profile)

        answer = None
        if re.search(r"\b(balance|outstanding|owe|owing|due)\b", q.lower() or "balance"):
            answer = (
                f"{party.name} has outstanding balance {profile.get('open_invoice_balance', profile.get('balance', 0)):.2f} "
                f"(credit limit {float(party.credit_limit or 0):.2f})."
            )
        elif re.search(r"\b(churn|risk|inactive)\b", q.lower()):
            answer = (
                f"Churn risk for {party.name} is {profile['churn']['band']} "
                f"(score {profile['churn']['score']})."
            )
        elif re.search(r"\b(promo|promotion|discount|offer)\b", q.lower()):
            promo = profile.get("promotion") or _promotion_for(profile)
            answer = f"{promo['label']}: {promo['suggestion']}"
        else:
            answer = (
                f"{party.name}: spend {profile.get('monetary', 0):.2f} in lookback, "
                f"churn {profile['churn']['band']}, "
                f"suggested action — {(profile.get('promotion') or {}).get('suggestion', 'n/a')}."
            )
        return {
            "generated_at": intel["generated_at"],
            "method": "rules_v1",
            "customer": profile,
            "answer": answer,
            "query": q or None,
        }

    # Portfolio-level assist
    if re.search(r"\bbest\b|\btop\b|\bchampion", q.lower() if q else "best"):
        answer = "Top customers by spend: " + ", ".join(
            f"{c['name']} ({c['monetary']:.2f})" for c in intel["best_customers"][:5]
        ) or "No customers with sales in the lookback window."
    elif re.search(r"\bchurn\b|\bat\s*risk\b|\binactive\b", q.lower() if q else ""):
        answer = "Highest churn risks: " + ", ".join(
            f"{c['name']} ({c['churn']['band']})" for c in intel["churn_risks"][:5]
        ) or "No elevated churn risks detected."
    else:
        answer = (
            f"{intel['customer_count']} active customers analysed. "
            f"{len(intel['churn_risks'])} at medium/high churn risk. "
            f"Top spender: {intel['best_customers'][0]['name'] if intel['best_customers'] else 'n/a'}."
        )

    return {
        "generated_at": intel["generated_at"],
        "method": "rules_v1",
        "answer": answer,
        "query": q or None,
        "best_customers": intel["best_customers"][:10],
        "churn_risks": intel["churn_risks"][:10],
        "promotion_suggestions": intel["promotion_suggestions"][:10],
    }
