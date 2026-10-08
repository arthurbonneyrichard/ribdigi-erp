"""SaaS billing HTTP routes. Platform-owner plans and tenant consent stay separate from POS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import saas_billing as billing_svc
from app import tenants as tenants_svc
from app.billing_gateway import get_gateway, verify_webhook_signature, webhook_json
from app.billing_schemas import (
    BillingAssignBody,
    BillingCancelBody,
    BillingCheckoutBody,
    BillingConsentBody,
    BillingManualPaymentBody,
    BillingPlanPatch,
    BillingPlanWrite,
    BillingSandboxAuthorizeBody,
)
from app.config import settings
from app.db import get_db
from app.rbac import is_platform_owner_role
from app.security import require_platform_permission, require_roles

router = APIRouter(tags=["saas-billing"])


def _owner(claims: dict) -> dict:
    if not is_platform_owner_role(claims.get("role")):
        raise HTTPException(status_code=403, detail="Only the platform owner can manage billing plans")
    return claims


@router.get("/platform/billing/status")
async def billing_provider_status(claims=Depends(require_platform_permission("platform", "read"))):
    _owner(claims)
    from app.api import env

    return env(billing_svc.provider_status())


@router.get("/platform/billing/plans")
async def list_billing_plans(
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from sqlalchemy import select

    from app import models as m
    from app.api import env

    await billing_svc.ensure_default_plans(db)
    rows = (await db.execute(select(m.PlatformBillingPlan).order_by(m.PlatformBillingPlan.code))).scalars().all()
    await db.commit()
    return env([billing_svc.serialize_plan(row) for row in rows])


@router.post("/platform/billing/plans")
async def create_billing_plan(
    payload: BillingPlanWrite,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    plan = await billing_svc.create_plan(db, payload, actor=claims)
    await db.commit()
    return env(billing_svc.serialize_plan(plan), "Billing plan created")


@router.patch("/platform/billing/plans/{plan_id}")
async def patch_billing_plan(
    plan_id: str,
    payload: BillingPlanPatch,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    plan = await billing_svc.update_plan(db, plan_id, payload, actor=claims)
    await db.commit()
    return env(billing_svc.serialize_plan(plan), "Billing plan updated")


@router.get("/platform/billing/attention")
async def billing_attention(
    claims=Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    rows = await billing_svc.attention_list(db)
    return env(rows)


@router.get("/platform/billing/tenants/{tenant_ref}")
async def tenant_billing_for_owner(
    tenant_ref: str,
    claims=Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    await billing_svc.ensure_default_plans(db)
    account = await billing_svc.get_account(db, tenant.id)
    plan = await billing_svc._load_plan(db, account.plan_id) if account else None
    invoices = await billing_svc.list_invoices(db, tenant.id)
    return env(
        {
            "tenant_id": tenant.id,
            "slug": tenant.slug,
            "company_name": tenant.company_name,
            "tenant_status": tenant.status,
            "trial_ends_at": tenant.trial_ends_at,
            "account": billing_svc.serialize_account(account, plan) if account else None,
            "invoices": [billing_svc.serialize_invoice(row) for row in invoices],
        }
    )


@router.post("/platform/billing/tenants/{tenant_ref}/assign")
async def assign_tenant_billing_plan(
    tenant_ref: str,
    payload: BillingAssignBody,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    account = await billing_svc.assign_plan(db, tenant, payload, actor=claims)
    plan = await billing_svc._load_plan(db, account.plan_id)
    await db.commit()
    return env(billing_svc.serialize_account(account, plan), "Billing plan assigned")


@router.post("/platform/billing/tenants/{tenant_ref}/payments")
async def record_manual_billing_payment(
    tenant_ref: str,
    payload: BillingManualPaymentBody,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    invoice = await billing_svc.manual_payment(db, tenant, payload, actor=claims)
    await db.commit()
    return env(billing_svc.serialize_invoice(invoice), "Payment recorded")


@router.post("/platform/billing/tenants/{tenant_ref}/retry")
async def retry_tenant_billing(
    tenant_ref: str,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    result = await billing_svc.retry_payment(db, tenant, actor=claims)
    await db.commit()
    return env(result, "Retry processed")


@router.post("/platform/billing/tenants/{tenant_ref}/reactivate")
async def reactivate_tenant_billing(
    tenant_ref: str,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    result = await billing_svc.reactivate_access(db, tenant, actor=claims)
    await db.commit()
    return env(result, "Tenant access restored")


async def _tenant_admin(claims: dict, db: AsyncSession):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return tenant


@router.get("/billing/account")
async def my_billing_account(
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    await billing_svc.ensure_default_plans(db)
    account = await billing_svc.get_account(db, tenant.id)
    plan = await billing_svc._load_plan(db, account.plan_id) if account else None
    await db.commit()
    body = billing_svc.serialize_account(account, plan) if account else {
        "tenant_id": tenant.id,
        "billing_status": "trialing" if tenant.status == "trial" else "payment_required",
        "access_note": billing_svc.ACCESS_NOTES["trialing"],
        "checkout_path": billing_svc.checkout_path(),
        "plan": None,
        "authorization_present": False,
        "auto_renew": False,
    }
    body["trial_ends_at"] = tenant.trial_ends_at
    body["tenant_status"] = tenant.status
    body["provider"] = billing_svc.provider_status()
    return env(body)


@router.get("/billing/plans")
async def my_billing_plans(
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from app import models as m
    from app.api import env

    await billing_svc.ensure_default_plans(db)
    rows = (
        await db.execute(
            select(m.PlatformBillingPlan)
            .where(m.PlatformBillingPlan.is_active == True)  # noqa: E712
            .order_by(m.PlatformBillingPlan.code)
        )
    ).scalars().all()
    await db.commit()
    return env([billing_svc.serialize_plan(row) for row in rows])


@router.post("/billing/consent")
async def billing_consent(
    payload: BillingConsentBody,
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    account = await billing_svc.record_consent(
        db, tenant, plan_code=payload.plan_code, accept=payload.accept, user_id=claims["sub"]
    )
    plan = await billing_svc._load_plan(db, account.plan_id)
    await db.commit()
    return env(billing_svc.serialize_account(account, plan), "Renewal consent recorded")


@router.post("/billing/checkout")
async def billing_checkout(
    payload: BillingCheckoutBody,
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    result = await billing_svc.start_checkout(
        db, tenant, plan_code=payload.plan_code, email=claims.get("email") or tenant.email or "billing@localhost"
    )
    await db.commit()
    return env(result, "Checkout started")


@router.get("/billing/checkout/return")
async def billing_checkout_return(
    reference: str = "",
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    """A browser return never marks an invoice paid."""
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    account = await billing_svc.get_account(db, tenant.id)
    plan = await billing_svc._load_plan(db, account.plan_id) if account else None
    body = billing_svc.serialize_account(account, plan) if account else {}
    body["return_reference"] = reference
    body["confirmed_by_redirect"] = False
    return env(body)


@router.post("/billing/sandbox/authorize")
async def billing_sandbox_authorize(
    payload: BillingSandboxAuthorizeBody,
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    if settings.APP_ENV.lower() == "production" or get_gateway().provider != "mock":
        raise HTTPException(status_code=404, detail="Not found")
    tenant = await _tenant_admin(claims, db)
    account = await billing_svc.attach_sandbox_authorization(
        db, tenant, authorization_code=payload.authorization_code, user_id=claims["sub"]
    )
    plan = await billing_svc._load_plan(db, account.plan_id)
    await db.commit()
    return env(billing_svc.serialize_account(account, plan), "Sandbox payment method saved")


@router.post("/billing/cancel")
async def billing_cancel(
    payload: BillingCancelBody,
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    account = await billing_svc.cancel_auto_renew(
        db, tenant, confirm=payload.confirm, user_id=claims["sub"]
    )
    plan = await billing_svc._load_plan(db, account.plan_id)
    await db.commit()
    return env(billing_svc.serialize_account(account, plan), "Future renewals canceled")


@router.get("/billing/invoices")
async def my_billing_invoices(
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    rows = await billing_svc.list_invoices(db, tenant.id)
    return env([billing_svc.serialize_invoice(row) for row in rows])


@router.post("/billing/webhooks/{provider}")
async def billing_webhook(
    provider: str,
    request: Request,
    x_paystack_signature: str | None = Header(default=None, alias="x-paystack-signature"),
    x_ribdigi_billing_signature: str | None = Header(default=None, alias="x-ribdigi-billing-signature"),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    name = (provider or "").strip().lower()
    if name not in {"mock", "paystack"}:
        raise HTTPException(status_code=404, detail="Unknown billing provider")
    body = await request.body()
    header = x_paystack_signature if name == "paystack" else x_ribdigi_billing_signature
    if not verify_webhook_signature(name, body, header):
        raise HTTPException(status_code=401, detail="Invalid billing webhook signature")
    try:
        event = webhook_json(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid billing webhook body") from exc
    result = await billing_svc.apply_webhook(db, provider=name, event=event)
    await db.commit()
    return env(result, "Webhook processed")
