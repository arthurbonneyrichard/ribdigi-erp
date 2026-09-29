from pathlib import Path

p = Path("backend/app/credit.py")
text = p.read_text(encoding="utf-8")

old_credit = '''    invoices = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.supplier_id == supplier_id,
                m.PurchaseInvoice.status.in_(["unpaid", "partial", "overdue"]),
            )
        )
    ).scalars().all()
    orders = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.supplier_id == supplier_id,
                m.PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
            )
        )
    ).scalars().all()

    open_bills: list[dict] = []
    open_total = 0.0
    for inv in invoices:
        due = max(money_json(inv.total_amount) - money_json(inv.paid_amount), 0)
        if due <= 0:
            continue
        open_total += due
        open_bills.append(
            {
                "document_type": "purchase_invoice",
                "purchase_invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "purchase_order_id": inv.purchase_order_id,
                "amount": money_json(round(due, 2)),
                "due_date": inv.due_date,
                "status": inv.status,
            }
        )
    invoiced_pos = {i.purchase_order_id for i in invoices if i.purchase_order_id}
    for po in orders:
        if po.id in invoiced_pos:
            continue
        due = max(money_json(po.total_amount) - money_json(po.paid_amount), 0)
        if due <= 0:
            continue
        open_total += due
        open_bills.append(
            {
                "document_type": "purchase_order",
                "purchase_order_id": po.id,
                "po_number": po.po_number,
                "amount": money_json(round(due, 2)),
                "due_date": po.due_date,
                "status": po.status,
            }
        )

    # Live open documents — party.balance can be stale after payments.
    outstanding = money_json(round(open_total, 2))

    return {
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "email": getattr(supplier, "email", None),
            "phone": getattr(supplier, "phone", None),
            "payment_terms_days": getattr(supplier, "payment_terms_days", None),
        },
        "outstanding_balance": money_json(round(outstanding, 2)),
        "party_balance": money_json(supplier.balance or 0),
        "open_bill_count": len(open_bills),
        "open_bill_total": money_json(round(open_total, 2)),
        "open_bills": open_bills,
    }
'''

new_credit = '''    from app.purchasing import PURCHASE_INVOICE_OPEN

    invoices = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.supplier_id == supplier_id,
                m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
            )
        )
    ).scalars().all()
    orders = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.supplier_id == supplier_id,
                m.PurchaseOrder.status.in_(list(OPEN_PO_STATUSES)),
            )
        )
    ).scalars().all()
    remaining_credit = await _posted_return_credit_by_po(db, tenant_id)

    open_bills: list[dict] = []
    open_total = 0.0
    for inv in invoices:
        due = max(money_json(inv.total_amount) - money_json(inv.paid_amount), 0)
        due = _apply_po_return_credit(due, inv.purchase_order_id, remaining_credit)
        if due <= 0:
            continue
        open_total += due
        open_bills.append(
            {
                "document_type": "purchase_invoice",
                "purchase_invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "purchase_order_id": inv.purchase_order_id,
                "total_amount": money_json(inv.total_amount),
                "paid_amount": money_json(inv.paid_amount),
                "amount": money_json(round(due, 2)),
                "due_date": inv.due_date,
                "status": inv.status,
            }
        )
    invoiced_pos = {i.purchase_order_id for i in invoices if i.purchase_order_id}
    open_commitments: list[dict] = []
    commitment_total = 0.0
    for po in orders:
        if po.id in invoiced_pos:
            continue
        due = max(money_json(po.total_amount) - money_json(po.paid_amount), 0)
        if due <= 0:
            continue
        commitment_total += due
        open_commitments.append(
            {
                "document_type": "purchase_order",
                "purchase_order_id": po.id,
                "po_number": po.po_number,
                "amount": money_json(round(due, 2)),
                "due_date": po.due_date,
                "status": po.status,
            }
        )

    outstanding = money_json(round(open_total, 2))

    return {
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "email": getattr(supplier, "email", None),
            "phone": getattr(supplier, "phone", None),
            "payment_terms_days": getattr(supplier, "payment_terms_days", None),
        },
        "outstanding_balance": money_json(round(outstanding, 2)),
        "party_balance": money_json(supplier.balance or 0),
        "open_bill_count": len(open_bills),
        "open_bill_total": money_json(round(open_total, 2)),
        "open_bills": open_bills,
        "commitment_total": money_json(round(commitment_total, 2)),
        "open_commitments": open_commitments,
    }
'''

if old_credit not in text:
    raise SystemExit("supplier_credit_info block not found")
text = text.replace(old_credit, new_credit, 1)

marker = "    items: list[dict] = []\n    for inv in invoices:"
if marker not in text:
    raise SystemExit("items list marker not found")
text = text.replace(
    marker,
    "    items: list[dict] = []\n    commitments: list[dict] = []\n    remaining_credit = await _posted_return_credit_by_po(db, tenant_id)\n    for inv in invoices:",
    1,
)

old_bal = '''        balance = max(money_json(inv.total_amount) - money_json(inv.paid_amount or 0), 0)
        if balance <= 0:
            continue
        overdue_days = days_overdue(as_of, inv.due_date, inv.invoice_date or inv.created_at)
'''
new_bal = '''        balance = max(money_json(inv.total_amount) - money_json(inv.paid_amount or 0), 0)
        balance = _apply_po_return_credit(balance, inv.purchase_order_id, remaining_credit)
        if balance <= 0:
            continue
        overdue_days = days_overdue(as_of, inv.due_date, inv.invoice_date or inv.created_at)
'''
if old_bal not in text:
    raise SystemExit("invoice balance block not found")
text = text.replace(old_bal, new_bal, 1)

old_sched = '''        items.append(
            {
                "document_type": "purchase_order",
                "id": po.id,
                "document_number": po.po_number,
                "purchase_order_id": po.id,
                "due_date": po.due_date,
                "balance_due": money_json(round(balance, 2)),
                "status": po.status,
                "days_until_due": days_until,
                "days_overdue": overdue_days,
                "currency": "",
                "early_discount": None,
            }
        )

    def _sort_key(row: dict):
        due = row.get("due_date")
        if due is None:
            return (1, datetime.max, row.get("document_number") or "")
        return (0, due, row.get("document_number") or "")

    items.sort(key=_sort_key)
    upcoming = [r for r in items if (r.get("days_until_due") is None or r["days_until_due"] >= 0)]
    overdue = [r for r in items if r.get("days_until_due") is not None and r["days_until_due"] < 0]

    return {
        "as_of": as_of,
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "balance": money_json(supplier.balance),
        },
        "total_due": money_json(round(sum(r["balance_due"] for r in items), 2)),
        "overdue_count": len(overdue),
        "upcoming_count": len(upcoming),
        "items": items,
    }
'''

new_sched = '''        commitments.append(
            {
                "document_type": "purchase_order",
                "id": po.id,
                "document_number": po.po_number,
                "purchase_order_id": po.id,
                "due_date": po.due_date,
                "balance_due": money_json(round(balance, 2)),
                "status": po.status,
                "days_until_due": days_until,
                "days_overdue": overdue_days,
                "currency": "",
                "early_discount": None,
            }
        )

    def _sort_key(row: dict):
        due = row.get("due_date")
        if due is None:
            return (1, datetime.max, row.get("document_number") or "")
        return (0, due, row.get("document_number") or "")

    items.sort(key=_sort_key)
    upcoming = [r for r in items if (r.get("days_until_due") is None or r["days_until_due"] >= 0)]
    overdue = [r for r in items if r.get("days_until_due") is not None and r["days_until_due"] < 0]
    bill_due = money_json(round(sum(r["balance_due"] for r in items), 2))
    commitment_total = money_json(round(sum(r["balance_due"] for r in commitments), 2))

    return {
        "as_of": as_of,
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "balance": money_json(supplier.balance),
        },
        "total_due": bill_due,
        "commitment_total": commitment_total,
        "overdue_count": len(overdue),
        "upcoming_count": len(upcoming),
        "items": items,
        "commitments": commitments,
    }
'''
if old_sched not in text:
    raise SystemExit("schedule PO block not found")
text = text.replace(old_sched, new_sched, 1)
p.write_text(text, encoding="utf-8")
print("credit info + schedule patched")
