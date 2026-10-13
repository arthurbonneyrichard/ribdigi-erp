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
        "How this company sells",
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
