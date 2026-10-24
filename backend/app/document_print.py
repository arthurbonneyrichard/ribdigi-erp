"""Shared HTML + A4 PDF letterhead for commercial documents."""

from __future__ import annotations

import html
from typing import Any

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.document_display import document_item_label, format_tenant_date
from app.honesty import money_json
from app.print_branding import (
    POWERED_BY_RIBDIGI,
    branding_fields_for_payload,
    company_identity_fields,
    company_identity_html,
    company_letterhead_detail_lines,
    document_print_shell,
)


def identity_for_print(
    tenant: m.Tenant | None,
    *,
    company_name: str = "",
    store_name: str = "",
) -> dict[str, str | None]:
    fields = company_identity_fields(tenant)
    if (company_name or "").strip():
        fields["company_name"] = company_name.strip()
    if (store_name or "").strip():
        fields["store_name"] = store_name.strip()
    return fields


def letterhead_payload(
    tenant: m.Tenant | None,
    *,
    company_name: str = "",
    store_name: str = "",
    currency: str = "GHS",
) -> dict[str, Any]:
    fields = identity_for_print(tenant, company_name=company_name, store_name=store_name)
    branding = branding_fields_for_payload(tenant)
    return {
        "company_name": fields.get("company_name") or "RIBDIGI ERP",
        "legal_name": fields.get("legal_name"),
        "store_name": fields.get("store_name"),
        "company_address": fields.get("company_address"),
        "company_phone": fields.get("company_phone"),
        "company_email": fields.get("company_email"),
        "registration_number": fields.get("registration_number"),
        "tax_registration_number": fields.get("tax_registration_number"),
        "print_header": branding["print_header"],
        "print_footer": branding["print_footer"],
        "has_logo": branding["has_logo"],
        "tenant_id": getattr(tenant, "id", None),
        "logo_key": getattr(tenant, "logo_url", None) if tenant else None,
        "currency": currency or (getattr(tenant, "currency", None) if tenant else None) or "GHS",
    }


def labeled_items(items: list[dict] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items or []:
        qty = item.get("quantity")
        if qty is None:
            qty = item.get("accepted_qty", item.get("received_qty"))
        rows.append(
            {
                "name": document_item_label(item),
                "quantity": qty,
                "unit_price": item.get("unit_price"),
                "tax_rate": item.get("tax_rate"),
                "discount": item.get("discount"),
                "line_total": item.get("line_total"),
                "received_qty": item.get("received_qty"),
                "accepted_qty": item.get("accepted_qty"),
                "rejected_qty": item.get("rejected_qty"),
                "notes": item.get("notes"),
            }
        )
    return rows


def _fmt_when(value: Any, tenant: m.Tenant | None = None) -> str:
    return format_tenant_date(value, tenant) if value else ""


def render_document_print_html(
    *,
    title: str,
    company_name: str,
    body_html: str,
    tenant: m.Tenant | None = None,
    store_name: str = "",
    subtitle: str | None = None,
) -> str:
    fields = identity_for_print(tenant, company_name=company_name, store_name=store_name)
    return document_print_shell(
        title=title,
        company_name=str(fields.get("company_name") or "RIBDIGI ERP"),
        subtitle=subtitle,
        body_html=body_html,
        tenant=tenant,
        identity_html=company_identity_html(tenant, fields=fields),
    )


def _meta_html(lines: list[str]) -> str:
    bits = [line for line in lines if str(line or "").strip()]
    if not bits:
        return ""
    return '<div class="meta">' + "<br/>".join(bits) + "</div>"


def _notes_html(notes: Any) -> str:
    text = str(notes or "").strip()
    if not text:
        return ""
    return f'<p class="meta" style="margin-top:12px">Notes {html.escape(text)}</p>'


def _totals_html(rows: list[tuple[str, str, bool]]) -> str:
    bits: list[str] = []
    for label, value, emph in rows:
        if emph:
            bits.append(f"<strong>{html.escape(label)} {html.escape(value)}</strong>")
        else:
            bits.append(f"{html.escape(label)} {html.escape(value)}")
    return f'<div class="totals">{"<br/>".join(bits)}</div>'


def _money_line(currency: str, amount: Any) -> str:
    return f"{currency} {money_json(amount or 0)}".strip()


def _line_table_html(items: list[dict], currency: str) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(i.get('name') or 'Item'))}</td>"
        f'<td class="r">{html.escape(str(i.get("quantity") if i.get("quantity") is not None else ""))}</td>'
        f'<td class="r">{html.escape(str(currency))} {html.escape(str(i.get("unit_price") if i.get("unit_price") is not None else ""))}</td>'
        f'<td class="r">{html.escape(str(i.get("tax_rate") if i.get("tax_rate") is not None else ""))}</td>'
        f'<td class="r">{html.escape(str(i.get("discount") if i.get("discount") is not None else ""))}</td>'
        f'<td class="r">{html.escape(str(currency))} {html.escape(str(i.get("line_total") if i.get("line_total") is not None else ""))}</td>'
        "</tr>"
        for i in items
    )
    return (
        '<table class="doc"><thead><tr>'
        "<th>Product</th><th>Qty</th><th>Unit</th><th>Tax</th><th>Discount</th><th>Total</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _grn_table_html(items: list[dict]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(i.get('name') or 'Item'))}</td>"
        f'<td class="r">{html.escape(str(i.get("received_qty") if i.get("received_qty") is not None else ""))}</td>'
        f'<td class="r">{html.escape(str(i.get("accepted_qty") if i.get("accepted_qty") is not None else ""))}</td>'
        f'<td class="r">{html.escape(str(i.get("rejected_qty") if i.get("rejected_qty") is not None else ""))}</td>'
        "</tr>"
        for i in items
    )
    return (
        '<table class="doc"><thead><tr>'
        "<th>Product</th><th>Received</th><th>Accepted</th><th>Rejected</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _request_table_html(items: list[dict]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(i.get('name') or 'Item'))}</td>"
        f'<td class="r">{html.escape(str(i.get("quantity") if i.get("quantity") is not None else ""))}</td>'
        f"<td>{html.escape(str(i.get('notes') or ''))}</td>"
        "</tr>"
        for i in items
    )
    return (
        '<table class="doc"><thead><tr>'
        "<th>Product</th><th>Qty</th><th>Notes</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def document_body_html(payload: dict[str, Any]) -> str:
    currency = str(payload.get("currency") or "")
    table = str(payload.get("table") or "lines")
    items = list(payload.get("items") or [])
    if table == "grn":
        table_html = _grn_table_html(items)
    elif table == "request":
        table_html = _request_table_html(items)
    elif table == "none":
        table_html = ""
    else:
        table_html = _line_table_html(items, currency)
    totals = payload.get("totals") or []
    totals_html = _totals_html(totals) if totals else ""
    return (
        f"{_meta_html(list(payload.get('meta_html_lines') or []))}"
        f"{table_html}"
        f"{totals_html}"
        f"{_notes_html(payload.get('notes'))}"
        f'<div class="foot"><div class="powered">{html.escape(POWERED_BY_RIBDIGI)}</div></div>'
    )


def render_payload_html(payload: dict[str, Any], tenant: m.Tenant | None = None) -> str:
    return render_document_print_html(
        title=str(payload.get("title") or payload.get("doc_heading") or "Document"),
        company_name=str(payload.get("company_name") or "RIBDIGI ERP"),
        body_html=document_body_html(payload),
        tenant=tenant,
        store_name=str(payload.get("store_name") or ""),
        subtitle=payload.get("subtitle"),
    )


def to_document_a4_pdf(payload: dict[str, Any]) -> bytes:
    """A4 commercial document — same forest letterhead as the sales invoice / PO."""
    from app.print_branding import (
        BRAND_GREEN_RGB,
        FOREST_RGB,
        INK_RGB,
        append_a4_letterhead,
        assemble_a4_pdf,
        load_logo_jpeg,
    )
    from app.receipts import _money, _wrap
    from app.report_export import _pdf_escape

    page_width, page_height = 595.0, 842.0
    margin = 40.0
    content: list[str] = []
    fr, fg, fb = FOREST_RGB
    ir, ig, ib = INK_RGB

    company = str(payload.get("company_name") or "RIBDIGI ERP")
    logo = None
    if payload.get("logo_key") and payload.get("tenant_id"):

        class _T:
            id = payload["tenant_id"]
            logo_url = payload["logo_key"]

        logo = load_logo_jpeg(_T(), max_width_px=280, max_height_px=72)

    ident = {
        "company_name": company,
        "legal_name": payload.get("legal_name"),
        "store_name": payload.get("store_name"),
        "company_address": payload.get("company_address"),
        "company_phone": payload.get("company_phone"),
        "company_email": payload.get("company_email"),
        "registration_number": payload.get("registration_number"),
        "tax_registration_number": payload.get("tax_registration_number"),
    }
    details = company_letterhead_detail_lines(ident)
    y = append_a4_letterhead(
        content,
        company_name=company,
        logo=logo,
        print_header=str(payload["print_header"]) if payload.get("print_header") else None,
        detail_lines=details,
        page_width=page_width,
        page_height=page_height,
        margin=margin,
    )

    def draw_text(
        text: str,
        size: float,
        *,
        x: float | None = None,
        y_pos: float | None = None,
        bold: bool = False,
        rgb: tuple[float, float, float] | None = None,
    ) -> None:
        nonlocal y
        if y_pos is not None:
            y = y_pos
        if not text:
            return
        font = "/F2" if bold or size >= 12 else "/F1"
        r, g, b = rgb if rgb is not None else (ir, ig, ib)
        content.append(
            f"BT {font} {size:.0f} Tf {r:.3f} {g:.3f} {b:.3f} rg "
            f"{(x if x is not None else margin):.1f} {y - size:.1f} Td ({_pdf_escape(text)}) Tj ET"
        )

    heading = str(payload.get("doc_heading") or payload.get("title") or "DOCUMENT")
    draw_text(heading, 18, bold=True, rgb=FOREST_RGB)
    y -= 22

    meta_left = [str(line) for line in (payload.get("meta_left") or []) if str(line).strip()]
    meta_right = [str(line) for line in (payload.get("meta_right") or []) if str(line).strip()]
    meta_y = y
    for line in meta_left:
        draw_text(line[:72], 10, y_pos=meta_y)
        meta_y -= 13
    meta_y_r = y
    for line in meta_right:
        draw_text(line[:48], 9, x=320, y_pos=meta_y_r, rgb=(0.302, 0.365, 0.337))
        meta_y_r -= 12
    y = min(meta_y, meta_y_r) - 8

    party_name = str(payload.get("party_name") or "").strip()
    if party_name:
        bill_h = 44.0 if payload.get("party_detail") else 36.0
        content.append(
            f"0.961 0.969 0.925 rg {margin:.1f} {y - bill_h:.1f} "
            f"{page_width - 2 * margin:.1f} {bill_h:.1f} re f"
        )
        content.append(
            f"{BRAND_GREEN_RGB[0]:.3f} {BRAND_GREEN_RGB[1]:.3f} {BRAND_GREEN_RGB[2]:.3f} rg "
            f"{margin:.1f} {y - bill_h:.1f} 3 {bill_h:.1f} re f"
        )
        draw_text(str(payload.get("party_label") or "Party"), 8, y_pos=y - 12, bold=True, rgb=FOREST_RGB)
        draw_text(party_name[:60], 12, y_pos=y - 26, bold=True)
        if payload.get("party_detail"):
            draw_text(str(payload["party_detail"])[:70], 9, y_pos=y - 38, rgb=(0.302, 0.365, 0.337))
        y -= bill_h + 16

    table = str(payload.get("table") or "lines")
    items = list(payload.get("items") or [])
    if table != "none" and items:
        col_y = y
        content.append(
            f"{fr:.3f} {fg:.3f} {fb:.3f} rg {margin:.1f} {col_y - 16:.1f} "
            f"{page_width - 2 * margin:.1f} 16 re f"
        )
        if table == "grn":
            headers = [
                (margin + 4, "Product"),
                (margin + 280, "Recv"),
                (margin + 360, "Acc"),
                (margin + 440, "Rej"),
            ]
        elif table == "request":
            headers = [
                (margin + 4, "Product"),
                (margin + 360, "Qty"),
                (margin + 420, "Notes"),
            ]
        else:
            headers = [
                (margin + 4, "Qty"),
                (margin + 40, "Description"),
                (margin + 280, "Unit"),
                (margin + 340, "Tax%"),
                (margin + 390, "Disc"),
                (margin + 450, "Line"),
            ]
        for x, label in headers:
            draw_text(label, 8, x=x, y_pos=col_y - 2, bold=True, rgb=(1.0, 1.0, 1.0))
        y = col_y - 22
        for item in items:
            if y < margin + 140:
                break
            name = str(item.get("name") or "Item")[:36]
            row_top = y
            if table == "grn":
                draw_text(name, 9, x=margin + 4, y_pos=row_top)
                draw_text(str(item.get("received_qty") or ""), 9, x=margin + 280, y_pos=row_top)
                draw_text(str(item.get("accepted_qty") or ""), 9, x=margin + 360, y_pos=row_top)
                draw_text(str(item.get("rejected_qty") or ""), 9, x=margin + 440, y_pos=row_top)
            elif table == "request":
                draw_text(name, 9, x=margin + 4, y_pos=row_top)
                draw_text(str(item.get("quantity") or ""), 9, x=margin + 360, y_pos=row_top)
                draw_text(str(item.get("notes") or "")[:18], 9, x=margin + 420, y_pos=row_top)
            else:
                qty = money_json(item.get("quantity") or 0)
                unit = money_json(item.get("unit_price") or 0)
                tax = money_json(item.get("tax_rate") or 0)
                disc = money_json(item.get("discount") or 0)
                line_total = money_json(item.get("line_total") or 0)
                draw_text(f"{qty:g}", 9, x=margin + 4, y_pos=row_top)
                draw_text(name, 9, x=margin + 40, y_pos=row_top)
                draw_text(_money(unit), 9, x=margin + 280, y_pos=row_top)
                draw_text(_money(tax), 9, x=margin + 340, y_pos=row_top)
                draw_text(_money(disc), 9, x=margin + 390, y_pos=row_top)
                draw_text(_money(line_total), 9, x=margin + 450, y_pos=row_top, bold=True)
            y = row_top - 14
            content.append(
                f"0.831 0.898 0.769 RG 0.5 w {margin:.1f} {y + 2:.1f} m "
                f"{page_width - margin:.1f} {y + 2:.1f} l S"
            )
        y -= 10

    totals = list(payload.get("totals") or [])
    if totals:
        totals_x = 340.0
        box_h = 14 * len(totals) + 16
        content.append(
            f"0.949 0.969 0.925 rg {totals_x - 8:.1f} {y - box_h:.1f} "
            f"{page_width - margin - totals_x + 8:.1f} {box_h:.1f} re f"
        )
        content.append(
            f"0.831 0.898 0.769 RG 0.8 w {totals_x - 8:.1f} {y - box_h:.1f} "
            f"{page_width - margin - totals_x + 8:.1f} {box_h:.1f} re S"
        )
        ty = y - 12
        for label, value, emph in totals:
            size = 12 if emph else 10
            draw_text(str(label), size, x=totals_x, y_pos=ty, bold=emph, rgb=FOREST_RGB if emph else INK_RGB)
            draw_text(str(value), size, x=totals_x + 110, y_pos=ty, bold=emph)
            ty -= 14
        y = y - box_h - 16

    if payload.get("notes") and y > margin + 60:
        draw_text("Notes", 9, y_pos=y, bold=True, rgb=FOREST_RGB)
        y -= 12
        for part in _wrap(str(payload["notes"]), 78)[:4]:
            draw_text(part, 9, y_pos=y, rgb=(0.302, 0.365, 0.337))
            y -= 11

    y = max(y - 8, margin + 36)
    if payload.get("print_footer"):
        draw_text(str(payload["print_footer"]), 9, y_pos=y, rgb=(0.302, 0.365, 0.337))
        y -= 14
    draw_text(POWERED_BY_RIBDIGI, 7, y_pos=y, bold=True, rgb=BRAND_GREEN_RGB)
    return assemble_a4_pdf(content, logo=logo, page_width=page_width, page_height=page_height)


def print_response(
    payload: dict[str, Any],
    *,
    tenant: m.Tenant | None,
    fmt: str | None,
    filename: str,
) -> Response:
    kind = fmt or "html"
    if kind == "pdf":
        pdf = to_document_a4_pdf(payload)
        safe = filename.replace("/", "-")
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{safe}"'},
        )
    return Response(
        content=render_payload_html(payload, tenant),
        media_type="text/html; charset=utf-8",
    )


async def store_name_by_id(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None,
) -> str:
    if not store_id:
        return ""
    store = (
        await db.execute(
            select(m.Store).where(m.Store.id == store_id, m.Store.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    return ((store.name if store else None) or "").strip()


async def warehouse_store_name(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str | None,
) -> str:
    from app.purchasing import po_print_store_name

    return await po_print_store_name(db, tenant_id=tenant_id, warehouse_id=warehouse_id)


async def get_tenant_party(
    db: AsyncSession,
    tenant_id: str,
    party_id: str | None,
    *,
    kind: str | None = None,
) -> m.Party | None:
    if not party_id:
        return None
    filters = [m.Party.id == party_id, m.Party.tenant_id == tenant_id]
    if kind:
        filters.append(m.Party.kind == kind)
    return (await db.execute(select(m.Party).where(*filters))).scalar_one_or_none()


def _standard_totals(doc: dict, currency: str) -> list[tuple[str, str, bool]]:
    rows: list[tuple[str, str, bool]] = [
        ("Subtotal", _money_line(currency, doc.get("subtotal")), False),
        ("Tax", _money_line(currency, doc.get("tax_amount") or doc.get("tax")), False),
    ]
    disc = money_json(doc.get("discount_amount") or 0)
    if disc:
        rows.append(("Discount", _money_line(currency, disc), False))
    rows.append(("TOTAL", _money_line(currency, doc.get("total_amount") or doc.get("total")), True))
    return rows


def build_sales_quotation_print(
    quote: dict,
    *,
    tenant: m.Tenant | None,
    customer: m.Party | None,
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(tenant, "currency", None) if tenant else None) or "GHS"
    number = str(quote.get("quotation_number") or "")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(customer, "email", None) or "").strip()
    party_name = (getattr(customer, "name", None) or quote.get("customer_name") or "").strip()
    date_s = _fmt_when(quote.get("created_at"), tenant)
    until_s = _fmt_when(quote.get("valid_until"), tenant)
    payload.update(
        {
            "document_type": "sales_quotation",
            "title": f"Quotation {number}".strip() or "Quotation",
            "doc_heading": "QUOTATION",
            "subtitle": f"Valid until {until_s}" if until_s else (f"Quote date {date_s}" if date_s else None),
            "table": "lines",
            "items": labeled_items(quote.get("items")),
            "notes": quote.get("notes"),
            "party_label": "Quote to",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Quote    {number}",
                f"Status   {str(quote.get('status') or '').upper()}",
                f"Date     {date_s}" if date_s else "",
                f"Valid    {until_s}" if until_s else "",
            ],
            "meta_right": [f"Customer email {party_email}" if party_email else ""],
            "meta_html_lines": [
                f"Quotation <strong>{html.escape(number)}</strong> · Status {html.escape(str(quote.get('status') or '').upper())}",
                f"Customer {html.escape(str(party_name or quote.get('customer_id') or ''))}"
                + (f"<br/>Customer email {html.escape(party_email)}" if party_email else ""),
                f"Quote date {html.escape(date_s)}" if date_s else "",
                f"Valid until {html.escape(until_s)}" if until_s else "",
            ],
            "totals": _standard_totals(quote, currency),
        }
    )
    return payload


def build_sales_order_print(
    order: dict,
    *,
    tenant: m.Tenant | None,
    customer: m.Party | None,
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(tenant, "currency", None) if tenant else None) or "GHS"
    number = str(order.get("order_number") or "")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(customer, "email", None) or "").strip()
    party_name = (getattr(customer, "name", None) or order.get("customer_name") or "").strip()
    date_s = _fmt_when(order.get("created_at"), tenant)
    due_s = _fmt_when(order.get("delivery_date"), tenant)
    ship = str(order.get("delivery_address") or "").strip()
    payload.update(
        {
            "document_type": "sales_order",
            "title": f"Sales order {number}".strip() or "Sales order",
            "doc_heading": "SALES ORDER",
            "subtitle": f"Delivery {due_s}" if due_s else (f"Order date {date_s}" if date_s else None),
            "table": "lines",
            "items": labeled_items(order.get("items")),
            "notes": order.get("notes"),
            "party_label": "Sold to",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Order    {number}",
                f"Status   {str(order.get('status') or '').upper()}",
                f"Date     {date_s}" if date_s else "",
                f"Deliver  {due_s}" if due_s else "",
            ],
            "meta_right": [
                f"Ship to {ship[:40]}" if ship else "",
                f"Customer email {party_email}" if party_email else "",
            ],
            "meta_html_lines": [
                f"Sales order <strong>{html.escape(number)}</strong> · Status {html.escape(str(order.get('status') or '').upper())}",
                f"Customer {html.escape(str(party_name or order.get('customer_id') or ''))}"
                + (f"<br/>Customer email {html.escape(party_email)}" if party_email else ""),
                f"Order date {html.escape(date_s)}" if date_s else "",
                f"Delivery date {html.escape(due_s)}" if due_s else "",
                f"Ship to {html.escape(ship)}" if ship else "",
            ],
            "totals": _standard_totals(order, currency),
        }
    )
    return payload


def build_sales_return_print(
    ret: dict,
    *,
    tenant: m.Tenant | None,
    customer: m.Party | None,
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(tenant, "currency", None) if tenant else None) or "GHS"
    number = str(ret.get("return_number") or "")
    credit = str(ret.get("credit_note_number") or "—")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(customer, "email", None) or "").strip()
    party_name = (getattr(customer, "name", None) or "").strip()
    date_s = _fmt_when(ret.get("posted_at") or ret.get("created_at"), tenant)
    payload.update(
        {
            "document_type": "sales_return",
            "title": f"Credit note {credit}".strip() if credit != "—" else f"Sales return {number}".strip() or "Sales return",
            "doc_heading": "CREDIT NOTE",
            "subtitle": f"Return {number}",
            "table": "lines",
            "items": labeled_items(ret.get("items")),
            "notes": ret.get("notes"),
            "party_label": "Credit to",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Return   {number}",
                f"Credit   {credit}",
                f"Status   {str(ret.get('status') or '').upper()}",
                f"Date     {date_s}" if date_s else "",
            ],
            "meta_right": [
                f"Reason {ret.get('reason') or ''}",
                f"Customer email {party_email}" if party_email else "",
            ],
            "meta_html_lines": [
                f"Return <strong>{html.escape(number)}</strong> · Credit note <strong>{html.escape(credit)}</strong>",
                f"Customer {html.escape(str(party_name or ret.get('customer_id') or ''))}"
                + (f"<br/>Customer email {html.escape(party_email)}" if party_email else ""),
                f"Reason {html.escape(str(ret.get('reason') or ''))} · Status {html.escape(str(ret.get('status') or '').upper())}",
            ],
            "totals": [
                ("TOTAL", _money_line(currency, ret.get("total_amount")), True),
            ],
        }
    )
    return payload


def build_customer_payment_print(
    payment: m.CustomerPayment,
    *,
    tenant: m.Tenant | None,
    customer: m.Party | None,
    invoice_number: str = "",
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(payment, "currency", None) or "").strip() or (
        getattr(tenant, "currency", None) if tenant else None
    ) or "GHS"
    number = str(payment.payment_number or "")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(customer, "email", None) or "").strip()
    party_name = (getattr(customer, "name", None) or "").strip()
    date_s = _fmt_when(payment.created_at, tenant)
    payload.update(
        {
            "document_type": "customer_payment",
            "title": f"Payment receipt {number}".strip() or "Payment receipt",
            "doc_heading": "PAYMENT RECEIPT",
            "subtitle": f"Date {date_s}" if date_s else None,
            "table": "none",
            "items": [],
            "notes": payment.notes,
            "party_label": "Received from",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Receipt  {number}",
                f"Date     {date_s}" if date_s else "",
                f"Method   {str(payment.payment_method or '').replace('_', ' ')}",
            ],
            "meta_right": [
                f"Invoice {invoice_number}" if invoice_number else "",
                f"Ref {payment.reference}" if payment.reference else "",
            ],
            "meta_html_lines": [
                f"Receipt <strong>{html.escape(number)}</strong>",
                f"Customer {html.escape(str(party_name or payment.customer_id))}"
                + (f"<br/>Customer email {html.escape(party_email)}" if party_email else ""),
                f"Date {html.escape(date_s)}" if date_s else "",
                f"Method {html.escape(str(payment.payment_method or '').replace('_', ' '))}",
                f"Invoice {html.escape(invoice_number)}" if invoice_number else "",
            ],
            "totals": [("Received", _money_line(currency, payment.amount), True)],
        }
    )
    return payload


def build_grn_print(
    grn: dict,
    *,
    tenant: m.Tenant | None,
    supplier: m.Party | None,
    po_number: str = "",
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(tenant, "currency", None) if tenant else None) or "GHS"
    number = str(grn.get("grn_number") or "")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(supplier, "email", None) or "").strip()
    party_name = (getattr(supplier, "name", None) or "").strip()
    date_s = _fmt_when(grn.get("received_at") or grn.get("created_at"), tenant)
    payload.update(
        {
            "document_type": "goods_receipt",
            "title": f"Goods received {number}".strip() or "Goods received",
            "doc_heading": "GOODS RECEIVED",
            "subtitle": f"PO {po_number}" if po_number else (f"Received {date_s}" if date_s else None),
            "table": "grn",
            "items": labeled_items(grn.get("items")),
            "notes": grn.get("notes"),
            "party_label": "Supplier",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"GRN      {number}",
                f"Status   {str(grn.get('status') or '').upper()}",
                f"Date     {date_s}" if date_s else "",
                f"PO       {po_number}" if po_number else "",
            ],
            "meta_right": [f"Supplier email {party_email}" if party_email else ""],
            "meta_html_lines": [
                f"GRN <strong>{html.escape(number)}</strong> · Status {html.escape(str(grn.get('status') or '').upper())}",
                f"Supplier {html.escape(str(party_name or grn.get('supplier_id') or ''))}"
                + (f"<br/>Supplier email {html.escape(party_email)}" if party_email else ""),
                f"Date received {html.escape(date_s)}" if date_s else "",
                f"Purchase order {html.escape(po_number)}" if po_number else "",
            ],
            "totals": [],
        }
    )
    return payload


def build_purchase_invoice_print(
    inv: dict,
    *,
    tenant: m.Tenant | None,
    supplier: m.Party | None,
    store_name: str = "",
) -> dict[str, Any]:
    currency = str(inv.get("currency") or "").strip() or (
        getattr(tenant, "currency", None) if tenant else None
    ) or "GHS"
    number = str(inv.get("invoice_number") or "")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(supplier, "email", None) or "").strip()
    party_name = (getattr(supplier, "name", None) or "").strip()
    date_s = _fmt_when(inv.get("invoice_date") or inv.get("created_at"), tenant)
    due_s = _fmt_when(inv.get("due_date"), tenant)
    totals = _standard_totals(inv, currency)
    totals.append(("Paid", _money_line(currency, inv.get("paid_amount")), False))
    totals.append(("Balance due", _money_line(currency, inv.get("balance_due")), True))
    payload.update(
        {
            "document_type": "purchase_invoice",
            "title": f"Supplier bill {number}".strip() or "Supplier bill",
            "doc_heading": "SUPPLIER BILL",
            "subtitle": f"Due {due_s}" if due_s else (f"Bill date {date_s}" if date_s else None),
            "table": "lines",
            "items": labeled_items(inv.get("items")),
            "notes": inv.get("notes"),
            "party_label": "Bill from",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Bill     {number}",
                f"Status   {str(inv.get('status') or '').upper()}",
                f"Date     {date_s}" if date_s else "",
                f"Pay by   {due_s}" if due_s else "",
            ],
            "meta_right": [
                f"Supplier # {inv.get('supplier_invoice_number')}" if inv.get("supplier_invoice_number") else "",
                f"Supplier email {party_email}" if party_email else "",
            ],
            "meta_html_lines": [
                f"Supplier bill <strong>{html.escape(number)}</strong> · Status {html.escape(str(inv.get('status') or '').upper())}",
                f"Supplier {html.escape(str(party_name or inv.get('supplier_id') or ''))}"
                + (f"<br/>Supplier email {html.escape(party_email)}" if party_email else ""),
                f"Bill date {html.escape(date_s)}" if date_s else "",
                f"Payment due {html.escape(due_s)}" if due_s else "",
            ],
            "totals": totals,
        }
    )
    return payload


def build_purchase_return_print(
    ret: dict,
    *,
    tenant: m.Tenant | None,
    supplier: m.Party | None,
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(tenant, "currency", None) if tenant else None) or "GHS"
    number = str(ret.get("return_number") or "")
    debit = str(ret.get("debit_note_number") or "—")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(supplier, "email", None) or "").strip()
    party_name = (getattr(supplier, "name", None) or "").strip()
    payload.update(
        {
            "document_type": "purchase_return",
            "title": f"Purchase return {number}".strip() or "Purchase return",
            "doc_heading": "DEBIT NOTE",
            "subtitle": f"Debit note {debit}",
            "table": "lines",
            "items": labeled_items(ret.get("items")),
            "notes": ret.get("notes"),
            "party_label": "Return to",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Return   {number}",
                f"Debit    {debit}",
                f"Status   {str(ret.get('status') or '').upper()}",
            ],
            "meta_right": [
                f"Reason {ret.get('reason') or ''}",
                f"Supplier email {party_email}" if party_email else "",
            ],
            "meta_html_lines": [
                f"Return <strong>{html.escape(number)}</strong> · Debit note <strong>{html.escape(debit)}</strong>",
                f"Supplier {html.escape(str(party_name or ret.get('supplier_id') or ''))}"
                + (f"<br/>Supplier email {html.escape(party_email)}" if party_email else ""),
                f"Reason {html.escape(str(ret.get('reason') or ''))} · Status {html.escape(str(ret.get('status') or '').upper())}",
            ],
            "totals": [("TOTAL", _money_line(currency, ret.get("total_amount")), True)],
        }
    )
    return payload


def build_supplier_payment_print(
    payment: m.SupplierPayment,
    *,
    tenant: m.Tenant | None,
    supplier: m.Party | None,
    bill_number: str = "",
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(payment, "currency", None) or "").strip() or (
        getattr(tenant, "currency", None) if tenant else None
    ) or "GHS"
    number = str(payment.payment_number or "")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(supplier, "email", None) or "").strip()
    party_name = (getattr(supplier, "name", None) or "").strip()
    date_s = _fmt_when(payment.created_at, tenant)
    payload.update(
        {
            "document_type": "supplier_payment",
            "title": f"Supplier payment {number}".strip() or "Supplier payment",
            "doc_heading": "SUPPLIER PAYMENT",
            "subtitle": f"Date {date_s}" if date_s else None,
            "table": "none",
            "items": [],
            "notes": payment.notes,
            "party_label": "Paid to",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Receipt  {number}",
                f"Date     {date_s}" if date_s else "",
                f"Method   {str(payment.payment_method or '').replace('_', ' ')}",
            ],
            "meta_right": [
                f"Bill {bill_number}" if bill_number else "",
                f"Ref {payment.reference}" if payment.reference else "",
            ],
            "meta_html_lines": [
                f"Payment <strong>{html.escape(number)}</strong>",
                f"Supplier {html.escape(str(party_name or payment.supplier_id))}"
                + (f"<br/>Supplier email {html.escape(party_email)}" if party_email else ""),
                f"Date {html.escape(date_s)}" if date_s else "",
                f"Method {html.escape(str(payment.payment_method or '').replace('_', ' '))}",
                f"Bill {html.escape(bill_number)}" if bill_number else "",
            ],
            "totals": [("Paid", _money_line(currency, payment.amount), True)],
        }
    )
    return payload


def build_purchase_request_print(
    request: dict,
    *,
    tenant: m.Tenant | None,
    supplier: m.Party | None,
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(tenant, "currency", None) if tenant else None) or "GHS"
    number = str(request.get("request_number") or "")
    payload = letterhead_payload(tenant, company_name=getattr(tenant, "company_name", "") or "", store_name=store_name, currency=currency)
    party_email = (getattr(supplier, "email", None) or "").strip()
    party_name = (getattr(supplier, "name", None) or "").strip() or None
    date_s = _fmt_when(request.get("created_at"), tenant)
    needed = _fmt_when(request.get("required_date"), tenant)
    dept = str(request.get("department") or "").strip()
    payload.update(
        {
            "document_type": "purchase_request",
            "title": f"Purchase request {number}".strip() or "Purchase request",
            "doc_heading": "PURCHASE REQUEST",
            "subtitle": f"Needed by {needed}" if needed else (f"Request date {date_s}" if date_s else None),
            "table": "request",
            "items": labeled_items(request.get("items")),
            "notes": request.get("notes"),
            "party_label": "Preferred supplier",
            "party_name": party_name,
            "party_detail": party_email or None,
            "meta_left": [
                f"Request  {number}",
                f"Status   {str(request.get('status') or '').upper()}",
                f"Date     {date_s}" if date_s else "",
                f"Needed   {needed}" if needed else "",
            ],
            "meta_right": [
                f"Dept {dept}" if dept else "",
                f"Supplier email {party_email}" if party_email else "",
            ],
            "meta_html_lines": [
                f"Purchase request <strong>{html.escape(number)}</strong> · Status {html.escape(str(request.get('status') or '').upper())}",
                f"Preferred supplier {html.escape(str(party_name or '—'))}"
                + (f"<br/>Supplier email {html.escape(party_email)}" if party_email else ""),
                f"Request date {html.escape(date_s)}" if date_s else "",
                f"Needed by {html.escape(needed)}" if needed else "",
                f"Department {html.escape(dept)}" if dept else "",
            ],
            "totals": [],
        }
    )
    return payload


def build_expense_print(
    expense: dict,
    *,
    tenant: m.Tenant | None,
    store_name: str = "",
) -> dict[str, Any]:
    currency = (getattr(tenant, "currency", None) if tenant else None) or "GHS"
    number = str(expense.get("reference") or expense.get("id") or "")
    payload = letterhead_payload(
        tenant,
        company_name=getattr(tenant, "company_name", "") or "",
        store_name=store_name,
        currency=currency,
    )
    payee = str(expense.get("payee") or "").strip()
    date_s = _fmt_when(expense.get("expense_date") or expense.get("created_at"), tenant)
    payload.update(
        {
            "document_type": "expense",
            "title": f"Expense {number}".strip() or "Expense",
            "doc_heading": "EXPENSE",
            "subtitle": f"Date {date_s}" if date_s else None,
            "table": "none",
            "items": [],
            "notes": expense.get("description"),
            "party_label": "Payee",
            "party_name": payee or None,
            "party_detail": None,
            "meta_left": [
                f"Expense  {number}" if number else "",
                f"Status   {str(expense.get('status') or '').upper()}",
                f"Date     {date_s}" if date_s else "",
                f"Category {expense.get('category') or ''}",
            ],
            "meta_right": [
                f"Method {str(expense.get('payment_method') or '').replace('_', ' ')}",
                f"Payee {payee}" if payee else "",
            ],
            "meta_html_lines": [
                f"Expense <strong>{html.escape(number or '—')}</strong> · Status {html.escape(str(expense.get('status') or '').upper())}",
                f"Category {html.escape(str(expense.get('category') or '—'))}",
                f"Payee {html.escape(payee)}" if payee else "",
                f"Date {html.escape(date_s)}" if date_s else "",
                f"Method {html.escape(str(expense.get('payment_method') or '').replace('_', ' '))}",
            ],
            "totals": [("Amount", _money_line(currency, expense.get("amount")), True)],
        }
    )
    return payload


async def get_customer_payment(db: AsyncSession, tenant_id: str, payment_id: str) -> m.CustomerPayment:
    row = await db.get(m.CustomerPayment, payment_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return row


async def get_supplier_payment(db: AsyncSession, tenant_id: str, payment_id: str) -> m.SupplierPayment:
    row = await db.get(m.SupplierPayment, payment_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return row
