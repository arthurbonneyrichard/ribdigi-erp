"""Tenant SaaS subscription billing.

This charges a company for using Ribdigi ERP. It does not record sales, POS,
or customer payments. A renewal charge runs only when the tenant has recorded
consent and the gateway has returned a reusable authorization reference.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app import notifications as notifications_svc
from app import packages as packages_svc
from app.billing_gateway import CONSENT_VERSION, current_gateway, get_gateway, minor_units
from app.config import settings
from app.honesty import money_json
from app.models import uid

BILLING_STATUSES = {
    "trialing",
    "active",
    "payment_required",
    "past_due",
    "grace_period",
    "canceled",
    "suspended",
}
CARD_RE = re.compile(r"\d{13,19}")
SECRET_RESPONSE_KEYS = {
    "gateway_authorization_ref",
    "paystack_secret_key",
    "card_number",
    "cvv",
    "pan",
    "pin",
    "password",
}

ACCESS_NOTES = {
    "trialing": "Full access until the trial ends. No charge until you authorize renewal.",
    "active": "Full access through the paid-through date.",
    "payment_required": "Read-only until a payment method is authorized. Nothing has been charged.",
    "past_due": "Read-only while a limited retry schedule runs. Company data is kept.",
    "grace_period": "Read-only until the grace period ends. Company data is kept.",
    "canceled": "Access continues through the paid-through date. Further renewals are not charged.",
    "suspended": "Workspace access is suspended. Company data is kept and is not deleted.",
}


def _now() -> datetime:
    return datetime.utcnow()


def money(value) -> Decimal:
    return Decimal(str(value if value is not None else "0")).quantize(Decimal("0.01"))


def billable_price(account, plan) -> tuple[Decimal, str]:
    override = getattr(account, "price_override_amount", None)
    if override is not None:
        currency = (getattr(account, "price_override_currency", None) or plan.currency or "GHS").upper()
        return money(override), currency
    return money(plan.amount), (plan.currency or "GHS").upper()


def _reject_card_text(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if CARD_RE.search(text.replace(" ", "").replace("-", "")):
        raise HTTPException(status_code=422, detail=f"{label} must not contain a card number")
    return text


def reminder_days() -> set[int]:
    raw = (settings.BILLING_REMINDER_DAYS or "7,3,1").split(",")
    out: set[int] = set()
    for part in raw:
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out or {7, 3, 1}


def add_interval(start: datetime, interval: str) -> datetime:
    unit = (interval or "month").strip().lower()
    months = 12 if unit == "year" else 1
    return packages_svc.add_calendar_months(start, months)


def checkout_path() -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/company/billing"


def _mask(value: str | None) -> str | None:
    text = (value or "").strip()
    if len(text) < 4:
        return None
    return f"…{text[-4:]}"


def serialize_plan(plan: m.PlatformBillingPlan) -> dict:
    return {
        "id": plan.id,
        "code": plan.code,
        "package_code": plan.package_code,
        "name": plan.name,
        "interval": plan.interval,
        "amount": money_json(plan.amount),
        "currency": plan.currency,
        "trial_days": int(plan.trial_days or 0),
        "grace_days": int(plan.grace_days or 0),
        "is_active": bool(plan.is_active),
    }


def serialize_invoice(row: m.TenantBillingInvoice) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "plan_id": row.plan_id,
        "idempotency_key": row.idempotency_key,
        "amount": money_json(row.amount),
        "currency": row.currency,
        "status": row.status,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "gateway_reference": row.gateway_reference,
        "created_at": row.created_at,
        "paid_at": row.paid_at,
    }


def serialize_account(account: m.TenantBillingAccount, plan: m.PlatformBillingPlan | None) -> dict:
    status = account.billing_status or "trialing"
    return {
        "tenant_id": account.tenant_id,
        "billing_status": status,
        "access_note": ACCESS_NOTES.get(status, ACCESS_NOTES["trialing"]),
        "auto_renew": bool(account.auto_renew),
        "cancel_at_period_end": bool(account.cancel_at_period_end),
        "canceled_at": account.canceled_at,
        "paid_through": account.paid_through,
        "next_renewal_at": account.next_renewal_at,
        "next_retry_at": account.next_retry_at,
        "grace_ends_at": account.grace_ends_at,
        "consent_version": account.consent_version,
        "consent_at": account.consent_at,
        "consent_user_id": account.consent_user_id,
        "consent_amount": money_json(account.consent_amount) if account.consent_amount is not None else None,
        "consent_currency": account.consent_currency,
        "price_override_amount": money_json(account.price_override_amount)
        if getattr(account, "price_override_amount", None) is not None
        else None,
        "price_override_currency": getattr(account, "price_override_currency", None),
        "consent_interval": account.consent_interval,
        "authorization_present": bool(account.gateway_authorization_ref),
        "authorization_hint": _mask(account.gateway_authorization_ref),
        "customer_hint": _mask(account.gateway_customer_ref),
        "gateway_provider": account.gateway_provider,
        "checkout_path": checkout_path(),
        "plan": serialize_plan(plan) if plan else None,
    }


def provider_status() -> dict:
    gateway = get_gateway()
    return {
        "provider": gateway.provider,
        "configured": gateway.configured(),
        "live_charges": gateway.provider == "paystack" and gateway.configured(),
        "consent_version": CONSENT_VERSION,
        "checkout_path": checkout_path(),
    }


async def ensure_default_plans(db: AsyncSession) -> None:
    existing = (await db.execute(select(m.PlatformBillingPlan.id).limit(1))).first()
    if existing:
        return
    catalog = (
        ("starter-month", "starter", "Starter monthly", "month", "199.00"),
        ("professional-month", "professional", "Professional monthly", "month", "499.00"),
        ("enterprise-month", "enterprise", "Enterprise monthly", "month", "999.00"),
        ("starter-year", "starter", "Starter yearly", "year", "1990.00"),
        ("professional-year", "professional", "Professional yearly", "year", "4990.00"),
        ("enterprise-year", "enterprise", "Enterprise yearly", "year", "9990.00"),
    )
    for code, package_code, name, interval, amount in catalog:
        db.add(
            m.PlatformBillingPlan(
                id=uid(),
                code=code,
                package_code=package_code,
                name=name,
                interval=interval,
                amount=money(amount),
                currency="GHS",
                trial_days=int(settings.TRIAL_DAYS or 14),
                grace_days=int(settings.BILLING_GRACE_DAYS or 7),
                is_active=True,
            )
        )
    await db.flush()


async def _plan_by_code(db: AsyncSession, code: str) -> m.PlatformBillingPlan:
    await ensure_default_plans(db)
    plan = (
        await db.execute(
            select(m.PlatformBillingPlan).where(m.PlatformBillingPlan.code == code.strip().lower())
        )
    ).scalar_one_or_none()
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    return plan


async def get_account(db: AsyncSession, tenant_id: str) -> m.TenantBillingAccount | None:
    return (
        await db.execute(
            select(m.TenantBillingAccount).where(m.TenantBillingAccount.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


async def get_or_create_account(db: AsyncSession, tenant: m.Tenant) -> m.TenantBillingAccount:
    row = await get_account(db, tenant.id)
    if row:
        return row
    row = m.TenantBillingAccount(
        id=uid(),
        tenant_id=tenant.id,
        billing_status="trialing" if tenant.status == "trial" else "payment_required",
        auto_renew=False,
        gateway_provider=(settings.BILLING_PROVIDER or "mock").strip().lower(),
    )
    db.add(row)
    await db.flush()
    return row


async def _load_plan(db: AsyncSession, plan_id: str | None) -> m.PlatformBillingPlan | None:
    if not plan_id:
        return None
    return await db.get(m.PlatformBillingPlan, plan_id)


def _validate_plan_fields(payload) -> None:
    interval = (payload.interval or "").strip().lower()
    if interval not in {"month", "year"}:
        raise HTTPException(status_code=422, detail="interval must be month or year")
    package = (payload.package_code or "").strip().lower()
    if package not in packages_svc.VALID_PACKAGE_CODES or package == "trial":
        raise HTTPException(status_code=422, detail="package_code must be a paid package")
    amount = money(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be greater than zero")
    currency = (payload.currency or "").strip().upper()
    if currency not in {"GHS", "USD"}:
        raise HTTPException(status_code=422, detail="currency must be GHS or USD")
    if int(payload.trial_days) < 0 or int(payload.trial_days) > 365:
        raise HTTPException(status_code=422, detail="trial_days must be between 0 and 365")
    if int(payload.grace_days) < 1 or int(payload.grace_days) > 90:
        raise HTTPException(status_code=422, detail="grace_days must be between 1 and 90")


async def create_plan(db: AsyncSession, payload, *, actor) -> m.PlatformBillingPlan:
    _validate_plan_fields(payload)
    plan = m.PlatformBillingPlan(
        id=uid(),
        code=payload.code.strip().lower(),
        package_code=payload.package_code.strip().lower(),
        name=payload.name.strip(),
        interval=payload.interval.strip().lower(),
        amount=money(payload.amount),
        currency=payload.currency.strip().upper(),
        trial_days=int(payload.trial_days),
        grace_days=int(payload.grace_days),
        is_active=bool(payload.is_active),
    )
    db.add(plan)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Billing plan code already exists") from exc
    await _audit(
        db,
        tenant_id=actor["tenant_id"],
        user_id=actor["sub"],
        action="billing_plan_created",
        entity_id=plan.id,
        details={"code": plan.code, "amount": str(money(plan.amount)), "currency": plan.currency},
    )
    return plan


async def update_plan(db: AsyncSession, plan_id: str, payload, *, actor) -> m.PlatformBillingPlan:
    plan = await db.get(m.PlatformBillingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    data = payload.model_dump(exclude_unset=True)
    if "interval" in data and data["interval"] is not None:
        if data["interval"].strip().lower() not in {"month", "year"}:
            raise HTTPException(status_code=422, detail="interval must be month or year")
        plan.interval = data["interval"].strip().lower()
    if "amount" in data and data["amount"] is not None:
        amount = money(data["amount"])
        if amount <= 0:
            raise HTTPException(status_code=422, detail="amount must be greater than zero")
        plan.amount = amount
    if "currency" in data and data["currency"] is not None:
        currency = data["currency"].strip().upper()
        if currency not in {"GHS", "USD"}:
            raise HTTPException(status_code=422, detail="currency must be GHS or USD")
        plan.currency = currency
    if "name" in data and data["name"] is not None:
        plan.name = data["name"].strip()
    if "trial_days" in data and data["trial_days"] is not None:
        plan.trial_days = int(data["trial_days"])
    if "grace_days" in data and data["grace_days"] is not None:
        plan.grace_days = int(data["grace_days"])
    if "is_active" in data and data["is_active"] is not None:
        plan.is_active = bool(data["is_active"])
    plan.updated_at = _now()
    await db.flush()
    await _audit(
        db,
        tenant_id=actor["tenant_id"],
        user_id=actor["sub"],
        action="billing_plan_updated",
        entity_id=plan.id,
        details={"code": plan.code},
    )
    return plan


def _parse_iso(value: str | None) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().replace("Z", "")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Date must be ISO 8601") from exc


async def assign_plan(db: AsyncSession, tenant: m.Tenant, payload, *, actor) -> m.TenantBillingAccount:
    plan = await _plan_by_code(db, payload.plan_code)
    account = await get_or_create_account(db, tenant)
    account.plan_id = plan.id
    account.gateway_provider = (await current_gateway(db)).provider
    trial_ends = _parse_iso(payload.trial_ends_at)
    renewal = _parse_iso(payload.next_renewal_at)
    if trial_ends:
        tenant.trial_ends_at = trial_ends
        if not account.paid_through and tenant.status in {"trial", "active", "grace"}:
            tenant.status = "trial"
            account.billing_status = "trialing"
    if renewal:
        account.next_renewal_at = renewal
    elif trial_ends:
        account.next_renewal_at = trial_ends
    custom = getattr(payload, "custom_amount", None)
    if custom is not None:
        custom_currency = (getattr(payload, "custom_currency", None) or plan.currency or "GHS").strip().upper()
        if custom_currency not in {"GHS", "USD"}:
            raise HTTPException(status_code=422, detail="currency must be GHS or USD")
        amount = money(custom)
        if amount <= 0:
            raise HTTPException(status_code=422, detail="amount must be greater than zero")
        account.price_override_amount = amount
        account.price_override_currency = custom_currency
    tenant.package_code = plan.package_code
    tenant.enabled_modules = None
    account.updated_at = _now()
    await db.flush()
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=actor["sub"],
        action="billing_plan_assigned",
        entity_id=account.id,
        details={"plan_code": plan.code, "tenant_id": tenant.id},
    )
    return account


async def record_consent(
    db: AsyncSession, tenant: m.Tenant, *, plan_code: str, accept: bool, user_id: str
) -> m.TenantBillingAccount:
    if not accept:
        raise HTTPException(status_code=422, detail="Automatic renewal consent is required")
    plan = await _plan_by_code(db, plan_code)
    account = await get_or_create_account(db, tenant)
    now = _now()
    account.plan_id = plan.id
    account.consent_version = CONSENT_VERSION
    account.consent_at = now
    account.consent_user_id = user_id
    account.consent_plan_id = plan.id
    price, price_currency = billable_price(account, plan)
    account.consent_amount = price
    account.consent_currency = price_currency
    account.consent_interval = plan.interval
    account.auto_renew = bool(account.gateway_authorization_ref)
    account.updated_at = now
    if not account.next_renewal_at:
        account.next_renewal_at = tenant.trial_ends_at or (now + timedelta(days=int(plan.trial_days or 0)))
    await db.flush()
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=user_id,
        action="billing_consent_recorded",
        entity_id=account.id,
        details={
            "version": CONSENT_VERSION,
            "plan_id": plan.id,
            "amount": str(price),
            "currency": price_currency,
            "interval": plan.interval,
        },
    )
    return account


def _authorized(account: m.TenantBillingAccount) -> bool:
    return bool(
        account.auto_renew
        and account.consent_version
        and account.consent_at
        and account.gateway_authorization_ref
        and account.plan_id
    )


async def start_checkout(db: AsyncSession, tenant: m.Tenant, *, plan_code: str, email: str) -> dict:
    plan = await _plan_by_code(db, plan_code)
    account = await get_account(db, tenant.id)
    if not account or account.consent_plan_id != plan.id or not account.consent_at:
        raise HTTPException(status_code=422, detail="Record renewal consent before checkout")
    gateway = await current_gateway(db)
    reference = f"checkout:{account.id}:{plan.id}"
    result = gateway.checkout(
        email=email,
        amount_minor=minor_units(billable_price(account, plan)[0]),
        currency=billable_price(account, plan)[1],
        reference=reference,
        callback_url=checkout_path(),
    )
    if not result.ok:
        raise HTTPException(
            status_code=503,
            detail="The billing gateway is not configured for hosted checkout",
        )
    account.gateway_provider = gateway.provider
    account.updated_at = _now()
    await db.flush()
    return {
        "checkout_url": result.checkout_url,
        "reference": result.reference,
        "provider": gateway.provider,
        "paid": False,
    }


async def attach_sandbox_authorization(
    db: AsyncSession, tenant: m.Tenant, *, authorization_code: str, user_id: str
) -> m.TenantBillingAccount:
    gateway = await current_gateway(db)
    if gateway.provider != "mock" or not gateway.configured():
        raise HTTPException(status_code=404, detail="Sandbox authorization is not available")
    token = _reject_card_text(authorization_code, "authorization_code")
    if not token.startswith("mock_auth_"):
        raise HTTPException(status_code=422, detail="Sandbox authorization code is invalid")
    account = await get_account(db, tenant.id)
    if not account or not account.consent_at:
        raise HTTPException(status_code=422, detail="Record renewal consent before adding a payment method")
    account.gateway_provider = "mock"
    account.gateway_customer_ref = f"mock_cus_{tenant.id[:8]}"
    account.gateway_authorization_ref = token
    account.auto_renew = True
    account.cancel_at_period_end = False
    account.updated_at = _now()
    await db.flush()
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=user_id,
        action="billing_authorization_saved",
        entity_id=account.id,
        details={"provider": "mock", "hint": _mask(token)},
    )
    return account


async def cancel_auto_renew(db: AsyncSession, tenant: m.Tenant, *, confirm: bool, user_id: str):
    if not confirm:
        raise HTTPException(status_code=422, detail="Confirm cancellation of future renewals")
    account = await get_account(db, tenant.id)
    if not account:
        raise HTTPException(status_code=404, detail="Billing profile not found")
    now = _now()
    account.auto_renew = False
    account.cancel_at_period_end = True
    account.canceled_at = now
    account.billing_status = "canceled"
    account.updated_at = now
    await db.flush()
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=user_id,
        action="billing_auto_renew_canceled",
        entity_id=account.id,
        details={"paid_through": account.paid_through.isoformat() if account.paid_through else None},
    )
    await _notify(
        db,
        tenant,
        title="Automatic renewal turned off",
        message=(
            "Future subscription charges are stopped. Access continues through "
            f"{account.paid_through.isoformat() if account.paid_through else 'the paid-through date'}."
        ),
    )
    return account


async def list_invoices(db: AsyncSession, tenant_id: str) -> list[m.TenantBillingInvoice]:
    return list(
        (
            await db.execute(
                select(m.TenantBillingInvoice)
                .where(m.TenantBillingInvoice.tenant_id == tenant_id)
                .order_by(m.TenantBillingInvoice.created_at.desc())
            )
        ).scalars().all()
    )


async def _audit(db, *, tenant_id: str, user_id: str | None, action: str, entity_id: str, details: dict):
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="billing",
        action=action,
        entity="saas_billing",
        entity_id=entity_id,
        details=details,
    )


async def _notify(db, tenant: m.Tenant, *, title: str, message: str) -> None:
    await notifications_svc.create_notification(
        db,
        tenant_id=tenant.id,
        category="billing",
        title=title,
        message=message,
        entity_type="saas_billing",
        entity_id=tenant.id,
    )


async def _notify_owners(db, tenant: m.Tenant, *, title: str, message: str) -> None:
    """Tell platform owners on their own workspace. No card or token data."""
    from app.rbac import PLATFORM_OWNER_ROLES

    owners = (
        await db.execute(
            select(m.User).where(
                m.User.role.in_(tuple(PLATFORM_OWNER_ROLES)),
                m.User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    company = tenant.company_name or tenant.slug
    for owner in owners:
        await notifications_svc.create_notification(
            db,
            tenant_id=owner.tenant_id,
            user_id=owner.id,
            category="billing",
            title=title,
            message=f"{company}: {message}",
            entity_type="saas_billing",
            entity_id=tenant.id,
        )


async def _invoice_by_key(db: AsyncSession, key: str) -> m.TenantBillingInvoice | None:
    return (
        await db.execute(
            select(m.TenantBillingInvoice).where(m.TenantBillingInvoice.idempotency_key == key)
        )
    ).scalar_one_or_none()


async def _open_invoice(
    db: AsyncSession,
    *,
    account: m.TenantBillingAccount,
    plan: m.PlatformBillingPlan,
    key: str,
    period_start: datetime,
    period_end: datetime,
) -> m.TenantBillingInvoice:
    existing = await _invoice_by_key(db, key)
    if existing:
        return existing
    row = m.TenantBillingInvoice(
        id=uid(),
        tenant_id=account.tenant_id,
        account_id=account.id,
        plan_id=plan.id,
        idempotency_key=key,
        amount=billable_price(account, plan)[0],
        currency=billable_price(account, plan)[1],
        status="open",
        period_start=period_start,
        period_end=period_end,
    )
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        found = await _invoice_by_key(db, key)
        if not found:
            raise
        return found
    return row


async def _attempts(db: AsyncSession, invoice_id: str) -> list[m.TenantBillingAttempt]:
    return list(
        (
            await db.execute(
                select(m.TenantBillingAttempt)
                .where(m.TenantBillingAttempt.invoice_id == invoice_id)
                .order_by(m.TenantBillingAttempt.attempt_number.asc())
            )
        ).scalars().all()
    )


def _retry_delay(attempt_number: int) -> timedelta:
    if attempt_number <= 1:
        return timedelta(days=1)
    return timedelta(days=3)


async def _mark_paid(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    account: m.TenantBillingAccount,
    plan: m.PlatformBillingPlan,
    invoice: m.TenantBillingInvoice,
    gateway_reference: str | None,
) -> None:
    now = _now()
    if invoice.status != "paid":
        invoice.status = "paid"
        invoice.paid_at = now
        invoice.gateway_reference = gateway_reference
    account.billing_status = "active"
    account.paid_through = invoice.period_end
    account.next_renewal_at = invoice.period_end
    account.next_retry_at = None
    account.grace_ends_at = None
    account.updated_at = now
    tenant.status = "active"
    tenant.suspended_at = None
    tenant.suspended_reason = None
    tenant.grace_ends_at = None
    tenant.package_code = plan.package_code
    tenant.enabled_modules = None
    tenant.subscription_starts_at = invoice.period_start
    tenant.subscription_ends_at = invoice.period_end
    tenant.subscription_term_unit = "years" if plan.interval == "year" else "months"
    tenant.subscription_term_value = 1
    tenant.package_assigned_at = now
    tenant.trial_ends_at = invoice.period_end
    await db.flush()


async def _fail_attempt(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    account: m.TenantBillingAccount,
    plan: m.PlatformBillingPlan,
    invoice: m.TenantBillingInvoice,
    attempt: m.TenantBillingAttempt,
    reason: str,
    when: datetime | None = None,
) -> None:
    now = when or _now()
    attempt.status = "failed"
    attempt.failure_reason = (reason or "declined")[:200]
    invoice.status = "failed"
    max_attempts = max(1, int(settings.BILLING_MAX_ATTEMPTS or 3))
    prior = await _attempts(db, invoice.id)
    failed_count = len([row for row in prior if row.status == "failed"])
    grace_days = int(plan.grace_days or settings.BILLING_GRACE_DAYS or 7)
    if failed_count >= max_attempts:
        account.billing_status = "grace_period"
        account.grace_ends_at = now + timedelta(days=grace_days)
        account.next_retry_at = None
        tenant.status = "grace"
        tenant.grace_ends_at = account.grace_ends_at
    else:
        account.billing_status = "past_due"
        account.next_retry_at = now + _retry_delay(failed_count)
        tenant.status = "grace"
        tenant.grace_ends_at = now + timedelta(days=grace_days)
    account.updated_at = now
    await db.flush()
    await _notify(
        db,
        tenant,
        title="Subscription payment failed",
        message=(
            f"The renewal for {plan.name} was not collected ({attempt.failure_reason}). "
            f"Update the payment method at {checkout_path()}. Company data is kept."
        ),
    )
    await _notify_owners(
        db,
        tenant,
        title="Subscription payment failed",
        message=(
            f"The renewal for {plan.name} was not collected. "
            "Company data is kept. No card number is stored."
        ),
    )


async def charge_invoice(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    account: m.TenantBillingAccount,
    plan: m.PlatformBillingPlan,
    invoice: m.TenantBillingInvoice,
    email: str,
    when: datetime | None = None,
) -> str:
    """Charge one open invoice at most once per attempt number. Returns paid|skipped|failed."""
    when = when or _now()
    if invoice.status == "paid":
        return "skipped"
    expected_currency = (account.consent_currency or plan.currency or "").upper()
    expected_amount = money(account.consent_amount if account.consent_amount is not None else plan.amount)
    if invoice.currency.upper() != expected_currency or money(invoice.amount) != expected_amount:
        return "skipped"
    if not _authorized(account):
        return "skipped"
    existing = await _attempts(db, invoice.id)
    if any(row.status == "succeeded" for row in existing):
        await _mark_paid(
            db,
            tenant=tenant,
            account=account,
            plan=plan,
            invoice=invoice,
            gateway_reference=invoice.gateway_reference,
        )
        return "skipped"
    if any(row.status == "pending" for row in existing):
        return "skipped"
    max_attempts = max(1, int(settings.BILLING_MAX_ATTEMPTS or 3))
    if len(existing) >= max_attempts:
        return "skipped"
    if account.next_retry_at and account.next_retry_at > when and existing:
        return "skipped"
    number = len(existing) + 1
    attempt = m.TenantBillingAttempt(
        id=uid(),
        tenant_id=tenant.id,
        invoice_id=invoice.id,
        attempt_number=number,
        status="pending",
    )
    try:
        async with db.begin_nested():
            db.add(attempt)
            await db.flush()
    except IntegrityError:
        return "skipped"
    gateway = await current_gateway(db)
    result = gateway.charge(
        authorization_ref=account.gateway_authorization_ref or "",
        amount_minor=minor_units(money(invoice.amount)),
        currency=invoice.currency,
        reference=invoice.idempotency_key,
        email=email,
    )
    if result.ok:
        attempt.status = "succeeded"
        attempt.gateway_reference = result.gateway_reference
        if result.authorization_ref and result.authorization_ref.startswith(("AUTH_", "mock_auth_")):
            account.gateway_authorization_ref = result.authorization_ref
        if result.customer_ref:
            account.gateway_customer_ref = result.customer_ref
        await _mark_paid(
            db,
            tenant=tenant,
            account=account,
            plan=plan,
            invoice=invoice,
            gateway_reference=result.gateway_reference,
        )
        await _audit(
            db,
            tenant_id=tenant.id,
            user_id=None,
            action="billing_payment_succeeded",
            entity_id=invoice.id,
            details={
                "gateway_reference": result.gateway_reference,
                "amount": str(money(invoice.amount)),
                "currency": invoice.currency,
            },
        )
        await _notify(
            db,
            tenant,
            title="Subscription payment received",
            message=f"{plan.name} is paid through {invoice.period_end.isoformat()}.",
        )
        return "paid"
    if result.pending:
        attempt.gateway_reference = result.gateway_reference
        await db.flush()
        await _notify(
            db,
            tenant,
            title="Subscription payment pending",
            message=(
                f"The renewal for {plan.name} is waiting for the payment provider. "
                "The invoice stays unpaid until the provider confirms it."
            ),
        )
        return "pending"
    await _fail_attempt(
        db,
        tenant=tenant,
        account=account,
        plan=plan,
        invoice=invoice,
        attempt=attempt,
        reason=result.message,
        when=when,
    )
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=None,
        action="billing_payment_failed",
        entity_id=invoice.id,
        details={"reason": result.message, "attempt": number},
    )
    return "failed"


async def _tenant_email(db: AsyncSession, tenant: m.Tenant) -> str:
    admin = (
        await db.execute(
            select(m.User)
            .where(
                m.User.tenant_id == tenant.id,
                m.User.role == "company_admin",
                m.User.is_active == True,  # noqa: E712
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return (admin.email if admin else None) or tenant.email or "billing@localhost"


async def collect_due(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    account: m.TenantBillingAccount,
    when: datetime,
    reason: str,
) -> str:
    if not _authorized(account):
        account.billing_status = "payment_required"
        account.updated_at = when
        await db.flush()
        await _notify(
            db,
            tenant,
            title="Subscription payment required",
            message=(
                "No authorized payment method is on file, so nothing was charged. "
                f"Open {checkout_path()} to add one."
            ),
        )
        return "payment_required"
    plan = await _load_plan(db, account.plan_id)
    if not plan:
        return "skipped"
    period_start = account.next_renewal_at or when
    interval = account.consent_interval or plan.interval
    period_end = add_interval(period_start, interval)
    key = f"renew:{account.id}:{period_start.date().isoformat()}"
    invoice = await _open_invoice(
        db,
        account=account,
        plan=plan,
        key=key,
        period_start=period_start,
        period_end=period_end,
    )
    if invoice.status == "open":
        invoice.amount = money(
            account.consent_amount if account.consent_amount is not None else plan.amount
        )
        invoice.currency = (account.consent_currency or plan.currency).upper()
    if invoice.status == "paid":
        return "skipped"
    return await charge_invoice(
        db,
        tenant=tenant,
        account=account,
        plan=plan,
        invoice=invoice,
        email=await _tenant_email(db, tenant),
        when=when,
    )


async def note_trial_ended(db: AsyncSession, tenant: m.Tenant) -> str:
    """Return `paid` when a consented trial converted. Otherwise do not charge."""
    account = await get_account(db, tenant.id)
    if not account:
        return "skip"
    now = _now()
    if _authorized(account):
        account.next_renewal_at = account.next_renewal_at or tenant.trial_ends_at or now
        outcome = await collect_due(db, tenant=tenant, account=account, when=now, reason="trial_end")
        if outcome == "paid":
            return "paid"
        return "unpaid"
    account.billing_status = "payment_required"
    account.updated_at = now
    await db.flush()
    await _notify(
        db,
        tenant,
        title="Trial ended — payment required",
        message=(
            "The trial ended and no charge was made. "
            f"Choose a plan at {checkout_path()}."
        ),
    )
    await _notify_owners(
        db,
        tenant,
        title="Trial ended — payment required",
        message=(
            "The trial ended and no charge was made. "
            f"The company can subscribe at {checkout_path()}."
        ),
    )
    return "unpaid"


async def process_due_renewals(db: AsyncSession, *, now: datetime | None = None) -> dict:
    now = now or _now()
    await ensure_default_plans(db)
    reminded = 0
    charged = 0
    failed = 0
    suspended = 0
    accounts = (await db.execute(select(m.TenantBillingAccount))).scalars().all()
    for account in accounts:
        tenant = await db.get(m.Tenant, account.tenant_id)
        if not tenant:
            continue
        if account.billing_status == "grace_period" and account.grace_ends_at and account.grace_ends_at <= now:
            if tenant.status != "suspended":
                from app.tenants import suspend_tenant

                await suspend_tenant(db, tenant, reason="Subscription payment failed after grace")
            account.billing_status = "suspended"
            account.updated_at = now
            suspended += 1
            await _notify(
                db,
                tenant,
                title="Subscription suspended",
                message="The grace period ended without payment. Company data is still stored.",
            )
            await _notify_owners(
                db,
                tenant,
                title="Subscription suspended",
                message="The grace period ended without payment. Company data is still stored.",
            )
            continue
        if (
            account.billing_status == "trialing"
            and tenant.trial_ends_at
            and tenant.trial_ends_at > now
        ):
            days = (tenant.trial_ends_at.date() - now.date()).days
            if days in reminder_days():
                key = f"trial-reminder:{days}:{tenant.trial_ends_at.date().isoformat()}"
                if account.last_notice_key != key:
                    account.last_notice_key = key
                    reminded += 1
                    await _notify(
                        db,
                        tenant,
                        title=f"Trial ends in {days} day{'s' if days != 1 else ''}",
                        message=(
                            f"The trial ends on {tenant.trial_ends_at.date().isoformat()}. "
                            "Nothing is charged unless renewal was authorized."
                        ),
                    )
        if account.billing_status == "canceled" or not account.auto_renew:
            if account.paid_through and account.paid_through <= now and tenant.status == "active":
                tenant.status = "grace"
                grace_end = now + timedelta(days=int(settings.BILLING_GRACE_DAYS or 7))
                tenant.grace_ends_at = grace_end
                account.grace_ends_at = grace_end
                account.billing_status = "grace_period"
            continue
        due = account.next_renewal_at and account.next_renewal_at <= now
        retry_due = account.next_retry_at and account.next_retry_at <= now
        if account.billing_status != "trialing" and account.next_renewal_at and not due:
            days = (account.next_renewal_at.date() - now.date()).days
            if days in reminder_days():
                key = f"renew-reminder:{days}:{account.next_renewal_at.date().isoformat()}"
                if account.last_notice_key != key:
                    account.last_notice_key = key
                    reminded += 1
                    await _notify(
                        db,
                        tenant,
                        title=f"Subscription renews in {days} day{'s' if days != 1 else ''}",
                        message=f"The next renewal is {account.next_renewal_at.date().isoformat()}.",
                    )
        if not due and not retry_due:
            continue
        outcome = await collect_due(db, tenant=tenant, account=account, when=now, reason="renewal")
        if outcome == "paid":
            charged += 1
        elif outcome == "failed":
            failed += 1
    await db.flush()
    return {"reminded": reminded, "charged": charged, "failed": failed, "suspended": suspended}


async def apply_webhook(db: AsyncSession, *, provider: str, event: dict) -> dict:
    event_id = str(event.get("id") or "").strip()
    event_type = str(event.get("event") or "").strip().lower()
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if not event_id or not event_type:
        raise HTTPException(status_code=422, detail="Webhook event id and type are required")
    existing = (
        await db.execute(
            select(m.TenantBillingEvent).where(m.TenantBillingEvent.gateway_event_id == event_id)
        )
    ).scalar_one_or_none()
    if existing:
        return {"duplicate": True, "outcome": existing.outcome}
    reference = str(data.get("reference") or "").strip()
    invoice = await _invoice_by_key(db, reference) if reference else None
    outcome = "ignored"
    if invoice and event_type in {"charge.success", "charge.failed"}:
        expected_minor = minor_units(money(invoice.amount))
        supplied_minor = data.get("amount")
        currency = str(data.get("currency") or "").upper()
        tenant_ok = not data.get("tenant_id") or str(data.get("tenant_id")) == invoice.tenant_id
        amount_ok = supplied_minor is None or int(supplied_minor) == expected_minor
        currency_ok = not currency or currency == invoice.currency.upper()
        if not (tenant_ok and amount_ok and currency_ok):
            outcome = "mismatch"
        elif event_type == "charge.success":
            if invoice.status != "paid":
                tenant = await db.get(m.Tenant, invoice.tenant_id)
                account = await get_account(db, invoice.tenant_id)
                plan = await _load_plan(db, invoice.plan_id)
                if tenant and account and plan:
                    for row in await _attempts(db, invoice.id):
                        if row.status == "pending":
                            row.status = "succeeded"
                            row.gateway_reference = str(data.get("gateway_reference") or reference)
                    await _mark_paid(
                        db,
                        tenant=tenant,
                        account=account,
                        plan=plan,
                        invoice=invoice,
                        gateway_reference=str(data.get("gateway_reference") or reference),
                    )
                    auth = str(data.get("authorization_code") or "").strip()
                    if auth and not CARD_RE.search(auth):
                        account.gateway_authorization_ref = auth
                        account.auto_renew = bool(account.consent_at)
                    customer = str(data.get("customer_code") or "").strip()
                    if customer:
                        account.gateway_customer_ref = customer
            outcome = "paid"
        else:
            tenant = await db.get(m.Tenant, invoice.tenant_id)
            account = await get_account(db, invoice.tenant_id)
            plan = await _load_plan(db, invoice.plan_id)
            pending = next(
                (row for row in await _attempts(db, invoice.id) if row.status == "pending"),
                None,
            )
            if tenant and account and plan and pending and invoice.status != "paid":
                await _fail_attempt(
                    db,
                    tenant=tenant,
                    account=account,
                    plan=plan,
                    invoice=invoice,
                    attempt=pending,
                    reason="gateway_declined",
                )
            outcome = "failed"
    row = m.TenantBillingEvent(
        id=uid(),
        provider=provider,
        gateway_event_id=event_id,
        tenant_id=invoice.tenant_id if invoice else None,
        invoice_id=invoice.id if invoice else None,
        event_type=event_type[:80],
        outcome=outcome,
    )
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        return {"duplicate": True, "outcome": "duplicate"}
    return {"duplicate": False, "outcome": outcome}


async def manual_payment(db: AsyncSession, tenant: m.Tenant, payload, *, actor) -> m.TenantBillingInvoice:
    reference = _reject_card_text(payload.reference, "reference")
    note = _reject_card_text(payload.note, "note") if payload.note else None
    currency = payload.currency.strip().upper()
    if currency not in {"GHS", "USD"}:
        raise HTTPException(status_code=422, detail="currency must be GHS or USD")
    amount = money(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be greater than zero")
    account = await get_or_create_account(db, tenant)
    plan = await _load_plan(db, account.plan_id)
    if not plan:
        raise HTTPException(status_code=422, detail="Assign a billing plan before recording a payment")
    if currency != plan.currency or amount != money(plan.amount):
        raise HTTPException(status_code=422, detail="Amount and currency must match the assigned plan")
    now = _now()
    period_start = now
    period_end = add_interval(now, plan.interval)
    key = f"manual:{reference}"
    invoice = await _open_invoice(
        db,
        account=account,
        plan=plan,
        key=key,
        period_start=period_start,
        period_end=period_end,
    )
    if invoice.status != "paid":
        await _mark_paid(
            db,
            tenant=tenant,
            account=account,
            plan=plan,
            invoice=invoice,
            gateway_reference=reference,
        )
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=actor["sub"],
        action="billing_manual_payment",
        entity_id=invoice.id,
        details={"reference": reference, "note": note, "amount": str(amount), "currency": currency},
    )
    return invoice


async def retry_payment(db: AsyncSession, tenant: m.Tenant, *, actor) -> dict:
    account = await get_account(db, tenant.id)
    if not account:
        raise HTTPException(status_code=404, detail="Billing profile not found")
    if not _authorized(account):
        raise HTTPException(status_code=422, detail="A consented authorization is required before retry")
    account.next_retry_at = _now()
    await db.flush()
    outcome = await collect_due(db, tenant=tenant, account=account, when=_now(), reason="manual_retry")
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=actor["sub"],
        action="billing_retry_requested",
        entity_id=account.id,
        details={"outcome": outcome},
    )
    return {"outcome": outcome}


async def reactivate_access(db: AsyncSession, tenant: m.Tenant, *, actor) -> dict:
    """Owner override. Restores workspace access and does not create a charge."""
    from app.tenants import activate_tenant

    if tenant.status != "active":
        await activate_tenant(db, tenant)
    account = await get_account(db, tenant.id)
    now = _now()
    if account and account.billing_status == "suspended":
        paid_open = account.paid_through and account.paid_through > now
        account.billing_status = "active" if paid_open else "payment_required"
        account.grace_ends_at = None
        account.updated_at = now
        await db.flush()
    await _audit(
        db,
        tenant_id=tenant.id,
        user_id=actor["sub"],
        action="billing_access_reactivated",
        entity_id=account.id if account else tenant.id,
        details={"tenant_status": tenant.status, "billing_status": account.billing_status if account else None},
    )
    return {
        "tenant_status": tenant.status,
        "billing_status": account.billing_status if account else None,
        "charged": False,
    }


async def attention_list(db: AsyncSession) -> list[dict]:
    await ensure_default_plans(db)
    rows = (
        await db.execute(
            select(m.TenantBillingAccount).where(
                m.TenantBillingAccount.billing_status.in_(
                    ["payment_required", "past_due", "grace_period", "suspended"]
                )
            )
        )
    ).scalars().all()
    out = []
    for account in rows:
        tenant = await db.get(m.Tenant, account.tenant_id)
        plan = await _load_plan(db, account.plan_id)
        item = serialize_account(account, plan)
        item["company_name"] = tenant.company_name if tenant else None
        item["slug"] = tenant.slug if tenant else None
        item["tenant_status"] = tenant.status if tenant else None
        out.append(item)
    return out
