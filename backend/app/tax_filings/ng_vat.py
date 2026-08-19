"""Nigeria FIRS-style VAT return mapping from the jurisdiction-neutral filing pack.

Maps ERP boxes 1–5 / 2a into a workbook-oriented return used for manual FIRS filing.
Does not e-file to the FIRS portal.
"""

from __future__ import annotations

from app import models as m

TEMPLATE_CODE = "ng_vat_return"
TEMPLATE_NAME = "Nigeria FIRS VAT Return"


def map_return(pack: dict, tenant: m.Tenant) -> dict:
    fb = pack.get("filing_boxes") or {}
    by_code = {b["code"]: float(b.get("amount") or 0) for b in (fb.get("boxes") or [])}
    taxable_outputs = float(by_code.get("taxable_outputs_net", fb.get("taxable_outputs_net") or 0))
    zero_rated_outputs = float(
        by_code.get("zero_rated_outputs_net", fb.get("zero_rated_outputs_net") or 0)
    )
    exempt_outputs = float(by_code.get("exempt_outputs_net", fb.get("exempt_outputs_net") or 0))
    output_tax = float(by_code.get("output_tax", fb.get("output_tax") or pack.get("output_tax") or 0))
    reverse_charge = float(
        by_code.get("reverse_charge_tax", fb.get("reverse_charge_tax") or pack.get("reverse_charge_tax") or 0)
    )
    taxable_inputs = float(by_code.get("taxable_inputs_net", fb.get("taxable_inputs_net") or 0))
    input_tax = float(by_code.get("input_tax", fb.get("input_tax") or pack.get("input_tax") or 0))
    net = float(by_code.get("net_tax_payable", fb.get("net_tax_payable") or pack.get("net_tax_payable") or 0))

    # Simplified FIRS VAT return lines for manual workbook filing.
    boxes = [
        {
            "box": "1",
            "code": "NG1",
            "label": "Value of standard-rated taxable supplies",
            "amount": round(taxable_outputs, 2),
            "source_box": "1",
        },
        {
            "box": "2",
            "code": "NG2",
            "label": "Output VAT on standard-rated supplies",
            "amount": round(output_tax - reverse_charge, 2)
            if output_tax >= reverse_charge
            else round(output_tax, 2),
            "source_box": "2",
        },
        {
            "box": "3",
            "code": "NG3",
            "label": "Value of zero-rated supplies",
            "amount": round(zero_rated_outputs, 2),
            "source_box": "1z",
        },
        {
            "box": "4",
            "code": "NG4",
            "label": "Value of exempt supplies",
            "amount": round(exempt_outputs, 2),
            "source_box": "1e",
        },
        {
            "box": "5",
            "code": "NG5",
            "label": "Total output VAT (incl. reverse charge self-assess)",
            "amount": round(output_tax, 2),
            "source_box": "2",
        },
        {
            "box": "6",
            "code": "NG6",
            "label": "Reverse charge / self-assessed VAT",
            "amount": round(reverse_charge, 2),
            "source_box": "2a",
        },
        {
            "box": "7",
            "code": "NG7",
            "label": "Value of taxable purchases / inputs",
            "amount": round(taxable_inputs, 2),
            "source_box": "3",
        },
        {
            "box": "8",
            "code": "NG8",
            "label": "Input VAT claimable",
            "amount": round(input_tax, 2),
            "source_box": "4",
        },
        {
            "box": "9",
            "code": "NG9",
            "label": "Net VAT payable / (refundable)",
            "amount": round(net, 2),
            "source_box": "5",
        },
    ]

    tin = (getattr(tenant, "tax_registration_number", None) or "").strip() or None
    warnings: list[str] = []
    if not tin:
        warnings.append("tax_registration_number (TIN) is not set on the company profile")

    period = pack.get("period") or {}
    return {
        "template": TEMPLATE_CODE,
        "template_name": TEMPLATE_NAME,
        "jurisdiction": "NG",
        "header": {
            "taxpayer_name": tenant.company_name,
            "tax_registration_number": tin,
            "tin_missing": tin is None,
            "currency": (tenant.currency or "NGN").upper(),
            "timezone": tenant.timezone or "Africa/Lagos",
            "filing_period": getattr(tenant, "tax_filing_period", None) or "monthly",
            "period_from": period.get("from_date"),
            "period_to": period.get("to_date"),
            "generated_at": period.get("generated_at"),
        },
        "boxes": boxes,
        "schedules": {
            "output": list((pack.get("schedules") or {}).get("output") or []),
            "input": list((pack.get("schedules") or {}).get("input") or []),
        },
        "warnings": warnings,
        "source": "neutral_filing_pack",
    }
