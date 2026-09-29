OPEN_PO_STATUSES = ("sent", "partially_received", "received")


async def _posted_return_credit_by_po(db: AsyncSession, tenant_id: str) -> dict[str, float]:
    """Posted purchase-return debit notes grouped by PO (credits AP)."""
    rows = (
        await db.execute(
            select(m.PurchaseReturn.purchase_order_id, m.PurchaseReturn.total_amount).where(
                m.PurchaseReturn.tenant_id == tenant_id,
                m.PurchaseReturn.status == "posted",
            )
        )
    ).all()
    out: dict[str, float] = {}
    for po_id, amount in rows:
        if not po_id:
            continue
        out[str(po_id)] = money_json(round(out.get(str(po_id), 0.0) + money_json(amount), 2))
    return out


def _apply_po_return_credit(due: float, po_id: str | None, remaining: dict[str, float]) -> float:
    if due <= 0 or not po_id:
        return money_json(due)
    credit = remaining.get(po_id, 0.0)
    if credit <= 0:
        return money_json(due)
    applied = min(due, credit)
    remaining[po_id] = money_json(round(credit - applied, 2))
    return money_json(round(due - applied, 2))


def _bill_is_overdue(as_of: datetime, due_date: datetime | None) -> bool:
    return bool(due_date and due_date.date() < as_of.date())


async def ap_aging(db: AsyncSession, tenant_id: str, as_of: datetime | None = None) -> dict:
    """Supplier amounts due from billed invoices only.

    Unbilled PO remaining value is returned as open_commitments, not total_due.
    """
    from app.purchasing import PURCHASE_INVOICE_OPEN, refresh_overdue_purchase_invoices

    as_of = as_of or datetime.utcnow()
    await refresh_overdue_purchase_invoices(db, tenant_id, as_of=as_of)

    invoices = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
            )
        )
    ).scalars().all()
    invoiced_po_ids = {i.purchase_order_id for i in invoices if i.purchase_order_id}

    orders = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.status.in_(list(OPEN_PO_STATUSES)),
            )
        )
    ).scalars().all()
    suppliers = {
        p.id: p
        for p in (
            await db.execute(
                select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "supplier")
            )
        ).scalars().all()
    }
    return_credit = await _posted_return_credit_by_po(db, tenant_id)

    by_supplier: dict[str, dict] = {}
    totals = empty_buckets()
    documents: list[dict] = []
    commitments: list[dict] = []
    overdue_total = 0.0
    not_yet_due_total = 0.0

    def _party_row(supplier_id: str) -> dict:
        sup = suppliers.get(supplier_id)
        return by_supplier.setdefault(
            supplier_id,
            {
                "party_id": supplier_id,
                "name": sup.name if sup else supplier_id,
                "credit_limit": money_json(sup.credit_limit) if sup else money_json(0),
                "balance": money_json(sup.balance) if sup else money_json(0),
                "total_due": money_json(0),
                "commitment_total": money_json(0),
                **empty_buckets(),
            },
        )

    remaining_credit = dict(return_credit)
    for inv in invoices:
        due = max(money_json(inv.total_amount) - money_json(inv.paid_amount), 0)
        due = _apply_po_return_credit(due, inv.purchase_order_id, remaining_credit)
        if due <= 0:
            continue
        days = days_overdue(as_of, inv.due_date, inv.invoice_date or inv.created_at)
        bucket = age_bucket(days)
        add_to_bucket(totals, days, due)
        row = _party_row(inv.supplier_id)
        row["total_due"] = money_json(round(row["total_due"] + due, 2))
        row[bucket] = money_json(round(row[bucket] + due, 2))
        if _bill_is_overdue(as_of, inv.due_date):
            overdue_total = money_json(round(overdue_total + due, 2))
        else:
            not_yet_due_total = money_json(round(not_yet_due_total + due, 2))
        paid = money_json(inv.paid_amount)
        documents.append(
            {
                "id": inv.id,
                "document_number": inv.invoice_number,
                "document_type": "purchase_invoice",
                "party_id": inv.supplier_id,
                "party_name": row["name"],
                "invoice_date": inv.invoice_date,
                "due_date": inv.due_date,
                "total_amount": money_json(inv.total_amount),
                "paid_amount": paid,
                "balance_due": money_json(due),
                "status": inv.status,
                "currency": getattr(inv, "currency", None) or "",
                "exchange_rate": money_json(getattr(inv, "exchange_rate", None), default=1.0),
                "balance_due_base": money_json(
                    round(due * money_json(getattr(inv, "exchange_rate", None), default=1.0), 2)
                ),
                "days_overdue": days,
                "bucket": bucket,
            }
        )

    commitment_total = 0.0
    for po in orders:
        if po.id in invoiced_po_ids:
            continue
        due = max(money_json(po.total_amount) - money_json(po.paid_amount), 0)
        if due <= 0:
            continue
        row = _party_row(po.supplier_id)
        row["commitment_total"] = money_json(round(row["commitment_total"] + due, 2))
        commitment_total = money_json(round(commitment_total + due, 2))
        commitments.append(
            {
                "id": po.id,
                "document_number": po.po_number,
                "document_type": "purchase_order",
                "party_id": po.supplier_id,
                "party_name": row["name"],
                "due_date": po.due_date,
                "balance_due": money_json(due),
                "status": po.status,
            }
        )

    total_due = money_json(round(sum(totals.values()), 2))
    return {
        "as_of": as_of,
        "kind": "payable",
        "totals": {k: money_json(v) for k, v in totals.items()},
        "total_due": total_due,
        "overdue_total": money_json(overdue_total),
        "not_yet_due_total": money_json(not_yet_due_total),
        "commitment_total": money_json(commitment_total),
        "parties": sorted(by_supplier.values(), key=lambda x: x["total_due"], reverse=True),
        "documents": documents,
        "commitments": commitments,
    }


