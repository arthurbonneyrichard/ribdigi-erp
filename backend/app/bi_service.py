"""BusinessIntelligenceService — orchestrates metrics, rules, health, persistence."""

from __future__ import annotations

from copy import deepcopy
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.bi_defaults import (
    DEFAULT_SETTINGS,
    FORMULA_DOCS,
    INSIGHT_STATUS_ACKNOWLEDGED,
    INSIGHT_STATUS_ACTIVE,
    INSIGHT_STATUS_DISMISSED,
    PERSIST_PRIORITIES,
    PRIORITY_RANK,
)
from app.bi_metrics import BusinessMetricsService
from app.bi_priority import InsightPriorityService
from app.bi_rules import InsightRulesService
from app.credit import ar_aging
from app.dashboard_scope import managed_store_ids
from app.notifications import create_notification
from app.rbac import has_permission


def merge_settings(stored: dict | None) -> dict:
    base = deepcopy(DEFAULT_SETTINGS)
    if stored:
        for k, v in stored.items():
            if k == "health_weights" and isinstance(v, dict):
                base["health_weights"] = {**base["health_weights"], **v}
            else:
                base[k] = v
    return base


def compute_health_score(
    *,
    sales: dict,
    inventory: dict,
    profit: dict,
    expenses: dict,
    credit: dict | None,
    settings: dict,
) -> dict:
    """Transparent 0–100 health score from documented component formulas."""
    weights = settings.get("health_weights") or DEFAULT_SETTINGS["health_weights"]
    # Sales: MoM change mapped to 0-100 (0% => 70, +20% => 100, -20% => 40)
    mom = sales.get("mom_change_pct")
    if mom is None:
        sales_score = 70
    else:
        sales_score = max(0, min(100, 70 + mom * 1.5))

    # Inventory: penalize low/out/negative
    total_p = max(inventory.get("product_count") or 1, 1)
    bad = (
        (inventory.get("low_stock_count") or 0)
        + (inventory.get("out_of_stock_count") or 0) * 2
        + (inventory.get("negative_stock_count") or 0) * 5
    )
    inventory_score = max(0, min(100, 100 - (bad / total_p) * 100))

    # Profitability: gross margin if available else 70
    gm = (profit.get("current") or {}).get("gross_margin_pct")
    if gm is None:
        profit_score = 70
    else:
        profit_score = max(0, min(100, gm * 2))  # 50% margin => 100

    # Credit: lower score when overdue share high
    if credit and float(credit.get("total_due") or 0) > 0:
        totals = credit.get("totals") or {}
        overdue = float(totals.get("31_60") or 0) + float(totals.get("61_90") or 0) + float(
            totals.get("90_plus") or 0
        )
        share = overdue / float(credit["total_due"])
        credit_score = max(0, min(100, 100 - share * 100))
    else:
        credit_score = 90

    # Expenses: penalize MoM increase and high expense/sales
    exp_mom = expenses.get("mom_change_pct")
    ratio = expenses.get("expense_to_sales_pct")
    exp_score = 85
    if exp_mom is not None and exp_mom > 0:
        exp_score -= min(40, exp_mom)
    if ratio is not None:
        exp_score -= max(0, (ratio - 20) * 1.5)
    exp_score = max(0, min(100, exp_score))

    components = {
        "sales": round(sales_score, 1),
        "inventory": round(inventory_score, 1),
        "profitability": round(profit_score, 1),
        "credit": round(credit_score, 1),
        "expenses": round(exp_score, 1),
    }
    wsum = sum(float(weights.get(k, 0)) for k in components) or 100
    score = round(
        sum(components[k] * float(weights.get(k, 0)) for k in components) / wsum, 1
    )
    if score >= 80:
        status = "Good"
    elif score >= 60:
        status = "Fair"
    elif score >= 40:
        status = "Needs Attention"
    else:
        status = "Critical"

    return {
        "score": score,
        "status": status,
        "breakdown": components,
        "weights": weights,
        "formula": (
            "score = Σ(component_score × weight) / Σ(weights); "
            "sales≈70+1.5×mom%; inventory=100−bad_share; "
            "profitability≈2×gross_margin%; credit=100−overdue_share; "
            "expenses starts 85 minus MoM and expense/sales penalties"
        ),
        "external_ai": False,
    }


class BusinessIntelligenceService:
    def __init__(self, db: AsyncSession, claims: dict):
        self.db = db
        self.claims = claims
        self.tenant_id = claims["tenant_id"]
        self.company_id = claims.get("company_id")
        self.perms = claims.get("permissions") or {}

    def can_read_financial(self) -> bool:
        return has_permission(
            self.claims.get("role"), "accounting", "read", overrides=self.perms
        ) or has_permission(
            self.claims.get("role"), "reports", "read", overrides=self.perms
        )

    def can_read_credit(self) -> bool:
        return has_permission(
            self.claims.get("role"), "credit", "read", overrides=self.perms
        )

    async def load_settings(self) -> dict:
        row = (
            await self.db.execute(
                select(m.BusinessInsightSettings).where(
                    m.BusinessInsightSettings.tenant_id == self.tenant_id,
                    m.BusinessInsightSettings.company_id == self.company_id
                    if self.company_id
                    else m.BusinessInsightSettings.company_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        # Fallback: company-null tenant defaults when company-specific missing
        if row is None and self.company_id:
            row = (
                await self.db.execute(
                    select(m.BusinessInsightSettings).where(
                        m.BusinessInsightSettings.tenant_id == self.tenant_id,
                        m.BusinessInsightSettings.company_id.is_(None),
                    )
                )
            ).scalar_one_or_none()
        return merge_settings(row.settings if row else None)

    async def save_settings(self, patch: dict) -> dict:
        current = await self.load_settings()
        merged = merge_settings({**current, **(patch or {})})
        row = (
            await self.db.execute(
                select(m.BusinessInsightSettings).where(
                    m.BusinessInsightSettings.tenant_id == self.tenant_id,
                    m.BusinessInsightSettings.company_id == self.company_id
                    if self.company_id
                    else m.BusinessInsightSettings.company_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = m.BusinessInsightSettings(
                tenant_id=self.tenant_id,
                company_id=self.company_id,
                settings=merged,
                updated_by=self.claims.get("sub"),
            )
            self.db.add(row)
        else:
            row.settings = merged
            row.updated_at = datetime.utcnow()
            row.updated_by = self.claims.get("sub")
        await self.db.commit()
        await self.db.refresh(row)
        return merge_settings(row.settings)

    async def _metrics(self) -> BusinessMetricsService:
        settings = await self.load_settings()
        store_ids = await managed_store_ids(self.db, self.claims)
        return BusinessMetricsService(
            self.db,
            tenant_id=self.tenant_id,
            company_id=self.company_id,
            store_ids=store_ids,
            settings=settings,
        )

    async def build_bundle(self) -> dict:
        settings = await self.load_settings()
        metrics = await self._metrics()
        sales = await metrics.sales_overview()
        inventory = await metrics.inventory_overview()
        profit = await metrics.profit_overview()
        expenses = await metrics.expense_overview()
        purchases = await metrics.purchase_overview()
        customers = await metrics.customer_overview()
        expiry = await metrics.expiry_overview()
        slow_dead = await metrics.slow_and_dead_stock()
        by_store = await metrics.sales_by_store()
        reorder = await metrics.reorder_recommendations()
        top_products = await metrics.top_products()

        credit = None
        if self.can_read_credit():
            credit = await ar_aging(
                self.db, self.tenant_id, company_id=self.company_id
            )

        rules = InsightRulesService(settings)
        insights = rules.build(
            sales=sales,
            inventory=inventory,
            profit=profit,
            expenses=expenses,
            purchases=purchases,
            credit=credit,
            expiry=expiry,
            slow_dead=slow_dead,
            by_store=by_store,
            reorder=reorder,
            top_products=top_products,
            can_financial=self.can_read_financial(),
            can_credit=self.can_read_credit(),
        )

        health = compute_health_score(
            sales=sales,
            inventory=inventory,
            profit=profit if self.can_read_financial() else {},
            expenses=expenses,
            credit=credit,
            settings=settings,
        )

        attention = [
            i
            for i in insights
            if i["priority"] in ("CRITICAL", "WARNING", "ATTENTION", "OPPORTUNITY")
        ][:12]

        await self._persist_important(insights)
        await self._notify_critical(insights)
        await self.db.commit()

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "external_ai_required": False,
            "internet_required": False,
            "engine": "Smart Business Intelligence Layer 1",
            "health": health,
            "attention": attention,
            "insights": insights,
            "sales": sales,
            "inventory": inventory,
            "profit": profit if self.can_read_financial() else {"restricted": True},
            "expenses": expenses,
            "purchases": purchases,
            "customers": customers,
            "credit": credit if credit is not None else {"restricted": True},
            "expiry": expiry,
            "slow_dead": slow_dead,
            "locations": by_store,
            "reorder_recommendations": reorder,
            "top_products": top_products,
            "opportunities": [i for i in insights if i["priority"] == "OPPORTUNITY"],
            "formulas": FORMULA_DOCS,
            "settings": settings,
        }

    async def _persist_important(self, insights: list[dict]) -> None:
        """Store CRITICAL/WARNING insights; skip duplicates active same type+entity today."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        for item in insights:
            if item.get("priority") not in PERSIST_PRIORITIES:
                continue
            q = select(m.BusinessInsight).where(
                m.BusinessInsight.tenant_id == self.tenant_id,
                m.BusinessInsight.insight_type == item["insight_type"],
                m.BusinessInsight.status == INSIGHT_STATUS_ACTIVE,
                m.BusinessInsight.created_at >= today,
            )
            if self.company_id:
                q = q.where(m.BusinessInsight.company_id == self.company_id)
            if item.get("related_entity_id"):
                q = q.where(
                    m.BusinessInsight.related_entity_id == item["related_entity_id"]
                )
            existing = (await self.db.execute(q)).scalars().first()
            if existing:
                continue
            self.db.add(
                m.BusinessInsight(
                    tenant_id=self.tenant_id,
                    company_id=self.company_id,
                    insight_type=item["insight_type"],
                    category=item["category"],
                    priority=item["priority"],
                    title=item["title"],
                    message=item["message"],
                    recommendation=item.get("recommendation"),
                    metric_value=item.get("metric_value"),
                    comparison_value=item.get("comparison_value"),
                    percentage_change=item.get("percentage_change"),
                    related_entity_type=item.get("related_entity_type"),
                    related_entity_id=item.get("related_entity_id"),
                    action_href=item.get("action_href"),
                    status=INSIGHT_STATUS_ACTIVE,
                )
            )
        await self.db.commit()

    async def _notify_critical(self, insights: list[dict]) -> None:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        for item in insights:
            if item.get("priority") != "CRITICAL":
                continue
            entity_id = item.get("related_entity_id") or item.get("insight_type")
            title = item["title"][:160]
            existing = (
                await self.db.execute(
                    select(m.Notification).where(
                        m.Notification.tenant_id == self.tenant_id,
                        m.Notification.category == "business_insight",
                        m.Notification.status == "unread",
                        m.Notification.entity_id == entity_id,
                        m.Notification.title == title,
                        m.Notification.created_at >= today,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            await create_notification(
                self.db,
                tenant_id=self.tenant_id,
                title=title,
                message=item["message"][:500],
                category="business_insight",
                user_id=self.claims.get("sub")
                if self.claims.get("sub") not in (None, "system")
                else None,
                entity_type=item.get("related_entity_type"),
                entity_id=entity_id,
                company_id=self.company_id,
            )

    async def create_reorder_purchase_requests(
        self,
        *,
        product_ids: list[str] | None = None,
        supplier_id: str | None = None,
        warehouse_id: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Create draft purchase requests from Smart Reorder Recommendations.

        Groups lines by last PO supplier (or an explicit fallback). Skips products
        with no supplier, qty <= 0, or an existing open purchase request.
        """
        from app import purchasing as purchasing_svc

        metrics = await self._metrics()
        recs = await metrics.reorder_recommendations()
        wanted = {pid for pid in (product_ids or []) if pid} or None
        if wanted:
            recs = [r for r in recs if r.get("product_id") in wanted]

        pids = [r["product_id"] for r in recs if r.get("product_id")]
        already = await metrics.open_purchase_request_product_ids(pids)

        skipped: list[dict] = []
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in recs:
            pid = row.get("product_id")
            qty = int(row.get("recommended_reorder_qty") or 0)
            if not pid:
                continue
            if qty <= 0:
                skipped.append({"product_id": pid, "reason": "recommended_qty_zero"})
                continue
            if pid in already:
                skipped.append({"product_id": pid, "reason": "open_purchase_request"})
                continue
            sid = row.get("last_supplier_id") or supplier_id
            if not sid:
                skipped.append({"product_id": pid, "reason": "no_supplier"})
                continue
            grouped[sid].append(
                {
                    "product_id": pid,
                    "quantity": qty,
                    "notes": f"Smart Reorder Recommendation (days left: {row.get('estimated_days_remaining')})",
                }
            )

        created: list[dict] = []
        note = (notes or "").strip() or "Created from Smart Reorder Recommendation"
        for sid, items in grouped.items():
            pr = await purchasing_svc.create_purchase_request(
                self.db,
                tenant_id=self.tenant_id,
                user_id=self.claims.get("sub") or "system",
                supplier_id=sid,
                warehouse_id=warehouse_id,
                notes=note,
                items=items,
                company_id=self.company_id,
            )
            created.append(await purchasing_svc.serialize_pr(self.db, pr))
        await self.db.commit()
        return {
            "created": created,
            "skipped": skipped,
            "created_count": len(created),
            "skipped_count": len(skipped),
            "external_ai_required": False,
        }

    async def list_history(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        q = select(m.BusinessInsight).where(
            m.BusinessInsight.tenant_id == self.tenant_id
        )
        if self.company_id:
            q = q.where(m.BusinessInsight.company_id == self.company_id)
        if status:
            q = q.where(m.BusinessInsight.status == status)
        q = q.order_by(m.BusinessInsight.created_at.desc()).limit(limit)
        rows = (await self.db.execute(q)).scalars().all()
        return [self._row_dict(r) for r in rows]

    async def get_insight(self, insight_id: str) -> m.BusinessInsight | None:
        row = await self.db.get(m.BusinessInsight, insight_id)
        if not row or row.tenant_id != self.tenant_id:
            return None
        if self.company_id and row.company_id and row.company_id != self.company_id:
            return None
        return row

    async def acknowledge(self, insight_id: str) -> dict | None:
        row = await self.get_insight(insight_id)
        if not row:
            return None
        row.status = INSIGHT_STATUS_ACKNOWLEDGED
        row.acknowledged_at = datetime.utcnow()
        row.acknowledged_by = self.claims.get("sub")
        await self.db.commit()
        await self.db.refresh(row)
        return self._row_dict(row)

    async def dismiss(self, insight_id: str) -> dict | None:
        row = await self.get_insight(insight_id)
        if not row:
            return None
        row.status = INSIGHT_STATUS_DISMISSED
        row.resolved_at = datetime.utcnow()
        row.acknowledged_by = self.claims.get("sub")
        await self.db.commit()
        await self.db.refresh(row)
        return self._row_dict(row)

    @staticmethod
    def _row_dict(r: m.BusinessInsight) -> dict:
        return {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "company_id": r.company_id,
            "insight_type": r.insight_type,
            "category": r.category,
            "priority": r.priority,
            "title": r.title,
            "message": r.message,
            "recommendation": r.recommendation,
            "metric_value": float(r.metric_value) if r.metric_value is not None else None,
            "comparison_value": float(r.comparison_value)
            if r.comparison_value is not None
            else None,
            "percentage_change": float(r.percentage_change)
            if r.percentage_change is not None
            else None,
            "related_entity_type": r.related_entity_type,
            "related_entity_id": r.related_entity_id,
            "action_href": r.action_href,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }


async def scan_tenant_business_insights(db: AsyncSession, tenant_id: str) -> dict:
    """Persist Layer 1 CRITICAL/WARNING insights for each active company (scheduled)."""
    companies = (
        await db.execute(
            select(m.Company.id).where(
                m.Company.tenant_id == tenant_id,
                m.Company.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    scanned = 0
    for company_id in companies:
        claims = {
            "tenant_id": tenant_id,
            "company_id": company_id,
            "sub": "system",
            "role": "company_admin",
            "permissions": {"*": ["*"]},
        }
        await BusinessIntelligenceService(db, claims).build_bundle()
        scanned += 1
    return {"companies": scanned, "engine": "Smart Business Intelligence Layer 1"}
