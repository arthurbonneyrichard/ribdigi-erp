"""BusinessMetricsService — deterministic ERP metric calculations (Layer 1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.bi_defaults import (
    APPROVED_EXPENSE_STATUS,
    OPEN_PO_STATUSES,
    OPEN_PR_STATUSES,
    POSTED_PURCHASE_STATUSES,
    POSTED_SALES_STATUSES,
)
from app.reports import apply_company_filter


def _pct_change(current: float, prior: float) -> float | None:
    if prior <= 0:
        return None
    return round(((current - prior) / prior) * 100, 2)


def _day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


def _week_start(now: datetime) -> datetime:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(days=start.weekday())


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class BusinessMetricsService:
    """Pure metric extraction from Ribdigi ERP tables (tenant/company scoped)."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        tenant_id: str,
        company_id: str | None = None,
        store_ids: list[str] | None = None,
        settings: dict | None = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.company_id = company_id
        self.store_ids = store_ids  # None = all; [] = no stores (manager with none)
        self.settings = settings or {}

    def _sales_base(self):
        stmt = select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
            m.SalesInvoice.tenant_id == self.tenant_id,
            m.SalesInvoice.status.in_(list(POSTED_SALES_STATUSES)),
        )
        stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, self.company_id)
        if self.store_ids is not None:
            if not self.store_ids:
                return None  # sentinel: zero
            stmt = stmt.where(m.SalesInvoice.store_id.in_(self.store_ids))
        return stmt

    async def _sales_sum(self, start: datetime, end: datetime) -> float:
        base = self._sales_base()
        if base is None:
            return 0.0
        stmt = base.where(
            m.SalesInvoice.created_at >= start,
            m.SalesInvoice.created_at < end,
        )
        return float((await self.db.execute(stmt)).scalar_one() or 0)

    async def _sales_count(self, start: datetime, end: datetime) -> int:
        stmt = select(func.count(m.SalesInvoice.id)).where(
            m.SalesInvoice.tenant_id == self.tenant_id,
            m.SalesInvoice.status.in_(list(POSTED_SALES_STATUSES)),
            m.SalesInvoice.created_at >= start,
            m.SalesInvoice.created_at < end,
        )
        stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, self.company_id)
        if self.store_ids is not None:
            if not self.store_ids:
                return 0
            stmt = stmt.where(m.SalesInvoice.store_id.in_(self.store_ids))
        return int((await self.db.execute(stmt)).scalar_one() or 0)

    async def _expense_sum(self, start: datetime, end: datetime) -> float:
        stmt = select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
            m.Expense.tenant_id == self.tenant_id,
            m.Expense.status == APPROVED_EXPENSE_STATUS,
            m.Expense.expense_date >= start,
            m.Expense.expense_date < end,
        )
        stmt = apply_company_filter(stmt, m.Expense.company_id, self.company_id)
        return float((await self.db.execute(stmt)).scalar_one() or 0)

    async def _purchase_sum(self, start: datetime, end: datetime) -> float:
        stmt = select(func.coalesce(func.sum(m.PurchaseInvoice.total_amount), 0)).where(
            m.PurchaseInvoice.tenant_id == self.tenant_id,
            m.PurchaseInvoice.status.in_(list(POSTED_PURCHASE_STATUSES)),
            m.PurchaseInvoice.invoice_date >= start,
            m.PurchaseInvoice.invoice_date < end,
        )
        stmt = apply_company_filter(stmt, m.PurchaseInvoice.company_id, self.company_id)
        return float((await self.db.execute(stmt)).scalar_one() or 0)

    async def sales_overview(self, now: datetime | None = None) -> dict:
        now = now or datetime.utcnow()
        today_start, _ = _day_bounds(now)
        yesterday_start = today_start - timedelta(days=1)
        week_start = _week_start(now)
        last_week_start = week_start - timedelta(days=7)
        month_start = _month_start(now)
        if month_start.month == 1:
            prior_month_start = month_start.replace(year=month_start.year - 1, month=12)
        else:
            prior_month_start = month_start.replace(month=month_start.month - 1)
        # last month end = this month start
        days_in_month = max((now - month_start).days, 1)

        today = await self._sales_sum(today_start, now + timedelta(seconds=1))
        yesterday = await self._sales_sum(yesterday_start, today_start)
        this_week = await self._sales_sum(week_start, now + timedelta(seconds=1))
        last_week = await self._sales_sum(last_week_start, week_start)
        this_month = await self._sales_sum(month_start, now + timedelta(seconds=1))
        last_month = await self._sales_sum(prior_month_start, month_start)
        tx_count = await self._sales_count(month_start, now + timedelta(seconds=1))
        avg_tx = round(this_month / tx_count, 2) if tx_count else 0.0
        avg_daily = round(this_month / days_in_month, 2)

        return {
            "as_of": now.isoformat(),
            "today": today,
            "yesterday": yesterday,
            "this_week": this_week,
            "last_week": last_week,
            "this_month": this_month,
            "last_month": last_month,
            "dod_change_pct": _pct_change(today, yesterday),
            "wow_change_pct": _pct_change(this_week, last_week),
            "mom_change_pct": _pct_change(this_month, last_month),
            "avg_daily_sales": avg_daily,
            "avg_transaction_value": avg_tx,
            "transaction_count_mtd": tx_count,
            "filters": {
                "tenant_id": self.tenant_id,
                "company_id": self.company_id,
                "store_ids": self.store_ids,
            },
            "data_source": "sales_invoices (posted/sent/partial/paid/overdue)",
        }

    async def top_products(self, *, days: int = 30, limit: int = 10) -> list[dict]:
        now = datetime.utcnow()
        start = now - timedelta(days=days)
        stmt = (
            select(
                m.SalesInvoiceItem.product_id,
                m.Product.name,
                m.Product.sku,
                func.coalesce(func.sum(m.SalesInvoiceItem.quantity), 0).label("qty"),
                func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).label("revenue"),
            )
            .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
            .join(m.Product, m.Product.id == m.SalesInvoiceItem.product_id)
            .where(
                m.SalesInvoice.tenant_id == self.tenant_id,
                m.SalesInvoice.status.in_(list(POSTED_SALES_STATUSES)),
                m.SalesInvoice.created_at >= start,
            )
            .group_by(m.SalesInvoiceItem.product_id, m.Product.name, m.Product.sku)
            .order_by(func.sum(m.SalesInvoiceItem.line_total).desc())
            .limit(limit)
        )
        stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, self.company_id)
        if self.store_ids is not None:
            if not self.store_ids:
                return []
            stmt = stmt.where(m.SalesInvoice.store_id.in_(self.store_ids))
        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "product_id": r.product_id,
                "name": r.name,
                "sku": r.sku,
                "qty": float(r.qty or 0),
                "revenue": float(r.revenue or 0),
            }
            for r in rows
        ]

    async def profit_overview(self, *, days: int = 30) -> dict:
        """Revenue / COGS / gross profit from invoice lines × product.cost_price."""
        now = datetime.utcnow()
        start = now - timedelta(days=days)
        prior_start = start - timedelta(days=days)

        async def _period(a: datetime, b: datetime) -> dict:
            stmt = (
                select(
                    func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0),
                    func.coalesce(
                        func.sum(m.SalesInvoiceItem.quantity * m.Product.cost_price), 0
                    ),
                    func.count(m.SalesInvoiceItem.id),
                )
                .select_from(m.SalesInvoiceItem)
                .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
                .join(m.Product, m.Product.id == m.SalesInvoiceItem.product_id)
                .where(
                    m.SalesInvoice.tenant_id == self.tenant_id,
                    m.SalesInvoice.status.in_(list(POSTED_SALES_STATUSES)),
                    m.SalesInvoice.created_at >= a,
                    m.SalesInvoice.created_at < b,
                )
            )
            stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, self.company_id)
            if self.store_ids is not None:
                if not self.store_ids:
                    return {
                        "revenue": 0.0,
                        "cogs": 0.0,
                        "gross_profit": 0.0,
                        "gross_margin_pct": None,
                        "lines_missing_cost": 0,
                    }
                stmt = stmt.where(m.SalesInvoice.store_id.in_(self.store_ids))
            rev, cogs, _n = (await self.db.execute(stmt)).one()
            revenue = float(rev or 0)
            cogs_f = float(cogs or 0)
            gp = round(revenue - cogs_f, 2)
            margin = round((gp / revenue) * 100, 2) if revenue > 0 else None
            # Approximate incomplete cost when COGS is zero but revenue exists
            missing = 1 if revenue > 0 and cogs_f <= 0 else 0
            return {
                "revenue": revenue,
                "cogs": cogs_f,
                "gross_profit": gp,
                "gross_margin_pct": margin,
                "lines_missing_cost": missing,
            }

        current = await _period(start, now + timedelta(seconds=1))
        prior = await _period(prior_start, start)
        expenses = await self._expense_sum(start, now + timedelta(seconds=1))
        prior_expenses = await self._expense_sum(prior_start, start)
        net = round(current["gross_profit"] - expenses, 2)
        prior_net = round(prior["gross_profit"] - prior_expenses, 2)
        return {
            "period_days": days,
            "current": {**current, "expenses": expenses, "net_profit": net},
            "prior": {**prior, "expenses": prior_expenses, "net_profit": prior_net},
            "revenue_change_pct": _pct_change(current["revenue"], prior["revenue"]),
            "gross_profit_change_pct": _pct_change(
                current["gross_profit"], prior["gross_profit"]
            ),
            "net_profit_change_pct": _pct_change(net, prior_net),
            "cost_data_incomplete": current["lines_missing_cost"] > 0,
            "data_source": "sales_invoice_items × products.cost_price; expenses (approved)",
            "formula": "gross_profit = revenue - cogs; net_profit = gross_profit - approved_expenses",
        }

    async def inventory_overview(self) -> dict:
        stmt = select(m.Product).where(
            m.Product.tenant_id == self.tenant_id,
            m.Product.is_active == True,  # noqa: E712
        )
        stmt = apply_company_filter(stmt, m.Product.company_id, self.company_id)
        products = (await self.db.execute(stmt)).scalars().all()

        low: list[dict] = []
        out: list[dict] = []
        negative: list[dict] = []
        overstock: list[dict] = []
        stock_value = 0.0
        for p in products:
            qty = float(p.stock_qty or 0)
            cost = float(p.cost_price or 0)
            stock_value += qty * cost
            reorder = float(p.reorder_level or 0)
            minimum = float(p.minimum_stock or 0)
            threshold = max(reorder, minimum)
            row = {
                "product_id": p.id,
                "sku": p.sku,
                "name": p.name,
                "stock_qty": qty,
                "reorder_level": reorder,
                "minimum_stock": minimum,
            }
            if qty < 0:
                negative.append(row)
            elif qty <= 0:
                out.append(row)
            elif threshold > 0 and qty <= threshold:
                low.append(row)

        return {
            "product_count": len(products),
            "stock_value": round(stock_value, 2),
            "low_stock_count": len(low),
            "out_of_stock_count": len(out),
            "negative_stock_count": len(negative),
            "low_stock": low[:50],
            "out_of_stock": out[:50],
            "negative_stock": negative[:50],
            "data_source": "products.stock_qty / reorder_level / minimum_stock / cost_price",
        }

    async def product_sales_qty(
        self, product_id: str, *, days: int = 30
    ) -> float:
        now = datetime.utcnow()
        start = now - timedelta(days=days)
        stmt = (
            select(func.coalesce(func.sum(m.SalesInvoiceItem.quantity), 0))
            .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
            .where(
                m.SalesInvoice.tenant_id == self.tenant_id,
                m.SalesInvoice.status.in_(list(POSTED_SALES_STATUSES)),
                m.SalesInvoice.created_at >= start,
                m.SalesInvoiceItem.product_id == product_id,
            )
        )
        stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, self.company_id)
        return float((await self.db.execute(stmt)).scalar_one() or 0)

    async def reorder_recommendations(self, *, limit: int = 25) -> list[dict]:
        """Smart Reorder Recommendation — deterministic velocity + thresholds (not ML)."""
        inv = await self.inventory_overview()
        candidates = inv["low_stock"] + inv["out_of_stock"]
        lead = int(self.settings.get("default_lead_time_days", 7))
        safety = int(self.settings.get("safety_stock_days", 7))
        period = 30
        unique: list[dict] = []
        seen: set[str] = set()
        for row in candidates:
            pid = row["product_id"]
            if pid in seen:
                continue
            seen.add(pid)
            unique.append(row)
        incoming_map = await self.pending_incoming_qty([r["product_id"] for r in unique])

        results = []
        for row in unique:
            pid = row["product_id"]
            qty_sold = await self.product_sales_qty(pid, days=period)
            avg_daily = qty_sold / period if period else 0.0
            stock = float(row["stock_qty"])
            incoming = float(incoming_map.get(pid) or 0)
            days_remaining = (
                round(stock / avg_daily, 1) if avg_daily > 0 else None
            )
            target = avg_daily * (lead + safety) if avg_daily > 0 else float(
                row.get("reorder_level") or row.get("minimum_stock") or 0
            )
            recommended = max(0, ceil(target - stock - incoming))
            if recommended <= 0:
                continue
            results.append(
                {
                    **row,
                    "avg_daily_sales_qty": round(avg_daily, 3),
                    "qty_sold_last_days": qty_sold,
                    "period_days": period,
                    "estimated_days_remaining": days_remaining,
                    "lead_time_days": lead,
                    "safety_stock_days": safety,
                    "pending_incoming_qty": round(incoming, 3),
                    "recommended_reorder_qty": int(recommended),
                    "label": "Smart Reorder Recommendation",
                    "not_ml_prediction": True,
                }
            )
            if len(results) >= limit:
                break
        await self._attach_last_suppliers(results)
        return results

    async def pending_incoming_qty(self, product_ids: list[str]) -> dict[str, float]:
        """Open PO remaining qty (sent / partially received) per product."""
        if not product_ids:
            return {}
        remaining = m.PurchaseOrderItem.quantity - func.coalesce(
            m.PurchaseOrderItem.received_qty, 0
        )
        stmt = (
            select(
                m.PurchaseOrderItem.product_id,
                func.coalesce(func.sum(remaining), 0),
            )
            .join(
                m.PurchaseOrder,
                m.PurchaseOrder.id == m.PurchaseOrderItem.purchase_order_id,
            )
            .where(
                m.PurchaseOrder.tenant_id == self.tenant_id,
                m.PurchaseOrder.status.in_(list(OPEN_PO_STATUSES)),
                m.PurchaseOrderItem.product_id.in_(list(product_ids)),
            )
            .group_by(m.PurchaseOrderItem.product_id)
        )
        stmt = apply_company_filter(stmt, m.PurchaseOrder.company_id, self.company_id)
        return {
            pid: float(qty or 0)
            for pid, qty in (await self.db.execute(stmt)).all()
        }

    async def last_suppliers_for_products(
        self, product_ids: list[str]
    ) -> dict[str, dict]:
        """Most recent non-cancelled PO supplier per product (tenant/company scoped)."""
        if not product_ids:
            return {}
        stmt = (
            select(
                m.PurchaseOrderItem.product_id,
                m.PurchaseOrder.supplier_id,
                m.PurchaseOrder.created_at,
                m.Party.name,
            )
            .join(
                m.PurchaseOrder,
                m.PurchaseOrder.id == m.PurchaseOrderItem.purchase_order_id,
            )
            .join(m.Party, m.Party.id == m.PurchaseOrder.supplier_id)
            .where(
                m.PurchaseOrder.tenant_id == self.tenant_id,
                m.PurchaseOrderItem.product_id.in_(list(product_ids)),
                m.PurchaseOrder.status != "cancelled",
            )
        )
        stmt = apply_company_filter(stmt, m.PurchaseOrder.company_id, self.company_id)
        best: dict[str, tuple] = {}
        for pid, sid, created, name in (await self.db.execute(stmt)).all():
            prev = best.get(pid)
            if prev is None or (created and created > prev[0]):
                best[pid] = (created, sid, name)
        return {
            pid: {"supplier_id": sid, "supplier_name": name}
            for pid, (_, sid, name) in best.items()
        }

    async def _attach_last_suppliers(self, rows: list[dict]) -> None:
        mapping = await self.last_suppliers_for_products(
            [r["product_id"] for r in rows if r.get("product_id")]
        )
        for row in rows:
            info = mapping.get(row.get("product_id") or "")
            row["last_supplier_id"] = info["supplier_id"] if info else None
            row["last_supplier_name"] = info["supplier_name"] if info else None

    async def open_purchase_request_product_ids(
        self, product_ids: list[str]
    ) -> set[str]:
        """Products already on a draft/pending/approved purchase request."""
        if not product_ids:
            return set()
        stmt = (
            select(m.PurchaseRequestItem.product_id)
            .join(
                m.PurchaseRequest,
                m.PurchaseRequest.id == m.PurchaseRequestItem.purchase_request_id,
            )
            .where(
                m.PurchaseRequest.tenant_id == self.tenant_id,
                m.PurchaseRequest.status.in_(list(OPEN_PR_STATUSES)),
                m.PurchaseRequestItem.product_id.in_(list(product_ids)),
            )
        )
        stmt = apply_company_filter(stmt, m.PurchaseRequest.company_id, self.company_id)
        return set((await self.db.execute(stmt)).scalars().all())

    async def expiry_overview(self) -> dict:
        now = datetime.utcnow()
        windows = list(self.settings.get("expiry_warning_days") or [7, 30, 60])
        stmt = select(m.ProductBatch).where(
            m.ProductBatch.tenant_id == self.tenant_id,
            m.ProductBatch.expiry_date.is_not(None),
        )
        stmt = apply_company_filter(stmt, m.ProductBatch.company_id, self.company_id)
        batches = (await self.db.execute(stmt)).scalars().all()

        expired = []
        by_window: dict[int, list] = {int(w): [] for w in windows}
        value_at_risk = 0.0
        qty_at_risk = 0.0

        # cost lookup
        product_ids = {b.product_id for b in batches}
        costs: dict[str, float] = {}
        if product_ids:
            prow = (
                await self.db.execute(
                    select(m.Product.id, m.Product.cost_price, m.Product.name, m.Product.sku).where(
                        m.Product.id.in_(list(product_ids))
                    )
                )
            ).all()
            names = {r.id: (r.name, r.sku) for r in prow}
            costs = {r.id: float(r.cost_price or 0) for r in prow}
        else:
            names = {}

        for b in batches:
            exp = b.expiry_date
            if not exp:
                continue
            qty = float(getattr(b, "quantity", None) or getattr(b, "qty", None) or 0)
            # ProductBatch may use different qty field — check model
            cost = costs.get(b.product_id, 0.0)
            name, sku = names.get(b.product_id, (b.product_id, ""))
            row = {
                "batch_id": b.id,
                "product_id": b.product_id,
                "name": name,
                "sku": sku,
                "expiry_date": exp.isoformat() if hasattr(exp, "isoformat") else str(exp),
                "quantity": qty,
                "value": round(qty * cost, 2),
            }
            if exp < now:
                expired.append(row)
                qty_at_risk += qty
                value_at_risk += qty * cost
                continue
            days_left = (exp.date() - now.date()).days
            for w in sorted(by_window.keys()):
                if days_left <= w:
                    by_window[w].append(row)
                    qty_at_risk += qty
                    value_at_risk += qty * cost
                    break

        return {
            "expired_count": len(expired),
            "expired": expired[:50],
            "windows": {
                str(w): {"count": len(rows), "batches": rows[:50]}
                for w, rows in by_window.items()
            },
            "qty_at_risk": round(qty_at_risk, 3),
            "value_at_risk": round(value_at_risk, 2),
            "data_source": "product_batches.expiry_date",
        }

    async def expense_overview(self) -> dict:
        now = datetime.utcnow()
        today_start, _ = _day_bounds(now)
        week_start = _week_start(now)
        month_start = _month_start(now)
        if month_start.month == 1:
            prior_month_start = month_start.replace(year=month_start.year - 1, month=12)
        else:
            prior_month_start = month_start.replace(month=month_start.month - 1)

        today = await self._expense_sum(today_start, now + timedelta(seconds=1))
        this_week = await self._expense_sum(week_start, now + timedelta(seconds=1))
        this_month = await self._expense_sum(month_start, now + timedelta(seconds=1))
        last_month = await self._expense_sum(prior_month_start, month_start)
        sales_mtd = await self._sales_sum(month_start, now + timedelta(seconds=1))
        ratio = round((this_month / sales_mtd) * 100, 2) if sales_mtd > 0 else None

        # by category
        stmt = (
            select(
                m.Expense.category_id,
                m.ExpenseCategory.name,
                func.coalesce(func.sum(m.Expense.amount), 0),
            )
            .outerjoin(m.ExpenseCategory, m.ExpenseCategory.id == m.Expense.category_id)
            .where(
                m.Expense.tenant_id == self.tenant_id,
                m.Expense.status == APPROVED_EXPENSE_STATUS,
                m.Expense.expense_date >= month_start,
            )
            .group_by(m.Expense.category_id, m.ExpenseCategory.name)
            .order_by(func.sum(m.Expense.amount).desc())
            .limit(10)
        )
        stmt = apply_company_filter(stmt, m.Expense.company_id, self.company_id)
        cats = [
            {"category_id": r[0], "name": r[1] or "Uncategorized", "amount": float(r[2] or 0)}
            for r in (await self.db.execute(stmt)).all()
        ]

        return {
            "today": today,
            "this_week": this_week,
            "this_month": this_month,
            "last_month": last_month,
            "mom_change_pct": _pct_change(this_month, last_month),
            "expense_to_sales_pct": ratio,
            "by_category": cats,
            "data_source": "expenses (status=approved)",
        }

    async def purchase_overview(self, *, days: int = 30) -> dict:
        now = datetime.utcnow()
        start = now - timedelta(days=days)
        prior_start = start - timedelta(days=days)
        current = await self._purchase_sum(start, now + timedelta(seconds=1))
        prior = await self._purchase_sum(prior_start, start)

        stmt = (
            select(
                m.PurchaseInvoice.supplier_id,
                m.Party.name,
                func.coalesce(func.sum(m.PurchaseInvoice.total_amount), 0),
            )
            .join(m.Party, m.Party.id == m.PurchaseInvoice.supplier_id)
            .where(
                m.PurchaseInvoice.tenant_id == self.tenant_id,
                m.PurchaseInvoice.status.in_(list(POSTED_PURCHASE_STATUSES)),
                m.PurchaseInvoice.invoice_date >= start,
            )
            .group_by(m.PurchaseInvoice.supplier_id, m.Party.name)
            .order_by(func.sum(m.PurchaseInvoice.total_amount).desc())
            .limit(10)
        )
        stmt = apply_company_filter(stmt, m.PurchaseInvoice.company_id, self.company_id)
        suppliers = [
            {
                "supplier_id": r[0],
                "name": r[1],
                "amount": float(r[2] or 0),
                "share_pct": round((float(r[2] or 0) / current) * 100, 1) if current > 0 else None,
            }
            for r in (await self.db.execute(stmt)).all()
        ]
        return {
            "period_days": days,
            "current": current,
            "prior": prior,
            "change_pct": _pct_change(current, prior),
            "by_supplier": suppliers,
            "data_source": "purchase_invoices",
        }

    async def customer_overview(self, *, days: int = 30) -> dict:
        now = datetime.utcnow()
        start = now - timedelta(days=days)
        cust_stmt = select(func.count(m.Party.id)).where(
            m.Party.tenant_id == self.tenant_id,
            m.Party.kind == "customer",
            m.Party.status == "active",
        )
        cust_stmt = apply_company_filter(cust_stmt, m.Party.company_id, self.company_id)
        total = int((await self.db.execute(cust_stmt)).scalar_one() or 0)

        new_stmt = select(func.count(m.Party.id)).where(
            m.Party.tenant_id == self.tenant_id,
            m.Party.kind == "customer",
            m.Party.created_at >= start,
        )
        new_stmt = apply_company_filter(new_stmt, m.Party.company_id, self.company_id)
        new_n = int((await self.db.execute(new_stmt)).scalar_one() or 0)

        top_stmt = (
            select(
                m.SalesInvoice.customer_id,
                m.Party.name,
                func.coalesce(func.sum(m.SalesInvoice.total_amount), 0),
                func.count(m.SalesInvoice.id),
            )
            .join(m.Party, m.Party.id == m.SalesInvoice.customer_id)
            .where(
                m.SalesInvoice.tenant_id == self.tenant_id,
                m.SalesInvoice.status.in_(list(POSTED_SALES_STATUSES)),
                m.SalesInvoice.created_at >= start,
            )
            .group_by(m.SalesInvoice.customer_id, m.Party.name)
            .order_by(func.sum(m.SalesInvoice.total_amount).desc())
            .limit(10)
        )
        top_stmt = apply_company_filter(top_stmt, m.SalesInvoice.company_id, self.company_id)
        top = [
            {
                "customer_id": r[0],
                "name": r[1],
                "spend": float(r[2] or 0),
                "orders": int(r[3] or 0),
            }
            for r in (await self.db.execute(top_stmt)).all()
        ]
        return {
            "total_customers": total,
            "new_customers": new_n,
            "top_customers": top,
            "period_days": days,
            "data_source": "parties (customer) + sales_invoices",
            "privacy_note": "Dashboard shows aggregate names/spend only; no extra PII fields.",
        }

    async def sales_by_store(self, *, days: int = 30) -> list[dict]:
        now = datetime.utcnow()
        start = now - timedelta(days=days)
        stmt = (
            select(
                m.SalesInvoice.store_id,
                m.Store.name,
                func.coalesce(func.sum(m.SalesInvoice.total_amount), 0),
            )
            .outerjoin(m.Store, m.Store.id == m.SalesInvoice.store_id)
            .where(
                m.SalesInvoice.tenant_id == self.tenant_id,
                m.SalesInvoice.status.in_(list(POSTED_SALES_STATUSES)),
                m.SalesInvoice.created_at >= start,
            )
            .group_by(m.SalesInvoice.store_id, m.Store.name)
            .order_by(func.sum(m.SalesInvoice.total_amount).desc())
        )
        stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, self.company_id)
        if self.store_ids is not None:
            if not self.store_ids:
                return []
            stmt = stmt.where(m.SalesInvoice.store_id.in_(self.store_ids))
        rows = (await self.db.execute(stmt)).all()
        total = sum(float(r[2] or 0) for r in rows) or 0.0
        return [
            {
                "store_id": r[0],
                "name": r[1] or "Unassigned",
                "sales": float(r[2] or 0),
                "share_pct": round((float(r[2] or 0) / total) * 100, 1) if total else None,
            }
            for r in rows
        ]

    async def slow_and_dead_stock(self) -> dict:
        slow_days = int(self.settings.get("slow_moving_days", 30))
        dead_days = int(self.settings.get("dead_stock_days", 60))
        now = datetime.utcnow()
        stmt = select(m.Product).where(
            m.Product.tenant_id == self.tenant_id,
            m.Product.is_active == True,  # noqa: E712
            m.Product.stock_qty > 0,
        )
        stmt = apply_company_filter(stmt, m.Product.company_id, self.company_id)
        products = (await self.db.execute(stmt)).scalars().all()
        slow, dead = [], []
        for p in products:
            qty_slow = await self.product_sales_qty(p.id, days=slow_days)
            qty_dead = await self.product_sales_qty(p.id, days=dead_days)
            row = {
                "product_id": p.id,
                "sku": p.sku,
                "name": p.name,
                "stock_qty": float(p.stock_qty or 0),
            }
            if qty_dead <= 0:
                dead.append({**row, "days_without_sale_at_least": dead_days})
            elif qty_slow <= 0:
                slow.append({**row, "days_without_sale_at_least": slow_days})
        return {
            "slow_moving_days": slow_days,
            "dead_stock_days": dead_days,
            "slow_moving": slow[:50],
            "dead_stock": dead[:50],
            "slow_moving_count": len(slow),
            "dead_stock_count": len(dead),
        }
