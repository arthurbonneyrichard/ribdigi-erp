"""Outbound email via SMTP with safe development fallback."""

from __future__ import annotations

import asyncio
import html
import io
import logging
import re
import smtplib
import ssl
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.document_display import document_item_label, first_document_date, format_tenant_date
from app.email_settings import SmtpConfig, resolve_smtp_config
from app.honesty import money_json

logger = logging.getLogger(__name__)

# In-memory outbox for tests / development inspection
_DEV_OUTBOX: list[dict[str, Any]] = []

# Platform sender names that should be shown as the Ribdigi House logo, not text.
_PLATFORM_BRAND_ALIASES = frozenset(
    {
        "ribdigi",
        "ribdigi erp",
        "ribdigi house",
        "ribdigihouse",
        "ribdigi-house",
    }
)

_BRANDING_DIR = Path(__file__).resolve().parent / "branding"


@dataclass
class EmailResult:
    sent: bool
    mode: str  # smtp | console | disabled
    message_id: str | None = None
    error: str | None = None
    recipients: list[str] = field(default_factory=list)


def clear_dev_outbox() -> None:
    _DEV_OUTBOX.clear()


def get_dev_outbox() -> list[dict[str, Any]]:
    return list(_DEV_OUTBOX)


def smtp_configured(tenant: Any | None = None) -> bool:
    return resolve_smtp_config(tenant).configured


def email_status(tenant: Any | None = None) -> dict:
    from app.email_settings import email_status as _email_status

    return _email_status(tenant)


def _delivery_mode(cfg: SmtpConfig | None = None) -> str:
    c = cfg or resolve_smtp_config(None)
    if not c.enabled:
        return "disabled"
    if c.configured:
        return "smtp"
    return "console"


def _is_platform_brand_name(name: str | None) -> bool:
    key = " ".join(str(name or "").strip().lower().split())
    return key in _PLATFORM_BRAND_ALIASES


PLATFORM_LOGO_CID = "ribdigi-house-logo@ribdigi"
_CID_SRC = re.compile(r'<img\b[^>]*\bsrc="cid:([^"]+)"[^>]*>', re.IGNORECASE)
_INLINE_MAX = 256
_inline_lock = threading.Lock()
# cid -> (owning tenant id or None for the platform mark, bytes, image subtype)
_INLINE_IMAGES: OrderedDict[str, tuple[str | None, bytes, str]] = OrderedDict()


def _register_inline(cid: str, owner: str | None, data: bytes, subtype: str) -> None:
    with _inline_lock:
        _INLINE_IMAGES[cid] = (owner, data, subtype)
        _INLINE_IMAGES.move_to_end(cid)
        while len(_INLINE_IMAGES) > _INLINE_MAX:
            _INLINE_IMAGES.popitem(last=False)


def _resolve_inline_images(
    html_body: str | None, tenant: Any | None
) -> tuple[str | None, list[tuple[str, bytes, str]]]:
    """Find ``cid:`` logos in the HTML that belong to this tenant (or the platform).

    An image this send cannot attach is removed so clients do not show a broken icon;
    the company name text stays in the header.
    """
    if not html_body or "cid:" not in html_body:
        return html_body, []
    tenant_id = str(getattr(tenant, "id", "") or "") or None
    found: list[tuple[str, bytes, str]] = []
    seen: set[str] = set()

    def _swap(match: re.Match) -> str:
        cid = match.group(1)
        with _inline_lock:
            entry = _INLINE_IMAGES.get(cid)
        if entry is None or (entry[0] is not None and entry[0] != tenant_id):
            return ""
        if cid not in seen:
            seen.add(cid)
            found.append((cid, entry[1], entry[2]))
        return match.group(0)

    return _CID_SRC.sub(_swap, html_body), found


def _platform_house_logo() -> tuple[int, int] | None:
    """Register the Ribdigi House noreply mark as an inline image; return (width, height)."""
    cached = _platform_house_logo_bytes()
    if cached is None:
        return None
    data, subtype, width, height = cached
    _register_inline(PLATFORM_LOGO_CID, None, data, subtype)
    return width, height


@lru_cache(maxsize=1)
def _platform_house_logo_bytes() -> tuple[bytes, str, int, int] | None:
    jpg = _BRANDING_DIR / "ribdigi-house-email.jpg"
    png = _BRANDING_DIR / "ribdigi-house-logo.png"
    path = jpg if jpg.is_file() else png if png.is_file() else None
    if path is None:
        return None
    try:
        from PIL import Image

        with Image.open(path) as src:
            img = src.convert("RGBA") if src.mode in {"RGBA", "LA", "P"} else src.convert("RGB")
        # Readable ~220px header, bitmap at 2× for HiDPI clients.
        max_w = 220
        img.thumbnail((max_w * 2, 144), Image.LANCZOS)
        buf = io.BytesIO()
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            img.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True)
            subtype = "jpeg"
        else:
            img.save(buf, format="PNG", optimize=True)
            subtype = "png"
        scale = min(max_w / img.width, 72 / img.height, 1.0)
        width = max(1, int(round(img.width * scale)))
        height = max(1, int(round(img.height * scale)))
        return buf.getvalue(), subtype, width, height
    except Exception:
        logger.exception("Failed to load Ribdigi House email logo")
        return None


def render_branded_html(
    *,
    body_html: str,
    company_name: str | None = None,
    tenant: Any | None = None,
    title: str | None = None,
    allow_platform_logo: bool | None = None,
) -> str:
    """Wrap inner HTML in branded email chrome (logo, header, footer).

    Prefer the tenant company logo when configured. Tenant documents never fall
    back to the Ribdigi House mark — company name only. Platform noreply mail
    (verify/reset) may embed the House logo when ``allow_platform_logo`` is true.
    """
    from app.logo_media import email_logo
    from app.print_branding import print_branding_settings

    company = (
        (company_name or getattr(tenant, "company_name", None) or "Ribdigi House") or "Ribdigi House"
    ).strip()
    company_esc = html.escape(company)
    branding = print_branding_settings(tenant)
    header = str(branding.get("header_text") or "").strip()
    footer = str(branding.get("footer_text") or "").strip()
    if allow_platform_logo is None:
        allow_platform_logo = tenant is None

    logo_html = ""
    used_platform_logo = False
    # Inline CID parts, not data: URIs — Gmail/Outlook strip data: images.
    logo = email_logo(tenant)
    if logo:
        _register_inline(logo.cid, str(tenant.id), logo.data, logo.subtype)
        logo_html = (
            f'<img class="ribdigi-email-logo" src="cid:{logo.cid}" '
            f'width="{logo.width}" height="{logo.height}" alt="{company_esc}" '
            f'style="display:block;width:{logo.width}px;height:{logo.height}px;'
            "max-width:240px;border:0;outline:none;background:#ffffff;padding:6px;"
            'border-radius:8px;margin:0 auto 12px;" />'
        )
    elif allow_platform_logo:
        platform = _platform_house_logo()
        if platform:
            width_px, height_px = platform
            logo_html = (
                f'<img class="ribdigi-email-logo ribdigi-house-logo" src="cid:{PLATFORM_LOGO_CID}" '
                f'width="{width_px}" height="{height_px}" alt="Ribdigi House" '
                f'style="display:block;width:{width_px}px;height:{height_px}px;'
                'max-width:220px;border:0;outline:none;margin:0 auto 8px;" />'
            )
            used_platform_logo = True

    # Logo replaces the Ribdigi House / RIBDIGI ERP text brand mark.
    show_company_text = not (used_platform_logo and _is_platform_brand_name(company))
    company_html = (
        f'<div class="ribdigi-email-company" style="font-size:18px;font-weight:700;'
        f'letter-spacing:.02em;">{company_esc}</div>'
        if show_company_text
        else ""
    )

    identity_html = ""
    if tenant is not None:
        from app.print_branding import company_identity_fields, company_letterhead_detail_lines

        ident = company_identity_fields(tenant)
        if company:
            ident["company_name"] = company
        detail_lines = company_letterhead_detail_lines(ident)
        if detail_lines:
            identity_html = (
                '<div class="ribdigi-email-identity" style="margin:8px 0 0;color:#e8f2df;'
                'font-size:12px;line-height:1.45;">'
                + "<br/>".join(html.escape(line) for line in detail_lines)
                + "</div>"
            )

    header_html = (
        f'<p class="ribdigi-email-header" style="margin:8px 0 0;color:#c8e86a;font-size:13px;">'
        f"{html.escape(header)}</p>"
        if header
        else ""
    )
    footer_html = (
        f'<p class="ribdigi-email-footer" style="margin:0 0 8px;color:#4d5d56;font-size:12px;">'
        f"{html.escape(footer)}</p>"
        if footer
        else ""
    )
    title_html = (
        f'<h1 style="margin:0 0 16px;font-size:20px;line-height:1.3;color:#10211b;">'
        f"{html.escape(title)}</h1>"
        if title
        else ""
    )

    return (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        f"<title>{html.escape(title or company)}</title></head>"
        '<body style="margin:0;padding:0;background:#f2f7ec;">'
        '<table role="presentation" class="ribdigi-email-brand" width="100%" cellspacing="0" '
        'cellpadding="0" style="background:#f2f7ec;padding:24px 12px;">'
        "<tr><td align=\"center\">"
        '<table role="presentation" width="600" cellspacing="0" cellpadding="0" '
        'style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;'
        'overflow:hidden;border:1px solid #d4e5c4;">'
        '<tr><td style="padding:20px 24px;background:#003d1f;color:#ffffff;text-align:center;'
        'font-family:Arial,Helvetica,sans-serif;border-bottom:3px solid #4ab012;">'
        f"{logo_html}"
        f"{company_html}"
        f"{identity_html}"
        f"{header_html}"
        "</td></tr>"
        '<tr><td style="padding:24px;font-family:Arial,Helvetica,sans-serif;color:#10211b;'
        'font-size:14px;line-height:1.55;">'
        f"{title_html}{body_html}"
        "</td></tr>"
        '<tr><td style="padding:16px 24px;background:#f5f7ec;border-top:1px solid #d4e5c4;'
        'text-align:center;font-family:Arial,Helvetica,sans-serif;">'
        f"{footer_html}"
        '<p style="margin:0;color:#4d5d56;font-size:11px;">Sent via Ribdigi House</p>'
        "</td></tr></table></td></tr></table></body></html>"
    )


def _split_content_type(content_type: str | None) -> tuple[str, str]:
    raw = (content_type or "application/octet-stream").strip()
    if "/" not in raw:
        return "application", "octet-stream"
    maintype, subtype = raw.split("/", 1)
    return maintype.strip() or "application", subtype.strip() or "octet-stream"


def _attach_files(msg: EmailMessage, attachments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Attach binary files; return lightweight metadata for outbox/logging."""
    meta: list[dict[str, Any]] = []
    for item in attachments or []:
        filename = str(item.get("filename") or "attachment.bin")
        content = item.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            raw = content.encode("utf-8")
        else:
            raw = bytes(content)
        maintype, subtype = _split_content_type(item.get("content_type"))
        msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=filename)
        meta.append(
            {
                "filename": filename,
                "content_type": f"{maintype}/{subtype}",
                "size_bytes": len(raw),
            }
        )
    return meta


def build_message(
    *,
    to: str | list[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    cfg: SmtpConfig | None = None,
    inline_images: list[tuple[str, bytes, str]] | None = None,
) -> EmailMessage:
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        raise HTTPException(status_code=400, detail="At least one recipient is required")
    c = cfg or resolve_smtp_config(None)
    msg = EmailMessage()
    msg["Subject"] = subject
    from_name = (c.from_name or "Ribdigi House").strip()
    from_email = (c.from_email or "noreply@localhost").strip()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
        if inline_images:
            # multipart/alternative → [text/plain, multipart/related → [text/html, image…]]
            html_part = msg.get_payload()[-1]
            for cid, data, subtype in inline_images:
                html_part.add_related(
                    data,
                    maintype="image",
                    subtype=subtype,
                    cid=f"<{cid}>",
                    filename=f"logo.{'jpg' if subtype == 'jpeg' else subtype}",
                    disposition="inline",
                )
    _attach_files(msg, attachments)
    return msg


def _smtp_send_sync(msg: EmailMessage, cfg: SmtpConfig) -> None:
    host = cfg.host
    port = int(cfg.port)
    timeout = float(settings.SMTP_TIMEOUT_SECONDS)
    user = (cfg.username or "").strip() or None
    password = cfg.password or None

    if cfg.use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=timeout) as server:
        server.ehlo()
        if cfg.use_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.send_message(msg)


async def send_email(
    *,
    to: str | list[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    tenant: Any | None = None,
    cfg: SmtpConfig | None = None,
) -> EmailResult:
    recipients = [to] if isinstance(to, str) else [r for r in to if r]
    c = cfg or resolve_smtp_config(tenant)
    mode = _delivery_mode(c)
    if mode == "disabled":
        return EmailResult(sent=False, mode="disabled", recipients=recipients)

    html_body, inline_images = _resolve_inline_images(html_body, tenant)
    msg = build_message(
        to=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        attachments=attachments,
        cfg=c,
        inline_images=inline_images,
    )
    attachment_meta = [
        {
            "filename": str(a.get("filename") or "attachment.bin"),
            "content_type": a.get("content_type") or "application/octet-stream",
            "size_bytes": len(a.get("content") or b"")
            if not isinstance(a.get("content"), str)
            else len(str(a.get("content")).encode("utf-8")),
        }
        for a in (attachments or [])
        if a.get("content") is not None
    ]
    record = {
        "to": recipients,
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
        "attachments": attachment_meta,
        "inline_images": [
            {"cid": cid, "content_type": f"image/{subtype}", "size_bytes": len(data)}
            for cid, data, subtype in inline_images
        ],
        "mode": mode,
    }

    if mode == "console":
        _DEV_OUTBOX.append(record)
        logger.info("EMAIL console to=%s subject=%s", recipients, subject)
        return EmailResult(sent=True, mode="console", recipients=recipients)

    try:
        await asyncio.to_thread(_smtp_send_sync, msg, c)
        _DEV_OUTBOX.append({**record, "delivered": True})
        return EmailResult(sent=True, mode="smtp", recipients=recipients)
    except Exception as exc:
        logger.exception("SMTP send failed")
        _DEV_OUTBOX.append({**record, "delivered": False, "error": str(exc)})
        return EmailResult(sent=False, mode="smtp", recipients=recipients, error=str(exc)[:500])


def verification_link(token: str) -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/verify-email?token={token}"


def password_reset_link(token: str) -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/reset-password?token={token}"


async def send_verification_email(
    *, to: str, token: str, company_name: str | None = None, tenant: Any | None = None
) -> EmailResult:
    try:
        link = verification_link(token)
        company = company_name or getattr(tenant, "company_name", None) or "Ribdigi House"
        subject = f"Verify your {company} email"
        text = (
            f"Welcome to {company}.\n\n"
            f"Verify your email by opening this link:\n{link}\n\n"
            f"If you did not create an account, ignore this message.\n"
        )
        # Platform noreply chrome uses the Ribdigi House logo (not plain text brand).
        # Tenant company name still appears in the welcome line when present.
        brand_company = company if not _is_platform_brand_name(company) else "Ribdigi House"
        inner = (
            f"<p>Welcome to <strong>{html.escape(company)}</strong>.</p>"
            f'<p><a href="{html.escape(link)}">Verify your email</a></p>'
            f"<p>Or paste: {html.escape(link)}</p>"
        )
        branded = render_branded_html(
            body_html=inner,
            company_name=brand_company,
            tenant=tenant,
            title="Verify your email",
            allow_platform_logo=True,
        )
        return await send_email(to=to, subject=subject, text_body=text, html_body=branded, tenant=tenant)
    except Exception:
        logger.exception("verification email failed")
        return EmailResult(sent=False, mode="error", error="send_failed")


async def send_password_reset_email(*, to: str, token: str, tenant: Any | None = None) -> EmailResult:
    link = password_reset_link(token)
    company = getattr(tenant, "company_name", None) or "RIBDIGI ERP"
    subject = "Reset your RIBDIGI ERP password"
    text = (
        "A password reset was requested for your account.\n\n"
        f"Reset link (expires in 1 hour):\n{link}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    inner = (
        "<p>A password reset was requested for your account.</p>"
        f'<p><a href="{html.escape(link)}">Reset password</a></p>'
        f"<p>Or paste: {html.escape(link)}</p>"
    )
    branded = render_branded_html(
        body_html=inner,
        company_name=company,
        tenant=tenant,
        title="Password reset",
        allow_platform_logo=True,
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=branded, tenant=tenant)


async def send_notification_email(
    *, to: str, title: str, message: str, category: str, tenant: Any | None = None
) -> EmailResult:
    subject = f"[RIBDIGI] {title}"
    text = f"{title}\n\n{message}\n\nCategory: {category}\n"
    company = getattr(tenant, "company_name", None) or "RIBDIGI ERP"
    inner = (
        f"<h3>{html.escape(title)}</h3>"
        f"<p>{html.escape(message)}</p>"
        f"<p><em>{html.escape(category)}</em></p>"
    )
    branded = render_branded_html(
        body_html=inner, company_name=company, tenant=tenant, title=title
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=branded, tenant=tenant)


def render_ai_insight_digest_bodies(
    *,
    company_name: str,
    insights: list[str],
    tenant: Any | None = None,
) -> tuple[str, str]:
    """Render the tenant-safe plain-text and HTML weekly digest."""
    company = (company_name or "RIBDIGI ERP").strip()
    notes = [str(note).strip() for note in insights if str(note).strip()]
    if not notes:
        notes = ["No urgent anomaly detected from the currently configured business rules."]

    text = "\n".join(
        [
            f"Weekly AI insight digest — {company}",
            "",
            *[f"{index}. {note}" for index, note in enumerate(notes, start=1)],
            "",
            "Open the RIBDIGI ERP dashboard to review the underlying business data.",
        ]
    )
    items = "".join(f"<li>{html.escape(note)}</li>" for note in notes)
    inner = (
        f"<ol>{items}</ol>"
        "<p>Open the RIBDIGI ERP dashboard to review the underlying business data.</p>"
    )
    html_body = render_branded_html(
        body_html=inner,
        company_name=company,
        tenant=tenant,
        title=f"Weekly AI insight digest — {company}",
    )
    return text, html_body


async def send_ai_insight_digest_email(
    *,
    to: str,
    company_name: str,
    insights: list[str],
    tenant: Any | None = None,
) -> EmailResult:
    text, html_body = render_ai_insight_digest_bodies(
        company_name=company_name,
        insights=insights,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Weekly AI insight digest — {company_name}",
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def _fmt_money(value: Any) -> str:
    try:
        return f"{money_json(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _fmt_doc_date(value: Any, tenant: Any | None = None) -> str:
    return format_tenant_date(value, tenant)


def _doc_line_row(*cells: str, right_from: int = 1) -> str:
    from app.print_branding import DOC_TD_RIGHT, DOC_TD_STYLE

    parts: list[str] = []
    for i, cell in enumerate(cells):
        style = DOC_TD_RIGHT if i >= right_from else DOC_TD_STYLE
        parts.append(f'<td style="{style}">{html.escape(str(cell))}</td>')
    return f"<tr>{''.join(parts)}</tr>"


def _doc_meta_block(html_inner: str) -> str:
    from app.print_branding import DOC_META_STYLE

    return f'<div style="{DOC_META_STYLE}">{html_inner}</div>'


def _doc_totals_block(lines: list[str], *, total_line: str) -> str:
    from app.print_branding import DOC_TOTALS_STYLE

    body = "<br/>".join(lines)
    return (
        f'<div style="{DOC_TOTALS_STYLE}">{body}<br/>'
        f'<strong style="color:#003d1f;font-size:15px;">{total_line}</strong></div>'
    )


def render_quotation_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    quotation: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    from app.print_branding import document_table_html

    number = quotation.get("quotation_number") or ""
    quote_date = _fmt_doc_date(
        first_document_date(quotation, "created_at", "quote_date", "quotation_date"),
        tenant,
    )
    valid_s = _fmt_doc_date(quotation.get("valid_until"), tenant)
    lines = [
        f"Quotation {number}",
        f"From: {company_name}",
        f"To: {customer_name}",
    ]
    if quote_date:
        lines.append(f"Quote date: {quote_date}")
    if valid_s:
        lines.append(f"Valid until: {valid_s} (this offer expires on this date)")
    lines.extend(["", "Items:"])
    html_rows = []
    for item in quotation.get("items") or []:
        desc = document_item_label(item)
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        lines.append(f"  - {desc}: qty {qty} × {currency} {price} = {currency} {total}")
        html_rows.append(
            _doc_line_row(str(desc), str(qty), f"{currency} {price}", f"{currency} {total}")
        )
    lines.extend(
        [
            "",
            f"Subtotal: {currency} {_fmt_money(quotation.get('subtotal'))}",
            f"Tax: {currency} {_fmt_money(quotation.get('tax_amount'))}",
            f"Discount: {currency} {_fmt_money(quotation.get('discount_amount'))}",
            f"Total: {currency} {_fmt_money(quotation.get('total_amount'))}",
        ]
    )
    if quotation.get("notes"):
        lines.extend(["", f"Notes: {quotation['notes']}"])
    lines.append("\nThank you for your business.")
    text = "\n".join(lines)
    inner = (
        _doc_meta_block(
            f"From <strong>{html.escape(company_name)}</strong><br/>"
            f"To {html.escape(str(customer_name))}"
            + (f"<br/>Quote date {html.escape(quote_date)}" if quote_date else "")
            + (
                f"<br/>Valid until {html.escape(valid_s)} — this offer expires on this date"
                if valid_s
                else ""
            )
        )
        + document_table_html(
            headers=["Item", "Qty", "Price", "Line"],
            rows_html="".join(html_rows),
        )
        + _doc_totals_block(
            [
                f"Subtotal: {html.escape(currency)} {_fmt_money(quotation.get('subtotal'))}",
                f"Tax: {html.escape(currency)} {_fmt_money(quotation.get('tax_amount'))}",
                f"Discount: {html.escape(currency)} {_fmt_money(quotation.get('discount_amount'))}",
            ],
            total_line=f"Total: {html.escape(currency)} {_fmt_money(quotation.get('total_amount'))}",
        )
    )
    if quotation.get("notes"):
        inner += f"<p style=\"margin:14px 0 0;color:#4d5d56;\">Notes: {html.escape(str(quotation['notes']))}</p>"
    branded = render_branded_html(
        body_html=inner,
        company_name=company_name,
        tenant=tenant,
        title=f"Quotation {number}",
    )
    return text, branded


async def send_quotation_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    quotation: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = quotation.get("quotation_number") or ""
    subject = f"Quotation {number} from {company_name}"
    text, html_body = render_quotation_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        quotation=quotation,
        tenant=tenant,
    )
    return await send_email(
        to=to, subject=subject, text_body=text, html_body=html_body, tenant=tenant
    )


def render_purchase_order_bodies(
    *,
    company_name: str,
    currency: str,
    supplier_name: str,
    purchase_order: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    from app.print_branding import document_table_html

    number = purchase_order.get("po_number") or ""
    order_date = _fmt_doc_date(
        first_document_date(purchase_order, "created_at", "order_date"),
        tenant,
    )
    due_s = _fmt_doc_date(purchase_order.get("due_date"), tenant)
    delivery_address = (purchase_order.get("delivery_address") or "").strip()
    lines = [
        f"Purchase Order {number}",
        f"From: {company_name}",
        f"To: {supplier_name}",
    ]
    if order_date:
        lines.append(f"Order date: {order_date}")
    if due_s:
        lines.append(f"Needed by: {due_s} (when we expect these goods delivered)")
    if delivery_address:
        lines.append(f"Delivery address: {delivery_address}")
    lines.extend(
        [
            "",
            "Items:",
        ]
    )
    html_rows = []
    for item in purchase_order.get("items") or []:
        desc = document_item_label(item)
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        tax = _fmt_money(item.get("tax_rate"))
        disc = money_json(item.get("discount") or 0)
        disc_s = f" discount {currency} {_fmt_money(disc)}" if disc else ""
        lines.append(
            f"  - {desc}: qty {qty} × {currency} {price} (tax {tax}%{disc_s}) = {currency} {total}"
        )
        disc_cell = _fmt_money(disc) if disc else "—"
        html_rows.append(
            _doc_line_row(
                str(desc),
                str(qty),
                f"{currency} {price}",
                f"{tax}%",
                f"{currency} {disc_cell}",
                f"{currency} {total}",
            )
        )
    lines.extend(
        [
            "",
            f"Subtotal: {currency} {_fmt_money(purchase_order.get('subtotal'))}",
            f"Tax: {currency} {_fmt_money(purchase_order.get('tax_amount'))}",
            f"Total: {currency} {_fmt_money(purchase_order.get('total_amount'))}",
        ]
    )
    if purchase_order.get("notes"):
        lines.extend(["", f"Notes: {purchase_order['notes']}"])
    lines.append("\nPlease confirm this purchase order.")
    text = "\n".join(lines)
    delivery_html = (
        f"<br/>Delivery address: {html.escape(delivery_address)}" if delivery_address else ""
    )
    inner = (
        _doc_meta_block(
            f"From <strong>{html.escape(company_name)}</strong><br/>"
            f"To {html.escape(str(supplier_name))}"
            + (f"<br/>Order date {html.escape(order_date)}" if order_date else "")
            + (
                f"<br/>Needed by {html.escape(due_s)} — when we expect these goods delivered"
                if due_s
                else ""
            )
            + f"{delivery_html}"
        )
        + document_table_html(
            headers=["Item", "Qty", "Price", "Tax", "Discount", "Line"],
            rows_html="".join(html_rows),
        )
        + _doc_totals_block(
            [
                f"Subtotal: {html.escape(currency)} {_fmt_money(purchase_order.get('subtotal'))}",
                f"Tax: {html.escape(currency)} {_fmt_money(purchase_order.get('tax_amount'))}",
            ],
            total_line=(
                f"Total: {html.escape(currency)} {_fmt_money(purchase_order.get('total_amount'))}"
            ),
        )
    )
    if purchase_order.get("notes"):
        inner += f"<p style=\"margin:14px 0 0;color:#4d5d56;\">Notes: {html.escape(str(purchase_order['notes']))}</p>"
    branded = render_branded_html(
        body_html=inner,
        company_name=company_name,
        tenant=tenant,
        title=f"Purchase Order {number}",
    )
    return text, branded


async def send_purchase_order_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    supplier_name: str,
    purchase_order: dict[str, Any],
    amended: bool = False,
    tenant: Any | None = None,
) -> EmailResult:
    number = purchase_order.get("po_number") or ""
    rev = purchase_order.get("revision_no")
    if amended and rev:
        subject = f"Purchase Order {number} (amended rev.{rev}) from {company_name}"
    else:
        subject = f"Purchase Order {number} from {company_name}"
    text, html_body = render_purchase_order_bodies(
        company_name=company_name,
        currency=currency,
        supplier_name=supplier_name,
        purchase_order=purchase_order,
        tenant=tenant,
    )
    return await send_email(
        to=to, subject=subject, text_body=text, html_body=html_body, tenant=tenant
    )


def render_sales_invoice_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    invoice: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    from app.print_branding import document_table_html

    number = invoice.get("invoice_number") or ""
    invoice_date = _fmt_doc_date(
        first_document_date(invoice, "posted_at", "invoice_date", "created_at"),
        tenant,
    )
    due_s = _fmt_doc_date(invoice.get("due_date"), tenant)
    lines = [
        f"Sales Invoice {number}",
        f"From: {company_name}",
        f"To: {customer_name}",
    ]
    if invoice_date:
        lines.append(f"Invoice date: {invoice_date}")
    if due_s:
        lines.append(f"Payment due date: {due_s} (please pay the balance by this date)")
    lines.extend(["", "Items:"])
    html_rows = []
    for item in invoice.get("items") or []:
        desc = document_item_label(item)
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        tax = _fmt_money(item.get("tax_rate"))
        lines.append(
            f"  - {desc}: qty {qty} × {currency} {price} (tax {tax}%) = {currency} {total}"
        )
        html_rows.append(
            _doc_line_row(
                str(desc),
                str(qty),
                f"{currency} {price}",
                f"{tax}%",
                f"{currency} {total}",
            )
        )
    lines.extend(
        [
            "",
            f"Subtotal: {currency} {_fmt_money(invoice.get('subtotal'))}",
            f"Tax: {currency} {_fmt_money(invoice.get('tax_amount'))}",
            f"Discount: {currency} {_fmt_money(invoice.get('discount_amount'))}",
            f"Total: {currency} {_fmt_money(invoice.get('total_amount'))}",
            f"Paid: {currency} {_fmt_money(invoice.get('paid_amount'))}",
            f"Balance due: {currency} {_fmt_money(invoice.get('balance_due'))}",
        ]
    )
    if invoice.get("notes"):
        lines.extend(["", f"Notes: {invoice['notes']}"])
    lines.append("\nThank you for your business.")
    text = "\n".join(lines)
    inner = (
        _doc_meta_block(
            f"From <strong>{html.escape(company_name)}</strong><br/>"
            f"To {html.escape(str(customer_name))}"
            + (f"<br/>Invoice date {html.escape(invoice_date)}" if invoice_date else "")
            + (
                f"<br/>Payment due date {html.escape(due_s)} — please pay the balance by this date"
                if due_s
                else ""
            )
        )
        + document_table_html(
            headers=["Item", "Qty", "Price", "Tax", "Line"],
            rows_html="".join(html_rows),
        )
        + _doc_totals_block(
            [
                f"Subtotal: {html.escape(currency)} {_fmt_money(invoice.get('subtotal'))}",
                f"Tax: {html.escape(currency)} {_fmt_money(invoice.get('tax_amount'))}",
                f"Discount: {html.escape(currency)} {_fmt_money(invoice.get('discount_amount'))}",
                f"Paid: {html.escape(currency)} {_fmt_money(invoice.get('paid_amount'))}",
                f"Balance due: {html.escape(currency)} {_fmt_money(invoice.get('balance_due'))}",
            ],
            total_line=f"Total: {html.escape(currency)} {_fmt_money(invoice.get('total_amount'))}",
        )
    )
    if invoice.get("notes"):
        inner += f"<p style=\"margin:14px 0 0;color:#4d5d56;\">Notes: {html.escape(str(invoice['notes']))}</p>"
    branded = render_branded_html(
        body_html=inner,
        company_name=company_name,
        tenant=tenant,
        title=f"Sales Invoice {number}",
    )
    return text, branded


async def send_sales_invoice_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    invoice: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = invoice.get("invoice_number") or ""
    subject = f"Invoice {number} from {company_name}"
    text, html_body = render_sales_invoice_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        invoice=invoice,
        tenant=tenant,
    )
    return await send_email(
        to=to, subject=subject, text_body=text, html_body=html_body, tenant=tenant
    )


def _catalog_item_text(item: dict[str, Any], currency: str, *, kind: str) -> str:
    desc = document_item_label(item)
    if kind == "grn":
        return (
            f"  - {desc}: received {item.get('received_qty')} · "
            f"accepted {item.get('accepted_qty')} · rejected {item.get('rejected_qty')}"
        )
    if kind == "request":
        notes = str(item.get("notes") or "").strip()
        extra = f" ({notes})" if notes else ""
        return f"  - {desc}: qty {item.get('quantity')}{extra}"
    qty = item.get("quantity")
    price = _fmt_money(item.get("unit_price"))
    total = _fmt_money(item.get("line_total"))
    tax = item.get("tax_rate")
    tax_s = f" (tax {_fmt_money(tax)}%)" if tax is not None else ""
    return f"  - {desc}: qty {qty} × {currency} {price}{tax_s} = {currency} {total}"


def _catalog_item_row(item: dict[str, Any], currency: str, *, kind: str) -> str:
    desc = document_item_label(item)
    if kind == "grn":
        return _doc_line_row(
            str(desc),
            str(item.get("received_qty") if item.get("received_qty") is not None else ""),
            str(item.get("accepted_qty") if item.get("accepted_qty") is not None else ""),
            str(item.get("rejected_qty") if item.get("rejected_qty") is not None else ""),
            right_from=1,
        )
    if kind == "request":
        return _doc_line_row(
            str(desc),
            str(item.get("quantity") if item.get("quantity") is not None else ""),
            str(item.get("notes") or "—"),
            right_from=1,
        )
    return _doc_line_row(
        str(desc),
        str(item.get("quantity") if item.get("quantity") is not None else ""),
        f"{currency} {_fmt_money(item.get('unit_price'))}",
        f"{_fmt_money(item.get('tax_rate'))}%",
        f"{currency} {_fmt_money(item.get('line_total'))}",
    )


def render_catalog_document_bodies(
    *,
    title: str,
    company_name: str,
    currency: str,
    party_name: str,
    document: dict[str, Any],
    tenant: Any | None = None,
    date_label: str = "Date",
    date_keys: tuple[str, ...] = ("created_at",),
    extra_date_label: str | None = None,
    extra_date_key: str | None = None,
    extra_date_hint: str | None = None,
    extra_meta: list[str] | None = None,
    item_kind: str = "priced",
    item_headers: list[str] | None = None,
    totals: list[tuple[str, Any]] | None = None,
    total_label: str = "Total",
    total_key: str = "total_amount",
    closing: str = "Thank you for your business.",
) -> tuple[str, str]:
    """Shared branded HTML + text for commercial documents with optional lines."""
    from app.print_branding import document_table_html

    date_s = _fmt_doc_date(first_document_date(document, *date_keys), tenant)
    extra_s = _fmt_doc_date(document.get(extra_date_key), tenant) if extra_date_key else ""
    lines = [title, f"From: {company_name}", f"To: {party_name}"]
    if date_s:
        lines.append(f"{date_label}: {date_s}")
    if extra_s and extra_date_label:
        hint = f" ({extra_date_hint})" if extra_date_hint else ""
        lines.append(f"{extra_date_label}: {extra_s}{hint}")
    for meta in extra_meta or []:
        if str(meta or "").strip():
            lines.append(str(meta))
    html_rows: list[str] = []
    items = list(document.get("items") or [])
    if item_kind != "none":
        lines.extend(["", "Items:"])
        for item in items:
            lines.append(_catalog_item_text(item, currency, kind=item_kind))
            html_rows.append(_catalog_item_row(item, currency, kind=item_kind))
    totals = totals if totals is not None else [
        ("Subtotal", document.get("subtotal")),
        ("Tax", document.get("tax_amount")),
        ("Discount", document.get("discount_amount")),
    ]
    shown_totals = [
        (label, value)
        for label, value in totals
        if value is not None and not (label == "Discount" and not money_json(value or 0))
    ]
    total_value = document.get(total_key) if total_key else None
    if shown_totals or total_key:
        lines.append("")
    for label, value in shown_totals:
        lines.append(f"{label}: {currency} {_fmt_money(value)}")
    if total_key:
        lines.append(f"{total_label}: {currency} {_fmt_money(total_value)}")
    if document.get("notes"):
        lines.extend(["", f"Notes: {document['notes']}"])
    lines.append(f"\n{closing}")
    text = "\n".join(lines)
    meta_html = (
        f"From <strong>{html.escape(company_name)}</strong><br/>"
        f"To {html.escape(str(party_name))}"
        + (f"<br/>{html.escape(date_label)} {html.escape(date_s)}" if date_s else "")
        + (
            f"<br/>{html.escape(extra_date_label)} {html.escape(extra_s)}"
            + (f" — {html.escape(extra_date_hint)}" if extra_date_hint else "")
            if extra_s and extra_date_label
            else ""
        )
    )
    for meta in extra_meta or []:
        if str(meta or "").strip():
            meta_html += f"<br/>{html.escape(str(meta))}"
    inner = _doc_meta_block(meta_html)
    if item_kind != "none":
        headers = item_headers or {
            "priced": ["Item", "Qty", "Price", "Tax", "Line"],
            "grn": ["Item", "Received", "Accepted", "Rejected"],
            "request": ["Item", "Qty", "Notes"],
        }.get(item_kind, ["Item", "Qty", "Price", "Tax", "Line"])
        inner += document_table_html(headers=headers, rows_html="".join(html_rows))
    if shown_totals or total_key:
        inner += _doc_totals_block(
            [
                f"{html.escape(label)}: {html.escape(currency)} {_fmt_money(value)}"
                for label, value in shown_totals
            ],
            total_line=(
                f"{html.escape(total_label)}: {html.escape(currency)} {_fmt_money(total_value)}"
                if total_key
                else ""
            ),
        )
    if document.get("notes"):
        inner += (
            f'<p style="margin:14px 0 0;color:#4d5d56;">Notes: '
            f"{html.escape(str(document['notes']))}</p>"
        )
    branded = render_branded_html(
        body_html=inner,
        company_name=company_name,
        tenant=tenant,
        title=title,
    )
    return text, branded


def render_sales_order_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    order: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = order.get("order_number") or ""
    ship = str(order.get("delivery_address") or "").strip()
    return render_catalog_document_bodies(
        title=f"Sales Order {number}".strip() or "Sales Order",
        company_name=company_name,
        currency=currency,
        party_name=customer_name,
        document=order,
        tenant=tenant,
        date_label="Order date",
        date_keys=("created_at", "order_date"),
        extra_date_label="Delivery date",
        extra_date_key="delivery_date",
        extra_date_hint="when we expect to deliver these goods",
        extra_meta=[f"Ship to: {ship}"] if ship else None,
        closing="Thank you for your business.",
    )


async def send_sales_order_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    order: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = order.get("order_number") or ""
    text, html_body = render_sales_order_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        order=order,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Sales order {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def render_sales_return_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    ret: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = ret.get("return_number") or ""
    credit = ret.get("credit_note_number") or ""
    title = f"Credit Note {credit}".strip() if credit else f"Sales Return {number}".strip()
    extra = [f"Return {number}"] if credit and number else []
    if ret.get("reason"):
        extra.append(f"Reason: {ret.get('reason')}")
    return render_catalog_document_bodies(
        title=title or "Credit Note",
        company_name=company_name,
        currency=currency,
        party_name=customer_name,
        document=ret,
        tenant=tenant,
        date_label="Return date",
        date_keys=("posted_at", "created_at"),
        extra_meta=extra,
        totals=[("Subtotal", ret.get("subtotal")), ("Tax", ret.get("tax_amount"))],
        closing="This credit note reduces the amount owed.",
    )


async def send_sales_return_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    ret: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = ret.get("credit_note_number") or ret.get("return_number") or ""
    text, html_body = render_sales_return_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        ret=ret,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Credit note {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def render_payment_receipt_bodies(
    *,
    title: str,
    company_name: str,
    currency: str,
    party_name: str,
    payment: dict[str, Any],
    tenant: Any | None = None,
    extra_meta: list[str] | None = None,
    total_label: str = "Received",
    closing: str = "Thank you for your payment.",
) -> tuple[str, str]:
    return render_catalog_document_bodies(
        title=title,
        company_name=company_name,
        currency=currency,
        party_name=party_name,
        document=payment,
        tenant=tenant,
        date_label="Date",
        date_keys=("created_at", "payment_date"),
        extra_meta=extra_meta,
        item_kind="none",
        totals=[],
        total_label=total_label,
        total_key="amount",
        closing=closing,
    )


async def send_customer_payment_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    payment: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = payment.get("payment_number") or ""
    extra = []
    if payment.get("invoice_number"):
        extra.append(f"Invoice: {payment.get('invoice_number')}")
    if payment.get("payment_method"):
        extra.append(f"Method: {str(payment.get('payment_method')).replace('_', ' ')}")
    if payment.get("reference"):
        extra.append(f"Ref: {payment.get('reference')}")
    text, html_body = render_payment_receipt_bodies(
        title=f"Payment Receipt {number}".strip() or "Payment Receipt",
        company_name=company_name,
        currency=currency,
        party_name=customer_name,
        payment=payment,
        tenant=tenant,
        extra_meta=extra,
        total_label="Received",
        closing="Thank you for your payment.",
    )
    return await send_email(
        to=to,
        subject=f"Payment receipt {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def render_purchase_request_bodies(
    *,
    company_name: str,
    currency: str,
    party_name: str,
    request: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = request.get("request_number") or ""
    extra = []
    if request.get("department"):
        extra.append(f"Department: {request.get('department')}")
    return render_catalog_document_bodies(
        title=f"Purchase Request {number}".strip() or "Purchase Request",
        company_name=company_name,
        currency=currency,
        party_name=party_name or "—",
        document=request,
        tenant=tenant,
        date_label="Request date",
        date_keys=("created_at",),
        extra_date_label="Needed by",
        extra_date_key="required_date",
        extra_date_hint="when these goods are needed",
        extra_meta=extra,
        item_kind="request",
        totals=[],
        total_key="",
        closing="Please review this purchase request.",
    )


async def send_purchase_request_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    party_name: str,
    request: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = request.get("request_number") or ""
    text, html_body = render_purchase_request_bodies(
        company_name=company_name,
        currency=currency,
        party_name=party_name,
        request=request,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Purchase request {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def render_grn_bodies(
    *,
    company_name: str,
    currency: str,
    supplier_name: str,
    grn: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = grn.get("grn_number") or ""
    extra = []
    if grn.get("po_number"):
        extra.append(f"Purchase order: {grn.get('po_number')}")
    return render_catalog_document_bodies(
        title=f"Goods Received {number}".strip() or "Goods Received",
        company_name=company_name,
        currency=currency,
        party_name=supplier_name,
        document=grn,
        tenant=tenant,
        date_label="Date received",
        date_keys=("received_at", "created_at"),
        extra_meta=extra,
        item_kind="grn",
        totals=[],
        total_key="",
        closing="Please keep this goods received note for your records.",
    )


async def send_grn_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    supplier_name: str,
    grn: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = grn.get("grn_number") or ""
    text, html_body = render_grn_bodies(
        company_name=company_name,
        currency=currency,
        supplier_name=supplier_name,
        grn=grn,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Goods received {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def render_purchase_invoice_bodies(
    *,
    company_name: str,
    currency: str,
    supplier_name: str,
    invoice: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = invoice.get("invoice_number") or ""
    extra = []
    if invoice.get("supplier_invoice_number"):
        extra.append(f"Supplier #: {invoice.get('supplier_invoice_number')}")
    return render_catalog_document_bodies(
        title=f"Supplier Bill {number}".strip() or "Supplier Bill",
        company_name=company_name,
        currency=currency,
        party_name=supplier_name,
        document=invoice,
        tenant=tenant,
        date_label="Bill date",
        date_keys=("invoice_date", "created_at"),
        extra_date_label="Payment due date",
        extra_date_key="due_date",
        extra_date_hint="please settle the balance by this date",
        extra_meta=extra,
        totals=[
            ("Subtotal", invoice.get("subtotal")),
            ("Tax", invoice.get("tax_amount")),
            ("Discount", invoice.get("discount_amount")),
            ("Paid", invoice.get("paid_amount")),
            ("Balance due", invoice.get("balance_due")),
        ],
        closing="Please keep this supplier bill for your records.",
    )


async def send_purchase_invoice_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    supplier_name: str,
    invoice: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = invoice.get("invoice_number") or ""
    text, html_body = render_purchase_invoice_bodies(
        company_name=company_name,
        currency=currency,
        supplier_name=supplier_name,
        invoice=invoice,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Supplier bill {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def render_purchase_return_bodies(
    *,
    company_name: str,
    currency: str,
    supplier_name: str,
    ret: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = ret.get("return_number") or ""
    debit = ret.get("debit_note_number") or ""
    title = f"Debit Note {debit}".strip() if debit else f"Purchase Return {number}".strip()
    extra = [f"Return {number}"] if debit and number else []
    if ret.get("reason"):
        extra.append(f"Reason: {ret.get('reason')}")
    return render_catalog_document_bodies(
        title=title or "Debit Note",
        company_name=company_name,
        currency=currency,
        party_name=supplier_name,
        document=ret,
        tenant=tenant,
        date_label="Return date",
        date_keys=("posted_at", "created_at"),
        extra_meta=extra,
        totals=[("Subtotal", ret.get("subtotal")), ("Tax", ret.get("tax_amount"))],
        closing="This debit note reduces the amount we owe.",
    )


async def send_purchase_return_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    supplier_name: str,
    ret: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = ret.get("debit_note_number") or ret.get("return_number") or ""
    text, html_body = render_purchase_return_bodies(
        company_name=company_name,
        currency=currency,
        supplier_name=supplier_name,
        ret=ret,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Debit note {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


async def send_supplier_payment_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    supplier_name: str,
    payment: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = payment.get("payment_number") or ""
    extra = []
    if payment.get("bill_number"):
        extra.append(f"Bill: {payment.get('bill_number')}")
    if payment.get("payment_method"):
        extra.append(f"Method: {str(payment.get('payment_method')).replace('_', ' ')}")
    if payment.get("reference"):
        extra.append(f"Ref: {payment.get('reference')}")
    text, html_body = render_payment_receipt_bodies(
        title=f"Supplier Payment {number}".strip() or "Supplier Payment",
        company_name=company_name,
        currency=currency,
        party_name=supplier_name,
        payment=payment,
        tenant=tenant,
        extra_meta=extra,
        total_label="Paid",
        closing="Please keep this payment receipt for your records.",
    )
    return await send_email(
        to=to,
        subject=f"Supplier payment {number} from {company_name}".strip(),
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


async def send_test_email(*, to: str, tenant: Any | None = None) -> EmailResult:
    c = resolve_smtp_config(tenant)
    if not c.enabled:
        raise HTTPException(status_code=400, detail="EMAIL_ENABLED is false")
    mode = _delivery_mode(c)
    if not c.configured and mode != "console":
        raise HTTPException(status_code=400, detail="SMTP is not configured")
    company = getattr(tenant, "company_name", None) or "RIBDIGI ERP"
    inner = (
        f"<p>This is a test email from <strong>{html.escape(company)}</strong>. "
        "SMTP delivery is working.</p>"
        "<p>Your company logo, print header, and footer (Company → Print branding) "
        "appear in the chrome of outbound emails.</p>"
    )
    branded = render_branded_html(
        body_html=inner,
        company_name=company,
        tenant=tenant,
        title="Test email",
    )
    return await send_email(
        to=to,
        subject="RIBDIGI ERP test email",
        text_body=(
            f"This is a test email from {company}. SMTP delivery is working.\n"
            "Your company logo, print header, and footer appear on outbound emails.\n"
        ),
        html_body=branded,
        cfg=c,
        tenant=tenant,
    )
