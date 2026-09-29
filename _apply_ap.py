from pathlib import Path

p = Path("backend/app/credit.py")
text = p.read_text(encoding="utf-8")
old_imp = """from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
"""
new_imp = """from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer
"""
if old_imp not in text:
    raise SystemExit("imports not found")
text = text.replace(old_imp, new_imp, 1)

old_ar = """    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(["posted", "sent", "partial", "overdue"]),
            )
        )
    ).scalars().all()
"""
new_ar = """    invoices = (
        await db.execute(
            select(m.SalesInvoice)
            .options(defer(m.SalesInvoice.coupon_id))
            .where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(["posted", "sent", "partial", "overdue"]),
            )
        )
    ).scalars().all()
"""
if old_ar not in text:
    raise SystemExit("ar_aging select not found")
text = text.replace(old_ar, new_ar, 1)

start = text.find("async def ap_aging")
end = text.find("async def customer_statement")
if start < 0:
    end = text.find("async def supplier_statement")
assert start > 0 and end > start, (start, end)

helpers = Path("_ap_aging_body.py").read_text(encoding="utf-8")
p.write_text(text[:start] + helpers + text[end:], encoding="utf-8")
print("ap_aging replaced")
