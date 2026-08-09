"""CSV, PDF, and Excel export helpers for operational/financial reports."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting as accounting_svc
from app import reports as reports_svc
from app import tax as tax_svc

EXPORT_FORMATS = frozenset({"csv", "pdf", "xlsx"})

EXPORTABLE = frozenset(
    {
        "summary",
        "sales_daily",
        "sales_monthly",
        "sales_products",
        "sales_customers",
        "sales_salesperson",
        "sales_by_store",
        "inventory_balance",
        "inventory_movements",
        "inventory_low_stock",
        "inventory_valuation",
        "purchases_summary",
        "purchases_suppliers",
        "purchases_pending_orders",
        "purchases_returns",
        "expenses_summary",
        "cash_flow",
        "trial_balance",
        "profit_loss",
        "balance_sheet",
        "tax",
        "tax_filing",
        "tax_filing_gh",
        "tax_filing_ke",
        "tax_filing_ng",
    }
)


def to_csv(rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> str:
    if not rows:
        headers = fieldnames or []
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        return buf.getvalue()
    headers = fieldnames or list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_cell(row.get(k)) for k in headers})
    return buf.getvalue()


def _csv_cell(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return str(value)
    return value


def _xlsx_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, dict)):
        return str(value)
    return value


def to_xlsx(
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
    *,
    sheet_title: str = "Report",
) -> bytes:
    return to_xlsx_sheets([(sheet_title, rows, fieldnames)])


def to_xlsx_sheets(
    sheets: list[tuple[str, list[dict[str, Any]], list[str] | None]],
) -> bytes:
    """Build a workbook from [(title, rows, optional fieldnames), ...]."""
    wb = Workbook()
    # remove default sheet after first real sheet is created
    default = wb.active
    first = True
    for title, rows, fieldnames in sheets:
        name = (title or "Report").strip()[:31] or "Report"
        ws = default if first else wb.create_sheet(title=name)
        if first:
            ws.title = name
            first = False
        if not rows:
            headers = fieldnames or []
            if headers:
                ws.append(headers)
            continue
        headers = fieldnames or list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([_xlsx_cell(row.get(k)) for k in headers])
    if first:
        # no sheets provided
        pass
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def to_pdf(title: str, lines: list[str], *, subtitle: str | None = None) -> bytes:
    """Minimal single-page PDF (Helvetica) without third-party deps."""
    content_lines = [f"BT /F1 16 Tf 50 780 Td ({_pdf_escape(title)}) Tj ET"]
    y = 750
    if subtitle:
        content_lines.append(f"BT /F1 10 Tf 50 {y} Td ({_pdf_escape(subtitle)}) Tj ET")
        y -= 20
    content_lines.append(
        f"BT /F1 9 Tf 50 {y} Td ({_pdf_escape('Generated: ' + datetime.utcnow().isoformat() + 'Z')}) Tj ET"
    )
    y -= 28
    for line in lines:
        if y < 50:
            content_lines.append(
                f"BT /F1 9 Tf 50 {y} Td ({_pdf_escape('… truncated …')}) Tj ET"
            )
            break
        content_lines.append(f"BT /F1 9 Tf 50 {y} Td ({_pdf_escape(line[:110])}) Tj ET")
        y -= 14

    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def _kv_lines(payload: dict, prefix: str = "") -> list[str]:
    lines: list[str] = []
    for key, value in payload.items():
        if key in {"rows", "lines", "items", "products", "daily", "by_category", "assets", "liabilities", "equity", "suppliers", "salespeople", "stores"}:
            continue
        if isinstance(value, (dict, list)):
            continue
        label = f"{prefix}{key}" if prefix else str(key)
        lines.append(f"{label}: {value}")
    return lines


def flatten_report(report_type: str, payload: Any) -> tuple[list[dict], list[str], str]:
    """Return (csv_rows, pdf_lines, title)."""
    title = report_type.replace("_", " ").title()

    if report_type == "summary":
        rows = [_flatten_dict(payload)]
        return rows, _kv_lines(payload), "Executive Summary"

    if report_type == "sales_daily":
        return [dict(payload)], _kv_lines(payload), "Sales Daily"

    if report_type == "sales_monthly":
        daily = payload.get("daily") or []
        rows = daily if daily else [ {k: v for k, v in payload.items() if k != "daily"} ]
        lines = _kv_lines(payload) + [f"{d.get('date')}: {d.get('revenue')}" for d in daily[:40]]
        return rows, lines, "Sales Monthly"

    if report_type == "sales_products":
        items = payload.get("products") or payload.get("items") or []
        if isinstance(payload, list):
            items = payload
        rows = [dict(x) for x in items]
        lines = _kv_lines(payload if isinstance(payload, dict) else {}) + [
            f"{r.get('sku') or r.get('product_name') or r.get('name')}: qty={r.get('quantity') or r.get('qty')} amount={r.get('revenue') or r.get('line_total') or r.get('total')}"
            for r in rows[:50]
        ]
        return rows or [{"note": "no rows"}], lines, "Sales by Product"

    if report_type == "sales_customers":
        items = payload.get("customers") or []
        rows = [dict(x) for x in items]
        lines = _kv_lines(payload if isinstance(payload, dict) else {}) + [
            f"{r.get('name')}: sales={r.get('sale_count')} revenue={r.get('revenue')} avg={r.get('avg_ticket')}"
            for r in rows[:50]
        ]
        return rows or [{"note": "no rows"}], lines, "Sales by Customer"

    if report_type == "sales_salesperson":
        items = payload.get("salespeople") or []
        rows = [dict(x) for x in items]
        lines = _kv_lines(payload if isinstance(payload, dict) else {}) + [
            f"{r.get('full_name')}: sales={r.get('sale_count')} revenue={r.get('revenue')} avg={r.get('avg_ticket')}"
            for r in rows[:50]
        ]
        return rows or [{"note": "no rows"}], lines, "Sales by Salesperson"

    if report_type == "sales_by_store":
        items = payload.get("stores") or []
        rows = [dict(x) for x in items]
        lines = _kv_lines(payload if isinstance(payload, dict) else {}) + [
            f"{r.get('name') or r.get('code')}: sales={r.get('sale_count')} revenue={r.get('revenue')} "
            f"inv={r.get('invoice_revenue')} pos={r.get('pos_revenue')}"
            for r in rows[:50]
        ]
        return rows or [{"note": "no rows"}], lines, "Sales by Store"

    if report_type == "inventory_balance":
        items = payload.get("items") or payload.get("products") or (payload if isinstance(payload, list) else [])
        rows = [dict(x) for x in items]
        return rows or [{"note": "no rows"}], [f"{r.get('sku')}: {r.get('qty') or r.get('stock_qty') or r.get('quantity')}" for r in rows[:60]], "Inventory Balance"

    if report_type == "inventory_movements":
        items = payload.get("movements") or payload.get("items") or (payload if isinstance(payload, list) else [])
        rows = [dict(x) for x in items]
        return rows or [{"note": "no rows"}], [f"{r.get('created_at')}: {r.get('movement_type')} {r.get('quantity')}" for r in rows[:60]], "Inventory Movements"

    if report_type == "inventory_low_stock":
        items = payload.get("items") or payload.get("products") or (payload if isinstance(payload, list) else [])
        warehouse = payload.get("warehouse_low_stock") or [] if isinstance(payload, dict) else []
        rows = [dict(x) for x in items] + [dict(x) for x in warehouse]
        return (
            rows or [{"note": "no rows"}],
            [
                f"{r.get('sku')}: qty={r.get('stock_qty', r.get('quantity'))} reorder={r.get('reorder_level')}"
                for r in rows[:60]
            ],
            "Low Stock",
        )

    if report_type == "inventory_valuation":
        items = payload.get("items") or []
        rows = [dict(x) for x in items]
        lines = _kv_lines(
            {
                k: payload.get(k)
                for k in (
                    "costing_method",
                    "total_quantity",
                    "total_value",
                    "line_count",
                    "warehouse_id",
                    "store_id",
                )
                if k in payload
            }
        ) + [
            f"{r.get('sku')}: qty={r.get('quantity')} cost={r.get('cost_price')} value={r.get('value')}"
            for r in rows[:60]
        ]
        return rows or [{"note": "no rows"}], lines, "Stock Valuation"

    if report_type == "purchases_summary":
        return [dict(payload)], _kv_lines(payload), "Purchases Summary"

    if report_type == "purchases_suppliers":
        items = payload.get("suppliers") or payload.get("items") or (payload if isinstance(payload, list) else [])
        rows = [dict(x) for x in items]
        return rows or [{"note": "no rows"}], [f"{r.get('name') or r.get('supplier_name')}: {r.get('total') or r.get('amount')}" for r in rows[:50]], "Purchases by Supplier"

    if report_type == "purchases_pending_orders":
        items = payload.get("orders") or []
        rows = [dict(x) for x in items]
        lines = [
            f"{r.get('po_number')}: {r.get('supplier_name')} open_qty={r.get('open_qty')} ({r.get('status')})"
            for r in rows[:60]
        ]
        return rows or [{"note": "no rows"}], lines or _kv_lines(payload), "Pending Purchase Orders"

    if report_type == "purchases_returns":
        items = payload.get("returns") or []
        rows = [dict(x) for x in items]
        lines = _kv_lines(
            {
                k: payload.get(k)
                for k in ("return_count", "posted_count", "total_amount", "posted_amount")
                if k in payload
            }
        ) + [
            f"{r.get('return_number')}: {r.get('reason')} {r.get('total_amount')} ({r.get('status')})"
            for r in rows[:60]
        ]
        return rows or [{"note": "no rows"}], lines, "Purchase Return Summary"

    if report_type == "expenses_summary":
        cats = payload.get("by_category") or []
        rows = cats if cats else [dict(payload)]
        lines = _kv_lines(payload) + [f"{c.get('name') or c.get('category')}: {c.get('total') or c.get('amount')}" for c in cats[:40]]
        return [dict(x) for x in rows], lines, "Expenses Summary"

    if report_type == "cash_flow":
        lines_data = payload.get("lines") or []
        rows = [dict(x) for x in lines_data] if lines_data else [dict(payload)]
        summary = {
            k: payload.get(k)
            for k in (
                "from_date",
                "to_date",
                "opening_cash",
                "closing_cash",
                "net_change",
                "inflows",
                "outflows",
                "net",
            )
            if k in payload
        }
        for section in ("operating", "investing", "financing", "transfers"):
            block = payload.get(section) or {}
            if isinstance(block, dict):
                summary[f"{section}_net"] = block.get("net")
        pdf = _kv_lines(summary) + [
            f"{r.get('date')} [{r.get('activity')}]: +{r.get('inflow')} -{r.get('outflow')} {r.get('description')}"
            for r in lines_data[:40]
        ]
        return rows, pdf, "Cash Flow"

    if report_type == "trial_balance":
        rows = [dict(x) for x in (payload.get("rows") or [])]
        lines = _kv_lines(payload) + [f"{r.get('code')} {r.get('name')}: Dr {r.get('debit')} Cr {r.get('credit')}" for r in rows[:50]]
        return rows or [{"note": "no rows"}], lines, "Trial Balance"

    if report_type == "profit_loss":
        accounts = payload.get("accounts") or []
        rows = [dict(x) for x in accounts] if accounts else [dict(payload)]
        lines = _kv_lines(
            {
                k: payload.get(k)
                for k in (
                    "from_date",
                    "to_date",
                    "revenue",
                    "cogs",
                    "gross_profit",
                    "operating_expenses",
                    "other_income",
                    "income",
                    "expense",
                    "net_profit",
                )
                if k in payload
            }
        ) + [
            f"{r.get('code')} {r.get('name')} [{r.get('bucket')}]: {r.get('balance')}"
            for r in accounts[:50]
        ]
        return rows, lines, "Profit and Loss"

    if report_type == "balance_sheet":
        rows = []
        for section in ("assets", "liabilities", "equity"):
            for item in payload.get(section) or []:
                rows.append({"section": section, **dict(item)})
        lines = _kv_lines(payload)
        for section in ("assets", "liabilities", "equity"):
            lines.append(f"-- {section.upper()} --")
            for item in payload.get(section) or []:
                lines.append(f"  {item.get('code')} {item.get('name')}: {item.get('balance')}")
        return rows or [{"note": "no rows"}], lines, "Balance Sheet"

    if report_type == "tax":
        items = payload.get("lines") or payload.get("items") or []
        if isinstance(payload, list):
            items = payload
        rows = [dict(x) for x in items] if items else [_flatten_dict(payload if isinstance(payload, dict) else {"data": payload})]
        return rows, _kv_lines(payload if isinstance(payload, dict) else {}) + [str(r)[:100] for r in rows[:40]], "Tax Report"

    if report_type == "tax_filing":
        boxes = (payload.get("filing_boxes") or {}).get("boxes") or []
        out_sched = (payload.get("schedules") or {}).get("output") or []
        in_sched = (payload.get("schedules") or {}).get("input") or []
        rows = list(payload.get("lines") or [])
        if not rows:
            rows = [
                *[{"section": "filing_box", **b} for b in boxes],
                *out_sched,
                *in_sched,
            ]
        lines = _kv_lines(
            {
                k: v
                for k, v in (payload if isinstance(payload, dict) else {}).items()
                if k not in {"lines", "schedules", "filing_boxes", "period", "government", "supported_jurisdictions"}
            }
        )
        lines.append("-- FILING BOXES --")
        for b in boxes:
            lines.append(f"Box {b.get('box')} {b.get('label')}: {b.get('amount')}")
        lines.append(f"Output schedule lines: {len(out_sched)}")
        lines.append(f"Input schedule lines: {len(in_sched)}")
        return rows or [{"note": "no rows"}], lines, "Tax Filing Pack"

    if report_type in {"tax_filing_gh", "tax_filing_ke", "tax_filing_ng"}:
        gov = payload.get("government") or {}
        header = gov.get("header") or {}
        boxes = gov.get("boxes") or []
        out_sched = (gov.get("schedules") or {}).get("output") or []
        in_sched = (gov.get("schedules") or {}).get("input") or []
        juris = report_type.rsplit("_", 1)[-1]  # gh | ke | ng
        box_section = f"{juris}_box"
        rows = [
            {"section": "header", **{k: v for k, v in header.items() if not isinstance(v, (list, dict))}},
            *[{"section": box_section, **b} for b in boxes],
            *[{"section": "output", **r} for r in out_sched],
            *[{"section": "input", **r} for r in in_sched],
        ]
        lines = [
            f"Template: {gov.get('template_name') or gov.get('template')}",
            f"Taxpayer: {header.get('taxpayer_name')}",
            f"TIN: {header.get('tax_registration_number') or '(missing)'}",
            f"Currency: {header.get('currency')}",
            f"Period: {header.get('period_from')} → {header.get('period_to')}",
        ]
        for w in gov.get("warnings") or []:
            lines.append(f"WARNING: {w}")
        label = f"{juris.upper()} VAT BOXES"
        lines.append(f"-- {label} --")
        for b in boxes:
            lines.append(f"Box {b.get('box')} {b.get('label')}: {b.get('amount')}")
        lines.append(f"Output schedule lines: {len(out_sched)}")
        lines.append(f"Input schedule lines: {len(in_sched)}")
        titles = {
            "tax_filing_gh": "Ghana GRA VAT Return",
            "tax_filing_ke": "Kenya KRA VAT Return",
            "tax_filing_ng": "Nigeria FIRS VAT Return",
        }
        title = titles.get(report_type, "Government VAT Return")
        return rows or [{"note": "no rows"}], lines, title

    raise HTTPException(status_code=400, detail=f"Unsupported report type: {report_type}")


def _flatten_dict(payload: dict, prefix: str = "") -> dict:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            for k, v in value.items():
                if not isinstance(v, (dict, list)):
                    out[f"{path}.{k}"] = v
        elif not isinstance(value, list):
            out[path] = value
    return out


async def build_report_payload(
    db: AsyncSession,
    tenant_id: str,
    report_type: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    date: str | None = None,
    year: int | None = None,
    month: int | None = None,
    warehouse_id: str | None = None,
    store_id: str | None = None,
    category_id: str | None = None,
    jurisdiction: str | None = None,
) -> Any:
    if report_type not in EXPORTABLE:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report type. Allowed: {sorted(EXPORTABLE)}",
        )

    fd = reports_svc.parse_date(from_date)
    td = reports_svc.parse_date(to_date, end_of_day=True)
    now = datetime.utcnow()

    if report_type == "summary":
        daily = await reports_svc.sales_daily(db, tenant_id, now)
        monthly = await reports_svc.sales_monthly(db, tenant_id, now.year, now.month)
        low = await reports_svc.inventory_low_stock(db, tenant_id)
        expenses = await reports_svc.expenses_summary(db, tenant_id)
        return {
            "today_sales": daily,
            "month_sales": monthly,
            "low_stock_count": low.get("count") if isinstance(low, dict) else len(low or []),
            "expenses": expenses,
        }
    if report_type == "sales_daily":
        return await reports_svc.sales_daily(db, tenant_id, reports_svc.parse_date(date) or now)
    if report_type == "sales_monthly":
        return await reports_svc.sales_monthly(
            db, tenant_id, year or now.year, month or now.month
        )
    if report_type == "sales_products":
        return await reports_svc.sales_by_product(
            db,
            tenant_id,
            from_date=fd,
            to_date=td,
            store_id=store_id,
            category_id=category_id,
        )
    if report_type == "sales_customers":
        return await reports_svc.sales_by_customer(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "sales_salesperson":
        return await reports_svc.sales_by_salesperson(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "sales_by_store":
        return await reports_svc.sales_by_store(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "inventory_balance":
        return await reports_svc.inventory_balance(db, tenant_id, warehouse_id)
    if report_type == "inventory_movements":
        return await reports_svc.inventory_movements(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "inventory_low_stock":
        return await reports_svc.inventory_low_stock(db, tenant_id)
    if report_type == "inventory_valuation":
        return await reports_svc.inventory_valuation(
            db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
        )
    if report_type == "purchases_summary":
        return await reports_svc.purchases_summary(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "purchases_suppliers":
        return await reports_svc.purchases_by_supplier(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "purchases_pending_orders":
        return await reports_svc.purchases_pending_orders(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "purchases_returns":
        return await reports_svc.purchases_return_summary(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "expenses_summary":
        return await reports_svc.expenses_summary(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "cash_flow":
        return await reports_svc.cash_flow(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "trial_balance":
        return await accounting_svc.trial_balance(db, tenant_id)
    if report_type == "profit_loss":
        return await accounting_svc.profit_and_loss(
            db, tenant_id, from_date=fd, to_date=td
        )
    if report_type == "balance_sheet":
        return await reports_svc.balance_sheet(db, tenant_id)
    if report_type == "tax":
        return await tax_svc.tax_report(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "tax_filing":
        return await tax_svc.tax_filing_pack(db, tenant_id, from_date=fd, to_date=td)
    if report_type == "tax_filing_gh":
        from app import tax_filings as tax_filings_svc

        return await tax_filings_svc.government_filing_pack(
            db,
            tenant_id,
            from_date=fd,
            to_date=td,
            jurisdiction=jurisdiction or "GH",
        )
    if report_type == "tax_filing_ke":
        from app import tax_filings as tax_filings_svc

        return await tax_filings_svc.government_filing_pack(
            db,
            tenant_id,
            from_date=fd,
            to_date=td,
            jurisdiction=jurisdiction or "KE",
        )
    if report_type == "tax_filing_ng":
        from app import tax_filings as tax_filings_svc

        return await tax_filings_svc.government_filing_pack(
            db,
            tenant_id,
            from_date=fd,
            to_date=td,
            jurisdiction=jurisdiction or "NG",
        )
    raise HTTPException(status_code=400, detail="Unhandled report type")


async def export_report(
    db: AsyncSession,
    tenant_id: str,
    report_type: str,
    fmt: str,
    **kwargs,
) -> tuple[bytes, str, str]:
    fmt = (fmt or "csv").lower()
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of {sorted(EXPORT_FORMATS)}",
        )
    payload = await build_report_payload(db, tenant_id, report_type, **kwargs)
    rows, pdf_lines, title = flatten_report(report_type, payload)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    if fmt == "csv":
        text = to_csv(rows)
        return text.encode("utf-8"), "text/csv", f"{report_type}_{stamp}.csv"
    if fmt == "xlsx":
        if report_type == "tax_filing" and isinstance(payload, dict):
            boxes = (payload.get("filing_boxes") or {}).get("boxes") or []
            out_sched = (payload.get("schedules") or {}).get("output") or []
            in_sched = (payload.get("schedules") or {}).get("input") or []
            summary = [
                {"metric": "output_tax", "amount": payload.get("output_tax")},
                {"metric": "input_tax", "amount": payload.get("input_tax")},
                {"metric": "net_tax_payable", "amount": payload.get("net_tax_payable")},
                {"metric": "input_tax_source", "amount": payload.get("input_tax_source")},
            ]
            raw = to_xlsx_sheets(
                [
                    ("Summary", summary, None),
                    ("FilingBoxes", boxes, None),
                    ("OutputSchedule", out_sched, None),
                    ("InputSchedule", in_sched, None),
                ]
            )
        elif report_type in {"tax_filing_gh", "tax_filing_ke", "tax_filing_ng"} and isinstance(
            payload, dict
        ):
            gov = payload.get("government") or {}
            header = gov.get("header") or {}
            header_rows = [{"field": k, "value": v} for k, v in header.items()]
            for w in gov.get("warnings") or []:
                header_rows.append({"field": "warning", "value": w})
            boxes = gov.get("boxes") or []
            out_sched = (gov.get("schedules") or {}).get("output") or []
            in_sched = (gov.get("schedules") or {}).get("input") or []
            sheet_map = {
                "tax_filing_gh": "GHBoxes",
                "tax_filing_ke": "KEBoxes",
                "tax_filing_ng": "NGBoxes",
            }
            box_sheet = sheet_map[report_type]
            raw = to_xlsx_sheets(
                [
                    ("ReturnHeader", header_rows, None),
                    (box_sheet, boxes, None),
                    ("OutputSchedule", out_sched, None),
                    ("InputSchedule", in_sched, None),
                ]
            )
        else:
            raw = to_xlsx(rows, sheet_title=title)
        return (
            raw,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{report_type}_{stamp}.xlsx",
        )
    pdf = to_pdf(title, pdf_lines, subtitle=f"Tenant {tenant_id[:8]}…")
    return pdf, "application/pdf", f"{report_type}_{stamp}.pdf"
