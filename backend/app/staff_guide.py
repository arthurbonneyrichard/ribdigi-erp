"""Staff user guide PDF built from the tenant's industry, modules, and role."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import packages as packages_svc
from app.rbac import permissions_for_role
from app.tenants import INDUSTRY_LABELS
from app.report_export import to_pdf

_INDUSTRY_STEPS: dict[str, list[str]] = {
    "retail": [
        "Sell at POS. Cash, card, wallet, and Mobile Money are recorded payments. A gift card or loyalty points reduce stored value, not the cash drawer. A named customer earns 1% of the sale as points.",
        "Mobile Money stores the amount and reference. It does not collect funds.",
        "Keep stock on the inventory pages. Low stock and product lists are the retail catalog.",
        "Customer credit is money still owed. Record a sale, then record a payment when cash arrives.",
    ],
    "pharmacy": [
        "Dispense from POS and keep batch and expiry dates on inventory.",
        "Rx-only products and the prescription queue are the pharmacy desk.",
        "This guide does not cover diagnosis coding or insurance claims.",
    ],
    "wholesale": [
        "Quote, confirm a sales order, fill quantity, then invoice.",
        "Filled quantity leaves stock. The invoice does not remove that quantity again.",
        "Customer credit follows the posted invoice until a payment is recorded.",
    ],
    "retail_wholesale": [
        "POS is the retail counter. Quotes and sales orders are the wholesale desk.",
        "Both channels share the same catalog and stock.",
        "A retail sale must stay on POS. A wholesale order must stay on the sales desk.",
    ],
    "hotel": [
        "Add rooms and nightly rates, then add a guest and book a stay.",
        "Online booking records an existing website or a new domain. A guest request holds the room as tentative until it is confirmed. The dashboard says how many stay requests are waiting. The request does not take a payment.",
        "Confirm a tentative reservation, then check the guest in at the front desk.",
        "Housekeeping and maintenance stay on the hotel desk. A dirty night is today only.",
        "The room folio is nights times the nightly rate. Record a folio payment, then check out. That payment is a recorded tender, not a card charge.",
        "Hotel reports count nights sold in the selected dates. Reservations, folios, and housekeeping need the internet.",
    ],
    "restaurant": [
        "Save tables, then save an order for dine-in, takeaway, or delivery.",
        "Online booking records an existing website or a new domain. Guests request a table on that link. A time that has already passed is refused. Seating can name a table. Finishing a seated visit frees the table when no open order is using it. The request is not an order and not a payment.",
        "Send the order to the kitchen, then complete it when it is served.",
        "Recipes tie a menu item to ingredients. The restaurant desk needs the internet.",
    ],
}

_MODULE_STEPS: dict[str, str] = {
    "pos": "POS: open a shift, add products, take a recorded payment, and print the receipt.",
    "inventory": "Inventory: products, stock counts, adjustments, and low stock.",
    "sales": "Sales: invoices, and wholesale quotes or orders when that industry is enabled.",
    "purchasing": "Purchasing: suppliers, purchase orders, and goods received.",
    "expenses": "Expenses: pick a category, record the amount and how it was paid, and review paid items.",
    "accounting": "Accounting: journals and the chart of accounts for this company.",
    "credit": "Customer credit: outstanding balances, due dates, and payments. A credit row is not cash received.",
    "reports": "Reports: filter by date and, on a multi-store company, by store. Export uses the same filters.",
    "customers": "Customers: names, balances, and loyalty points.",
    "hotel": "Hotel: reservations, front desk, and folios for a hotel company only.",
    "fmcg": "FMCG: schemes, routes, and deliveries for an FMCG company only.",
    "hospital": "Hospital: patients and visits for a hospital company only. Not a diagnosis or insurance desk.",
}

_HOTEL_MODULE_STEPS: dict[str, str] = {
    "pos": "Shop till: walk-up shop sales for this hotel. Meals and drinks stay on the guest bill. Guest folio payments stay on Billing.",
    "inventory": "Supplies: quantities on hand, counts, and low supplies. Rooms stay on Rooms and rates.",
    "sales": "Sales: the invoice created from a guest folio at checkout. Stays start on Reservations.",
    "purchasing": "Purchasing: suppliers, purchase orders, and supplies received for the hotel.",
    "expenses": "Expenses: hotel costs with a category, an amount, and how they were paid.",
    "accounting": "Accounting: journals for this hotel, including the checkout invoice.",
    "credit": "Customer credit: amounts still owed after checkout. A credit row is not cash received.",
    "reports": "Reports: occupancy and room revenue for the selected dates, plus the company reports.",
    "customers": "Guests and customers: guest profiles on the hotel desk, and the customer used by a checkout invoice.",
    "hotel": "Hotel: rooms, reservations, front desk, housekeeping, maintenance, folios, and cashiering.",
}


def guide_lines(
    *,
    company_name: str,
    industry: str | None,
    enabled_modules: list[str],
    role: str,
    permissions: dict | None,
) -> list[str]:
    canonical = packages_svc.canonicalize_industry(industry)
    label = INDUSTRY_LABELS.get(canonical, canonical) if canonical else "Not a configured business type"
    modules = set(enabled_modules or [])
    lines = [
        f"{company_name} staff guide",
        f"Business type: {label}",
        "This guide lists only the workflows enabled for this company.",
        "",
        "How this hotel runs" if canonical == "hotel" else "How this company sells",
    ]
    steps = _INDUSTRY_STEPS.get(canonical or "", [
        "Retail, hotel, and restaurant are the business types a new company can use.",
        "A company saved under another type keeps its own records and does not get that other desk.",
    ])
    for step in steps:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("Enabled workflows")
    shown = False
    for key, text in _MODULE_STEPS.items():
        if key not in modules:
            continue
        if key in packages_svc.INDUSTRY_SPECIFIC_MODULES and not packages_svc.industry_allows_module(canonical, key):
            continue
        if canonical == "hotel":
            text = _HOTEL_MODULE_STEPS.get(key, text)
        lines.append(f"- {text}")
        shown = True
    if not shown:
        lines.append("- No extra modules are enabled beyond sign-in and security.")
    lines.append("")
    lines.append(f"Your role: {role or 'staff'}")
    perms = permissions if isinstance(permissions, dict) else permissions_for_role(role or "")
    if perms.get("*") == ["*"] or (isinstance(perms.get("*"), list) and "*" in perms.get("*", [])):
        lines.append("- This role can read and change every module the company has enabled.")
    else:
        readable = sorted(k for k, actions in perms.items() if isinstance(actions, list) and "read" in actions)
        writable = sorted(k for k, actions in perms.items() if isinstance(actions, list) and "write" in actions)
        if readable:
            lines.append("- You can view: " + ", ".join(readable) + ".")
        if writable:
            lines.append("- You can change: " + ", ".join(writable) + ".")
        if not readable and not writable:
            lines.append("- This role has no extra module permissions.")
    lines.append("")
    lines.append("Invoice print, reports, backup, and restore follow the same company boundary.")
    return lines


async def build_staff_guide_pdf(db: AsyncSession, claims: dict) -> bytes:
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    user = await db.get(m.User, claims["sub"])
    industry = packages_svc.canonicalize_industry(getattr(tenant, "industry", None) if tenant else None)
    modules = packages_svc.resolve_enabled_modules(tenant) if tenant else []
    role = getattr(user, "role", None) or claims.get("role") or ""
    perms = getattr(user, "permissions", None) if user else None
    company = (getattr(tenant, "company_name", None) if tenant else None) or "Company"
    lines = guide_lines(
        company_name=company,
        industry=industry,
        enabled_modules=list(modules),
        role=str(role),
        permissions=perms if isinstance(perms, dict) else None,
    )
    title = f"{company} staff guide"
    return to_pdf(title, lines, subtitle=INDUSTRY_LABELS.get(industry or "", industry or ""))
