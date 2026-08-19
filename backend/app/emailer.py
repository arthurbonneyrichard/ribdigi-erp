"""Outbound email via SMTP with safe development fallback."""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory outbox for tests / development inspection
_DEV_OUTBOX: list[dict[str, Any]] = []


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


def smtp_configured() -> bool:
    return bool((settings.SMTP_HOST or "").strip() and (settings.SMTP_FROM_EMAIL or "").strip())


def _tenant_smtp_ready(tenant: Any | None) -> bool:
    if tenant is None or not bool(getattr(tenant, "smtp_enabled", False)):
        return False
    host = (getattr(tenant, "smtp_host", None) or "").strip()
    from_email = (getattr(tenant, "smtp_from_email", None) or "").strip()
    return bool(host and from_email)


def resolve_smtp_config(tenant: Any | None = None) -> dict[str, Any]:
    """Effective SMTP settings: tenant override when enabled, else deployment env."""
    if _tenant_smtp_ready(tenant):
        password = None
        enc = getattr(tenant, "smtp_password_enc", None)
        if enc:
            from app.totp import decrypt_secret

            try:
                password = decrypt_secret(enc)
            except Exception:
                password = None
        return {
            "source": "tenant",
            "enabled": True,
            "host": (tenant.smtp_host or "").strip(),
            "port": int(tenant.smtp_port or 587),
            "username": (tenant.smtp_username or "").strip() or None,
            "password": password,
            "from_email": (tenant.smtp_from_email or "").strip(),
            "from_name": (tenant.smtp_from_name or settings.SMTP_FROM_NAME or "RIBDIGI ERP").strip(),
            "use_tls": bool(getattr(tenant, "smtp_use_tls", True)),
            "use_ssl": bool(getattr(tenant, "smtp_use_ssl", False)),
        }
    return {
        "source": "env",
        "enabled": bool(settings.EMAIL_ENABLED),
        "host": (settings.SMTP_HOST or "").strip(),
        "port": int(settings.SMTP_PORT),
        "username": (settings.SMTP_USER or "").strip() or None,
        "password": settings.SMTP_PASSWORD or None,
        "from_email": (settings.SMTP_FROM_EMAIL or "").strip(),
        "from_name": (settings.SMTP_FROM_NAME or "RIBDIGI ERP").strip(),
        "use_tls": bool(settings.SMTP_USE_TLS),
        "use_ssl": bool(settings.SMTP_USE_SSL),
    }


def email_status(tenant: Any | None = None) -> dict:
    cfg = resolve_smtp_config(tenant)
    configured = bool(cfg["host"] and cfg["from_email"])
    mode = "disabled"
    if settings.EMAIL_ENABLED:
        mode = "smtp" if configured else "console"
    return {
        "enabled": bool(settings.EMAIL_ENABLED),
        "configured": configured,
        "mode": mode,
        "source": cfg["source"],
        "host": cfg["host"] or None,
        "port": cfg["port"],
        "from_email": cfg["from_email"] or None,
        "from_name": cfg["from_name"],
        "use_tls": bool(cfg["use_tls"]),
        "use_ssl": bool(cfg["use_ssl"]),
        "username": cfg["username"],
        "has_password": bool(cfg["password"]),
        "tenant_override_enabled": bool(getattr(tenant, "smtp_enabled", False)) if tenant else False,
        "frontend_url": settings.FRONTEND_URL,
    }


def _delivery_mode(tenant: Any | None = None) -> str:
    if not settings.EMAIL_ENABLED:
        return "disabled"
    cfg = resolve_smtp_config(tenant)
    if cfg["host"] and cfg["from_email"]:
        return "smtp"
    return "console"


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
    smtp_config: dict[str, Any] | None = None,
) -> EmailMessage:
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        raise HTTPException(status_code=400, detail="At least one recipient is required")
    cfg = smtp_config or resolve_smtp_config()
    msg = EmailMessage()
    msg["Subject"] = subject
    from_name = (cfg.get("from_name") or "RIBDIGI ERP").strip()
    from_email = (cfg.get("from_email") or "noreply@localhost").strip()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    _attach_files(msg, attachments)
    return msg


def _smtp_send_sync(msg: EmailMessage, smtp_config: dict[str, Any] | None = None) -> None:
    cfg = smtp_config or resolve_smtp_config()
    host = cfg["host"]
    port = int(cfg["port"] or 587)
    timeout = float(settings.SMTP_TIMEOUT_SECONDS)
    user = (cfg.get("username") or "").strip() or None
    password = cfg.get("password") or None

    if cfg.get("use_ssl"):
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=timeout) as server:
        server.ehlo()
        if cfg.get("use_tls"):
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
) -> EmailResult:
    recipients = [to] if isinstance(to, str) else [r for r in to if r]
    mode = _delivery_mode(tenant)
    if mode == "disabled":
        return EmailResult(sent=False, mode="disabled", recipients=recipients)

    cfg = resolve_smtp_config(tenant)
    msg = build_message(
        to=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        attachments=attachments,
        smtp_config=cfg,
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
        "mode": mode,
        "source": cfg.get("source"),
    }

    if mode == "console":
        _DEV_OUTBOX.append(record)
        logger.info("EMAIL console to=%s subject=%s", recipients, subject)
        return EmailResult(sent=True, mode="console", recipients=recipients)

    try:
        await asyncio.to_thread(_smtp_send_sync, msg, cfg)
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


async def send_verification_email(*, to: str, token: str, company_name: str | None = None) -> EmailResult:
    link = verification_link(token)
    company = company_name or "RIBDIGI ERP"
    subject = f"Verify your {company} email"
    text = (
        f"Welcome to {company}.\n\n"
        f"Verify your email by opening this link:\n{link}\n\n"
        f"If you did not create an account, ignore this message.\n"
    )
    html = (
        f"<p>Welcome to <strong>{company}</strong>.</p>"
        f"<p><a href=\"{link}\">Verify your email</a></p>"
        f"<p>Or paste: {link}</p>"
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=html)


async def send_password_reset_email(*, to: str, token: str) -> EmailResult:
    link = password_reset_link(token)
    subject = "Reset your RIBDIGI ERP password"
    text = (
        "A password reset was requested for your account.\n\n"
        f"Reset link (expires in 1 hour):\n{link}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html = (
        "<p>A password reset was requested for your account.</p>"
        f"<p><a href=\"{link}\">Reset password</a></p>"
        f"<p>Or paste: {link}</p>"
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=html)


async def send_notification_email(*, to: str, title: str, message: str, category: str) -> EmailResult:
    subject = f"[RIBDIGI] {title}"
    text = f"{title}\n\n{message}\n\nCategory: {category}\n"
    html = f"<h3>{title}</h3><p>{message}</p><p><em>{category}</em></p>"
    return await send_email(to=to, subject=subject, text_body=text, html_body=html)


def _fmt_money(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def render_quotation_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    quotation: dict[str, Any],
) -> tuple[str, str]:
    number = quotation.get("quotation_number") or ""
    valid = quotation.get("valid_until")
    valid_s = str(valid)[:10] if valid else "—"
    lines = [
        f"Quotation {number}",
        f"From: {company_name}",
        f"To: {customer_name}",
        f"Valid until: {valid_s}",
        "",
        "Items:",
    ]
    html_rows = []
    for item in quotation.get("items") or []:
        desc = item.get("product_id") or "Item"
        if item.get("variant_id"):
            desc = f"{desc} (variant {item['variant_id'][:8]})"
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        lines.append(f"  - {desc}: qty {qty} × {currency} {price} = {currency} {total}")
        html_rows.append(
            f"<tr><td>{desc}</td><td>{qty}</td><td>{currency} {price}</td><td>{currency} {total}</td></tr>"
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
    html = (
        f"<h2>Quotation {number}</h2>"
        f"<p>From <strong>{company_name}</strong><br/>To {customer_name}<br/>Valid until {valid_s}</p>"
        "<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\">"
        "<thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Line</th></tr></thead>"
        f"<tbody>{''.join(html_rows)}</tbody></table>"
        f"<p>Subtotal: {currency} {_fmt_money(quotation.get('subtotal'))}<br/>"
        f"Tax: {currency} {_fmt_money(quotation.get('tax_amount'))}<br/>"
        f"Discount: {currency} {_fmt_money(quotation.get('discount_amount'))}<br/>"
        f"<strong>Total: {currency} {_fmt_money(quotation.get('total_amount'))}</strong></p>"
    )
    if quotation.get("notes"):
        html += f"<p>Notes: {quotation['notes']}</p>"
    return text, html


async def send_quotation_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    quotation: dict[str, Any],
) -> EmailResult:
    number = quotation.get("quotation_number") or ""
    subject = f"Quotation {number} from {company_name}"
    text, html = render_quotation_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        quotation=quotation,
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=html)


def render_invoice_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    invoice: dict[str, Any],
) -> tuple[str, str]:
    number = invoice.get("invoice_number") or ""
    due = invoice.get("due_date")
    due_s = str(due)[:10] if due else "—"
    lines = [
        f"Invoice {number}",
        f"From: {company_name}",
        f"To: {customer_name}",
        f"Due date: {due_s}",
        f"Status: {invoice.get('status')}",
        "",
        "Items:",
    ]
    html_rows = []
    for item in invoice.get("items") or []:
        desc = item.get("product_id") or "Item"
        if item.get("variant_id"):
            desc = f"{desc} (variant {str(item['variant_id'])[:8]})"
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        lines.append(f"  - {desc}: qty {qty} × {currency} {price} = {currency} {total}")
        html_rows.append(
            f"<tr><td>{desc}</td><td>{qty}</td><td>{currency} {price}</td><td>{currency} {total}</td></tr>"
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
    html = (
        f"<h2>Invoice {number}</h2>"
        f"<p>From <strong>{company_name}</strong><br/>To {customer_name}<br/>Due {due_s}</p>"
        "<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\">"
        "<thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Line</th></tr></thead>"
        f"<tbody>{''.join(html_rows)}</tbody></table>"
        f"<p>Subtotal: {currency} {_fmt_money(invoice.get('subtotal'))}<br/>"
        f"Tax: {currency} {_fmt_money(invoice.get('tax_amount'))}<br/>"
        f"Discount: {currency} {_fmt_money(invoice.get('discount_amount'))}<br/>"
        f"<strong>Total: {currency} {_fmt_money(invoice.get('total_amount'))}</strong><br/>"
        f"Paid: {currency} {_fmt_money(invoice.get('paid_amount'))}<br/>"
        f"Balance due: {currency} {_fmt_money(invoice.get('balance_due'))}</p>"
    )
    if invoice.get("notes"):
        html += f"<p>Notes: {invoice['notes']}</p>"
    return text, html


async def send_invoice_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    invoice: dict[str, Any],
) -> EmailResult:
    number = invoice.get("invoice_number") or ""
    subject = f"Invoice {number} from {company_name}"
    text, html = render_invoice_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        invoice=invoice,
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=html)


async def send_purchase_order_email(
    *,
    to: str,
    company_name: str,
    supplier_name: str,
    purchase_order: dict[str, Any],
    text_body: str,
) -> EmailResult:
    number = purchase_order.get("po_number") or ""
    subject = f"Purchase Order {number} from {company_name}"
    html = (
        f"<p>Dear {supplier_name},</p>"
        f"<p>Please find purchase order <strong>{number}</strong> from {company_name}.</p>"
        f"<pre>{text_body}</pre>"
        f"<p>Total: {_fmt_money(purchase_order.get('total_amount'))}</p>"
    )
    return await send_email(to=to, subject=subject, text_body=text_body, html_body=html)


async def send_test_email(*, to: str, tenant: Any | None = None) -> EmailResult:
    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="EMAIL_ENABLED is false")
    mode = _delivery_mode(tenant)
    cfg = resolve_smtp_config(tenant)
    if mode == "smtp" and not (cfg["host"] and cfg["from_email"]):
        raise HTTPException(status_code=400, detail="SMTP is not configured")
    return await send_email(
        to=to,
        subject="RIBDIGI ERP test email",
        text_body="This is a test email from RIBDIGI ERP. SMTP delivery is working.",
        html_body="<p>This is a test email from <strong>RIBDIGI ERP</strong>. SMTP delivery is working.</p>",
        tenant=tenant,
    )
