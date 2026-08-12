"""Rule-based AI Customer Assistant (BR-21.9) — churn, best customers, promos.

No LLM. Reuses RFM from ai_sales + Party credit balances.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai as ai_svc
from app import ai_sales as ai_sales_svc
from app import credit as credit_svc
from app import models as m

CHURN_BASE = {
    "champions": 0.08,
    "loyal": 0.12,
    "potential_loyalists": 0.2,
    "promising": 0.28,
    "needs_attention": 0.45,
    "at_risk": 0.72,
    "hibernating": 0.88,
}

PROMO_BY_SEGMENT = {
    "champions": "VIP early-access bundle + loyalty points boost",
    "loyal": "Thank-you multi-buy discount on frequently purchased items",
    "potential_loyalists": "Progressive loyalty tier unlock after next purchase",
    "promising": "Welcome-back coupon on next invoice",
    "needs_attention": "Personalized restock reminder with free delivery threshold",
    "at_risk": "Win-back 15% off next order (time-limited)",
    "hibernating": "Reactivation offer: sample pack + deep discount",
}


def churn_score(row: dict[str, Any]) -> dict[str, Any]:
    segment = row.get("segment") or "needs_attention"
    base = CHURN_BASE.get(segment, 0.5)
    recency = int(row.get("recency_days") or 0)
    # Older recency increases risk
    bump = min(0.25, recency / 365.0)
    score = round(min(0.99, base + bump * 0.5), 3)
    if score >= 0.7:
        level = "high"
    elif score >= 0.4:
        level = "medium"
    else:
        level = "low"
    return {
        "customer_id": row["customer_id"],
        "customer_name": row.get("customer_name"),
        "segment": segment,
        "recency_days": recency,
        "churn_risk": score,
        "risk_level": level,
    }


def promotion_for(
    row: dict[str, Any],
    *,
    purchased_ids: set[str],
    affinity: list[dict[str, Any]],
    products: dict[str, m.Product],
) -> dict[str, Any]:
    segment = row.get("segment") or "needs_attention"
    suggestion = PROMO_BY_SEGMENT.get(segment, "Seasonal catalog highlight")
    # Affinity: suggest partner SKU not yet bought
    suggested_products: list[dict[str, Any]] = []
    for pair in affinity:
        a = pair["product_a"]["id"]
        b = pair["product_b"]["id"]
        if a in purchased_ids and b not in purchased_ids:
            p = products.get(b)
            if p:
                suggested_products.append({"product_id": b, "sku": p.sku, "name": p.name})
        elif b in purchased_ids and a not in purchased_ids:
            p = products.get(a)
            if p:
                suggested_products.append({"product_id": a, "sku": p.sku, "name": p.name})
        if len(suggested_products) >= 3:
            break
    return {
        "customer_id": row["customer_id"],
        "customer_name": row.get("customer_name"),
        "segment": segment,
        "promotion": suggestion,
        "suggested_products": suggested_products,
    }


def _query_intent(query: str | None) -> str:
    q = (query or "").strip().lower()
    if not q:
        return "overview"
    if re.search(r"\b(balance|outstanding|owing|ar|credit)\b", q):
        return "balance"
    if re.search(r"\b(churn|risk|leave|attrition)\b", q):
        return "churn"
    if re.search(r"\b(best|top|champion|vip)\b", q):
        return "best"
    if re.search(r"\b(promo|promotion|offer|discount|suggest)\b", q):
        return "promo"
    return "overview"


async def customer_assist(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    customer_id: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    if query:
        injection = ai_svc.find_injection(query)
        if injection:
            raise HTTPException(status_code=400, detail="Query rejected by AI prompt safety controls")
        if len(query) > ai_svc.max_message_chars():
            raise HTTPException(status_code=400, detail="query too long")

    intent = _query_intent(query)
    now = datetime.utcnow()
    start = now - timedelta(days=180)
    baskets = await ai_sales_svc._invoice_baskets(db, tenant_id, start=start, end=now)
    rfm_rows, segment_counts = await ai_sales_svc.build_rfm(
        db, tenant_id, baskets=baskets, start=start, end=now
    )

    # Affinity pairs for promo SKU suggestions
    from collections import Counter
    from itertools import combinations

    pair_counts: Counter[tuple[str, str]] = Counter()
    for b in baskets:
        ids = sorted(b.get("product_ids") or [])
        for a, c in combinations(ids, 2):
            pair_counts[(a, c)] += 1
    top_pairs = pair_counts.most_common(20)
    product_ids = {pid for pair, _ in top_pairs for pid in pair}
    # also products bought by focus customer
    focus_purchased: set[str] = set()
    if customer_id:
        for b in baskets:
            if b.get("customer_id") == customer_id:
                focus_purchased |= set(b.get("product_ids") or [])
        product_ids |= focus_purchased
    products: dict[str, m.Product] = {}
    if product_ids:
        for p in (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id, m.Product.id.in_(list(product_ids))
                )
            )
        ).scalars().all():
            products[p.id] = p
    affinity = [
        {
            "product_a": {
                "id": a,
                "sku": getattr(products.get(a), "sku", None),
                "name": getattr(products.get(a), "name", None),
            },
            "product_b": {
                "id": b,
                "sku": getattr(products.get(b), "sku", None),
                "name": getattr(products.get(b), "name", None),
            },
            "together_count": cnt,
        }
        for (a, b), cnt in top_pairs
    ]

    churn_rows = [churn_score(r) for r in rfm_rows]
    churn_rows.sort(key=lambda x: -x["churn_risk"])
    best = [
        {
            **r,
            "score": r["r"] + r["f"] + r["m"],
            "reason": "high RFM composite",
        }
        for r in rfm_rows
        if r["segment"] in {"champions", "loyal"} or (r["r"] + r["f"] + r["m"]) >= 12
    ][:20]
    if not best:
        best = [{**r, "score": r["r"] + r["f"] + r["m"], "reason": "top monetary"} for r in rfm_rows[:5]]

    # Promotions for all or focus customer
    promo_targets = rfm_rows
    if customer_id:
        promo_targets = [r for r in rfm_rows if r["customer_id"] == customer_id]
    promotions = [
        promotion_for(
            r,
            purchased_ids=focus_purchased if customer_id == r["customer_id"] else set(),
            affinity=affinity,
            products=products,
        )
        for r in promo_targets[:30]
    ]

    answer = None
    customer_pack = None
    if customer_id:
        try:
            stmt = await credit_svc.customer_statement(db, tenant_id, customer_id)
        except HTTPException:
            raise
        customer_pack = {
            "customer": stmt["customer"],
            "open_balance": float(stmt["customer"].get("balance") or 0),
            "credit_limit": float(stmt["customer"].get("credit_limit") or 0),
            "rfm": next((r for r in rfm_rows if r["customer_id"] == customer_id), None),
            "churn": next((c for c in churn_rows if c["customer_id"] == customer_id), None),
            "promotion": next((p for p in promotions if p["customer_id"] == customer_id), None),
        }
        if intent == "balance":
            bal = customer_pack["open_balance"]
            lim = customer_pack["credit_limit"]
            answer = (
                f"{stmt['customer']['name']} outstanding balance is {bal:.2f}"
                + (f" (credit limit {lim:.2f})." if lim else ".")
            )
        elif intent == "churn" and customer_pack["churn"]:
            c = customer_pack["churn"]
            answer = (
                f"Churn risk for {stmt['customer']['name']} is {c['churn_risk']} "
                f"({c['risk_level']}, segment={c['segment']})."
            )
        elif intent == "promo" and customer_pack["promotion"]:
            p = customer_pack["promotion"]
            answer = f"Suggested promotion: {p['promotion']}"
        elif intent == "best":
            answer = "Best customers are listed under best_customers (RFM champions/loyal)."
        else:
            answer = (
                f"Customer overview for {stmt['customer']['name']}: "
                f"balance={customer_pack['open_balance']:.2f}, "
                f"segment={(customer_pack['rfm'] or {}).get('segment')}, "
                f"churn={(customer_pack['churn'] or {}).get('churn_risk')}."
            )
    elif intent == "best":
        answer = f"Identified {len(best)} best customer(s) by RFM."
    elif intent == "churn":
        high = sum(1 for c in churn_rows if c["risk_level"] == "high")
        answer = f"{high} customer(s) currently high churn risk."
    elif intent == "promo":
        answer = f"{len(promotions)} promotion suggestion(s) ready."
    else:
        answer = (
            f"Customer intelligence pack: {len(rfm_rows)} customers scored; "
            f"{len(best)} best; {sum(1 for c in churn_rows if c['risk_level']=='high')} high churn."
        )

    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="customer_assist",
        status="ok",
        message=query,
        details={
            "intent": intent,
            "customer_id": customer_id,
            "rfm_count": len(rfm_rows),
            "method": "rule_based_rfm",
        },
    )
    await db.commit()
    return {
        "method": "rule_based_rfm",
        "intent": intent,
        "query": query,
        "answer": answer,
        "customer": customer_pack,
        "churn_risks": churn_rows[:50],
        "best_customers": best,
        "promotions": promotions[:30],
        "segment_counts": segment_counts,
        "lookback_days": 180,
    }
