"""SaaS billing HTTP routes. Platform-owner plans and tenant consent stay separate from POS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import saas_billing as billing_svc
from app import tenants as tenants_svc
from app import billing_gateway_setup as gateway_setup
from app.billing_gateway import (
    current_gateway,
    normalize_webhook_event,
    verify_webhook_signature,
    webhook_json,
)
from app.billing_schemas import (
    BillingAssignBody,
    BillingCancelBody,
    BillingCheckoutBody,
    BillingConsentBody,
    BillingGatewayRotate,
    BillingGatewayWrite,
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


async def _visible_provider(db) -> dict:
    """Show the enabled gateway name. Sandbox and an untested gateway are not a live charge."""
    status = billing_svc.provider_status()
    row = await gateway_setup._row(db)
    if row is None or not row.enabled or not row.last_test_ok:
        return status
    name = (row.provider or "").strip().lower()
    status = dict(status)
    status["provider"] = name or status["provider"]
    status["configured"] = True
    status["live_charges"] = name not in {"", "mock", "unconfigured"} and (row.mode or "") == "live"
    return status


@router.get("/platform/billing/status")
async def billing_provider_status(
    request: Request,
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    body = billing_svc.provider_status()
    row = await gateway_setup._row(db)
    provider = (row.provider if row else body["provider"])
    body["gateway"] = gateway_setup.public_view(
        row, webhook_url=gateway_setup.webhook_url_for(request, provider)
    )
    body["connected"] = bool(body["gateway"]["connected"])
    return env(body)


@router.put("/platform/billing/gateway")
async def save_billing_gateway(
    payload: BillingGatewayWrite,
    request: Request,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    from app.billing_gateway import normalize_billing_provider

    normalize_billing_provider(payload.provider)
    if payload.mode.strip().lower() not in {"sandbox", "live"}:
        raise HTTPException(status_code=422, detail="mode must be sandbox or live")
    body = await gateway_setup.save_gateway(db, payload, actor=claims, request=request)
    await db.commit()
    return env(body, "Gateway saved. Run a connection test before enabling it.")


@router.post("/platform/billing/gateway/test")
async def test_billing_gateway(
    request: Request,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    body = await gateway_setup.test_gateway(db, actor=claims, request=request)
    await db.commit()
    return env(body, "Connection test finished")


@router.post("/platform/billing/gateway/enable")
async def enable_billing_gateway(
    request: Request,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    body = await gateway_setup.set_enabled(db, enabled=True, actor=claims, request=request)
    await db.commit()
    return env(body, "Gateway enabled")


@router.post("/platform/billing/gateway/disable")
async def disable_billing_gateway(
    request: Request,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    body = await gateway_setup.set_enabled(db, enabled=False, actor=claims, request=request)
    await db.commit()
    return env(body, "Gateway disabled")


@router.post("/platform/billing/gateway/rotate")
async def rotate_billing_gateway(
    payload: BillingGatewayRotate,
    request: Request,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    body = await gateway_setup.rotate_gateway(db, payload, actor=claims, request=request)
    await db.commit()
    return env(body, "Credentials rotated. Test the connection again before enabling.")


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


@router.delete("/platform/billing/plans/{plan_id}")
async def delete_billing_plan(
    plan_id: str,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _owner(claims)
    from app.api import env

    body = await billing_svc.delete_plan(db, plan_id, actor=claims)
    await db.commit()
    return env(body, "Billing plan deleted")


@router.get("/platform/billing/companies")
async def billing_companies(
    claims=Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Company plans for platform staff. Does not record a payment or expose gateway secrets."""
    del claims
    from app.api import env

    rows = await billing_svc.company_billing_roster(db)
    await db.commit()
    return env(rows)


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
    invoices = await billing_svc.serialize_tenant_invoices(db, tenant.id)
    return env(
        {
            "tenant_id": tenant.id,
            "slug": tenant.slug,
            "company_name": tenant.company_name,
            "tenant_status": tenant.status,
            "trial_ends_at": tenant.trial_ends_at,
            "account": billing_svc.serialize_account(account, plan) if account else None,
            "invoices": invoices,
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


def _tenant_account_body(account, plan) -> dict:
    body = billing_svc.serialize_account(account, plan)
    if account and plan and body.get("plan"):
        body["plan"] = billing_svc.serialize_assigned_plan(account, plan)
    return body


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
    body = _tenant_account_body(account, plan) if account else billing_svc.account_view_without_profile(tenant)
    body["trial_ends_at"] = tenant.trial_ends_at
    body["tenant_status"] = tenant.status
    body["provider"] = await _visible_provider(db)
    body = billing_svc.apply_assigned_amount_to_account_body(body, account, tenant)
    if not isinstance(body.get("plan"), dict):
        body["plan"] = billing_svc.company_package_plan(tenant)
    if not body.get("next_renewal_at") and getattr(tenant, "subscription_ends_at", None):
        body["next_renewal_at"] = tenant.subscription_ends_at
    return env(body)


@router.get("/billing/plans")
async def my_billing_plans(
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    await billing_svc.ensure_default_plans(db)
    account = await billing_svc.get_account(db, tenant.id)
    plan = await billing_svc._load_plan(db, account.plan_id) if account else None
    await db.commit()
    if account is None or plan is None:
        return env([])
    return env([billing_svc.serialize_assigned_plan(account, plan)])


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
    return env(_tenant_account_body(account, plan), "Renewal consent recorded")


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
    """A browser return reports the profile already stored. It never marks an invoice paid."""
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    account = await billing_svc.get_account(db, tenant.id)
    plan = await billing_svc._load_plan(db, account.plan_id) if account else None
    body = _tenant_account_body(account, plan) if account else {}
    expected = f"checkout:{account.id}:{account.plan_id}" if account and account.plan_id else ""
    body["return_reference"] = reference
    body["reference_matches_checkout"] = bool(expected) and reference.strip() == expected
    body["confirmed_by_redirect"] = False
    body["paid"] = False
    body["provider"] = await _visible_provider(db)
    return env(body)


@router.post("/billing/sandbox/authorize")
async def billing_sandbox_authorize(
    payload: BillingSandboxAuthorizeBody,
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    if settings.APP_ENV.lower() == "production" or (await current_gateway(db)).provider != "mock":
        raise HTTPException(status_code=404, detail="Not found")
    tenant = await _tenant_admin(claims, db)
    account = await billing_svc.attach_sandbox_authorization(
        db, tenant, authorization_code=payload.authorization_code, user_id=claims["sub"]
    )
    plan = await billing_svc._load_plan(db, account.plan_id)
    await db.commit()
    return env(_tenant_account_body(account, plan), "Sandbox payment method saved")


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
    return env(_tenant_account_body(account, plan), "Future renewals canceled")


@router.get("/billing/invoices")
async def my_billing_invoices(
    claims=Depends(require_roles("company_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    tenant = await _tenant_admin(claims, db)
    rows = await billing_svc.serialize_tenant_invoices(db, tenant.id)
    return env(rows)


@router.post("/billing/webhooks/{provider}")
async def billing_webhook(
    provider: str,
    request: Request,
    x_paystack_signature: str | None = Header(default=None, alias="x-paystack-signature"),
    x_ribdigi_billing_signature: str | None = Header(default=None, alias="x-ribdigi-billing-signature"),
    x_verif_hash: str | None = Header(default=None, alias="verif-hash"),
    x_flutterwave_signature: str | None = Header(default=None, alias="flutterwave-signature"),
    db: AsyncSession = Depends(get_db),
):
    from app.api import env

    from app.billing_gateway import BILLING_PROVIDERS, is_custom_billing_provider

    name = (provider or "").strip().lower()
    if name not in BILLING_PROVIDERS and not is_custom_billing_provider(name):
        raise HTTPException(status_code=404, detail="Unknown billing provider")
    body = await request.body()
    if name == "paystack":
        header = x_paystack_signature
    elif name == "flutterwave":
        header = x_verif_hash or x_flutterwave_signature
    else:
        header = x_ribdigi_billing_signature
    from app.billing_gateway import webhook_signing_secret

    stored_secret = await webhook_signing_secret(db, name)
    if not verify_webhook_signature(name, body, header, secret=stored_secret):
        await gateway_setup.note_webhook(db, provider=name, outcome="signature_rejected")
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid billing webhook signature")
    try:
        event = webhook_json(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid billing webhook body") from exc
    event = normalize_webhook_event(name, event)
    result = await billing_svc.apply_webhook(db, provider=name, event=event)
    await gateway_setup.note_webhook(db, provider=name, outcome=str(result.get("outcome") or "processed"))
    await db.commit()
    return env(result, "Webhook processed")
