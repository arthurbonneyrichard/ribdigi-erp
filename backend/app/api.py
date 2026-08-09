from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.db import get_db
from app.inventory import apply_line_items_stock, apply_stock_change
from app.rbac import (
    RECORD_SCOPE_KEY,
    VALID_ROLES,
    apply_created_by_scope,
    assert_record_access,
    list_role_catalog,
    normalize_record_scope,
    permissions_for_role,
    record_scope_from_permissions,
    serialize_user,
)
from app import purchasing as purchasing_svc
from app import sales as sales_svc
from app import sales_docs as sales_docs_svc
from app import catalog as catalog_svc
from app import pos as pos_svc
from app import expenses as expenses_svc
from app import tax as tax_svc
from app import stores as stores_svc
from app import credit as credit_svc
from app import reports as reports_svc
from app import report_export as report_export_svc
from app import report_schedules as report_schedules_svc
from app import notifications as notifications_svc
from app import audit as audit_svc
from app import backup as backup_svc
from app import tenants as tenants_svc
from app import storage as storage_svc
from app import cheques as cheques_svc
from app import stock_counts as stock_counts_svc
from app import catalog_meta as catalog_meta_svc
from app import product_images as product_images_svc
from app import barcodes as barcode_svc
from app import product_import as product_import_svc
from app import product_lookup as product_lookup_svc
from app import stock_import as stock_import_svc
from app import barcode_labels as barcode_labels_svc
from app import suppliers as suppliers_svc
from app.config import settings
from app.schemas import (
    BarcodeLabelPrintRequest,
    BrandCreate,
    BrandUpdate,
    CreditLimitUpdate,
    CustomerPaymentCreate,
    EarlyPaySettingsUpdate,
    EmailVerifyConfirm,
    ExchangeRateRefresh,
    ExchangeRateUpsert,
    FxAutoRefreshUpdate,
    BankConnectionCreate,
    BankConnectionUpdate,
    ExpenseCategoryCreate,
    ExpenseCreate,
    ExpenseDecision,
    ExpenseThresholdUpdate,
    ExpenseUpdate,
    GrnCreate,
    JournalCreate,
    Login,
    NotificationPreferencesUpdate,
    PartyCreate,
    SupplierContactCreate,
    SupplierCreate,
    SupplierUpdate,
    PasswordResetConfirm,
    PasswordResetRequest,
    PosSaleCreate,
    PosSessionClose,
    PosSessionOpen,
    PosDrawerOpen,
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCreate,
    ProductImagePrimaryUpdate,
    ProductVariantCreate,
    ProductVariantUpdate,
    ProfileUpdate,
    PurchaseOrderAmend,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseRequestApprovalSettingsUpdate,
    PurchaseRequestCreate,
    PurchaseRequestDecision,
    PurchaseRequestReject,
    UnitOfMeasureCreate,
    UnitOfMeasureUpdate,
    PurchaseInvoiceCreate,
    PurchaseInvoiceUpdate,
    PurchaseReturnCreate,
    RecurringExpenseCreate,
    RefreshRequest,
    SalesInvoiceCreate,
    SalesOrderCreate,
    SalesQuotationCreate,
    SalesReturnCreate,
    SmsTestRequest,
    StockAdjust,
    StockMove,
    StockTransferCreate,
    StoreCreate,
    StoreDrawerSettingsUpdate,
    StoreReorderPolicyUpdate,
    InventoryFefoSettingsUpdate,
    SupplierPaymentCreate,
    TaxCalculateRequest,
    TaxCreate,
    TenantCreate,
    TenantProfileUpdate,
    TenantSuspendRequest,
    TransactionCreate,
    EmailTestRequest,
    TwoFactorConfirm,
    TwoFactorDisable,
    TwoFactorVerify,
    WebAuthnLoginOptions,
    WebAuthnLoginVerify,
    WebAuthnRegisterVerify,
    UserCreate,
    UserUpdate,
    ProductUpdate,
    StockCountCreate,
    StockCountItemsUpdate,
    WarehouseCreate,
)
from app.security import (
    create_access_token,
    current_claims,
    hash_password,
    hash_token,
    issue_one_time_token,
    issue_refresh_token,
    require_permission,
    require_roles,
    validate_password_strength,
    verify_password,
)
from app import totp as totp_svc

api = APIRouter(prefix="/api/v1")


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


async def tenant_pk(db: AsyncSession, tenant_ref: str) -> str:
    tenant = (
        await db.execute(
            select(m.Tenant).where((m.Tenant.id == tenant_ref) | (m.Tenant.slug == tenant_ref))
        )
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant.id


async def seed_tenant_defaults(db: AsyncSession, tenant_id: str) -> None:
    from app.accounting import ensure_default_accounts
    from app import catalog_meta as catalog_meta_svc

    await ensure_default_accounts(db, tenant_id)
    await expenses_svc.ensure_default_categories(db, tenant_id)
    await catalog_meta_svc.ensure_default_catalog(db, tenant_id)
    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Welcome to RIBDIGI ERP",
        message="Your tenant was provisioned. Complete company setup and add products to begin.",
    )
    db.add_all(
        [
            m.TaxRate(
                tenant_id=tenant_id,
                name="VAT",
                rate=15,
                tax_type="vat",
                pricing_mode="exclusive",
                is_default=True,
                is_active=True,
            ),
            m.Warehouse(tenant_id=tenant_id, name="Main Warehouse", code="WH-MAIN"),
        ]
    )


async def create_session(
    db: AsyncSession,
    *,
    user: m.User,
    request: Request | None = None,
) -> tuple[str, str]:
    refresh_raw, refresh_hash, refresh_exp = issue_refresh_token()
    jti = __import__("secrets").token_hex(16)
    access = create_access_token(user.id, user.tenant_id, user.role, jti=jti)
    session = m.AuthSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        jti=jti,
        user_agent=(request.headers.get("user-agent") if request else None),
        ip_address=(request.client.host if request and request.client else None),
        expires_at=refresh_exp,
    )
    db.add(session)
    return access, refresh_raw


@api.get("/health")
async def health():
    return env({"status": "ok", "service": "ribdigi-erp"})


@api.post("/tenants")
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)):
    validate_password_strength(payload.admin_password)
    existing = (
        await db.execute(select(m.Tenant).where(m.Tenant.slug == payload.slug))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug exists")

    tenant = m.Tenant(
        slug=payload.slug,
        company_name=payload.company_name,
        industry=payload.industry,
        currency=payload.currency,
        status="trial",
        trial_ends_at=tenants_svc.default_trial_ends_at(),
        trial_notices={},
    )
    db.add(tenant)
    await db.flush()

    admin = m.User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        full_name="Company Administrator",
        password_hash=hash_password(payload.admin_password),
        role="company_admin",
        email_verified=False,
        permissions=permissions_for_role("company_admin"),
    )
    db.add(admin)
    await db.flush()
    await seed_tenant_defaults(db, tenant.id)

    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=tenant.id,
            user_id=admin.id,
            purpose="email_verify",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    await db.commit()
    await db.refresh(tenant)

    data = {"tenant_id": tenant.id, "slug": tenant.slug, "status": tenant.status}
    from app import emailer

    email_result = await emailer.send_verification_email(
        to=payload.admin_email, token=raw, company_name=tenant.company_name
    )
    data["email"] = {
        "sent": email_result.sent,
        "mode": email_result.mode,
        "error": email_result.error,
    }
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["email_verification_token"] = raw
    return env(data, "Tenant created. Verify admin email before production use.")


@api.get("/tenants/me")
async def tenant_me(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    tenant = await tenants_svc.ensure_trial_state(db, tenant)
    if tenant.status == "suspended":
        raise HTTPException(status_code=403, detail="Tenant is suspended")
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant))


@api.patch("/tenants/me")
async def tenant_me_update(
    payload: TenantProfileUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    tenant = await tenants_svc.update_profile(
        db,
        tenant,
        company_name=payload.company_name,
        industry=payload.industry,
        currency=payload.currency,
        phone=payload.phone,
        email=str(payload.email) if payload.email is not None else None,
        website=payload.website,
        address=payload.address,
        timezone=payload.timezone,
        fiscal_year_start=payload.fiscal_year_start,
        tax_jurisdiction=payload.tax_jurisdiction,
        tax_registration_number=payload.tax_registration_number,
        tax_filing_period=payload.tax_filing_period,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="profile_update",
        entity="tenant",
        entity_id=tenant.id,
        details={"company_name": tenant.company_name},
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Company profile updated")


@api.post("/tenants/me/suspend")
async def tenant_me_suspend(
    payload: TenantSuspendRequest | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    reason = payload.reason if payload else None
    tenant = await tenants_svc.suspend_tenant(db, tenant, reason=reason)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="suspend",
        entity="tenant",
        entity_id=tenant.id,
        details={"reason": reason},
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Tenant suspended; sessions revoked")


@api.post("/tenants/me/activate")
async def tenant_me_activate(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Activate own tenant when already authenticated (trial/grace → active). Suspended cannot self-activate."""
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if tenant.status == "suspended":
        raise HTTPException(
            status_code=403,
            detail="Suspended tenants cannot self-activate; contact platform support",
        )
    tenant = await tenants_svc.activate_tenant(db, tenant)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="activate",
        entity="tenant",
        entity_id=tenant.id,
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Tenant activated")


@api.post("/tenants/me/logo")
async def tenant_me_logo_upload(
    file: UploadFile = File(...),
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    stored = await storage_svc.save_upload(
        tenant_id=tenant.id,
        category="logos",
        upload=file,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    if tenant.logo_url:
        storage_svc.delete_key(tenant.logo_url, tenant_id=tenant.id)
    tenant.logo_url = stored.key
    await audit_svc.record_event(
        db,
        tenant_id=tenant.id,
        user_id=claims["sub"],
        module="tenants",
        action="logo_upload",
        entity="tenant",
        entity_id=tenant.id,
        details={"key": stored.key, "size": stored.size, "content_type": stored.content_type},
    )
    await db.commit()
    return env(
        {
            **tenants_svc.serialize_tenant(tenant),
            "uploaded": {
                "key": stored.key,
                "size": stored.size,
                "content_type": stored.content_type,
                "filename": stored.original_filename,
            },
        },
        "Logo uploaded",
    )


@api.get("/tenants/me/logo")
async def tenant_me_logo_get(
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if not tenant.logo_url:
        raise HTTPException(status_code=404, detail="No logo uploaded")
    return storage_svc.media_response(tenant.logo_url, tenant_id=tenant.id)


@api.delete("/tenants/me/logo")
async def tenant_me_logo_delete(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if not tenant.logo_url:
        raise HTTPException(status_code=404, detail="No logo uploaded")
    storage_svc.delete_key(tenant.logo_url, tenant_id=tenant.id)
    tenant.logo_url = None
    await audit_svc.record_event(
        db,
        tenant_id=tenant.id,
        user_id=claims["sub"],
        module="tenants",
        action="logo_delete",
        entity="tenant",
        entity_id=tenant.id,
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Logo removed")


@api.get("/tenants")
async def tenants_list(
    status: str | None = None,
    claims=Depends(require_roles("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = await tenants_svc.list_tenants(db, status=status)
    return env([tenants_svc.serialize_tenant(t) for t in rows])


@api.post("/tenants/{tenant_ref}/suspend")
async def tenant_suspend_by_ref(
    tenant_ref: str,
    payload: TenantSuspendRequest | None = None,
    claims=Depends(require_roles("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    reason = payload.reason if payload else None
    tenant = await tenants_svc.suspend_tenant(db, tenant, reason=reason)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="suspend",
        entity="tenant",
        entity_id=tenant.id,
        details={"reason": reason, "target_tenant": tenant.id},
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Tenant suspended")


@api.post("/tenants/{tenant_ref}/activate")
async def tenant_activate_by_ref(
    tenant_ref: str,
    claims=Depends(require_roles("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    tenant = await tenants_svc.activate_tenant(db, tenant)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="activate",
        entity="tenant",
        entity_id=tenant.id,
        details={"target_tenant": tenant.id},
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Tenant activated")


@api.get("/settings/email")
async def settings_email_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
):
    from app import emailer

    return env(emailer.email_status())


@api.post("/settings/email/test")
async def settings_email_test(
    payload: EmailTestRequest | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import emailer

    user = await db.get(m.User, claims["sub"])
    to = str(payload.to) if payload and payload.to else (user.email if user else None)
    if not to:
        raise HTTPException(status_code=400, detail="No recipient email available")
    result = await emailer.send_test_email(to=to)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="settings",
        action="email_test",
        entity="email",
        details={"to": to, "sent": result.sent, "mode": result.mode},
    )
    await db.commit()
    if not result.sent and result.mode == "smtp":
        raise HTTPException(status_code=502, detail=result.error or "SMTP send failed")
    return env(
        {"sent": result.sent, "mode": result.mode, "to": to, "error": result.error},
        "Test email dispatched",
    )


@api.get("/settings/sms")
async def settings_sms_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
):
    from app import sms as sms_svc

    return env(sms_svc.sms_status())


@api.get("/settings/storage")
async def settings_storage_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
):
    return env(storage_svc.storage_status())


@api.post("/settings/sms/test")
async def settings_sms_test(
    payload: SmsTestRequest | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import sms as sms_svc

    user = await db.get(m.User, claims["sub"])
    to = (payload.to if payload and payload.to else None) or (user.phone if user else None)
    if not to:
        raise HTTPException(
            status_code=400,
            detail="No recipient phone — set your profile phone or pass `to`",
        )
    result = await sms_svc.send_test_sms(to=to)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="settings",
        action="sms_test",
        entity="sms",
        details={"to": result.recipients, "sent": result.sent, "mode": result.mode},
    )
    await db.commit()
    if not result.sent and result.mode == "twilio":
        raise HTTPException(status_code=502, detail=result.error or "Twilio send failed")
    return env(
        {
            "sent": result.sent,
            "mode": result.mode,
            "to": result.recipients,
            "sid": result.sid,
            "error": result.error,
        },
        "Test SMS dispatched",
    )


@api.post("/auth/login")
async def login(payload: Login, request: Request, db: AsyncSession = Depends(get_db)):
    tenant = await tenants_svc.resolve_tenant(db, payload.tenant_id)
    tenant = await tenants_svc.ensure_trial_state(db, tenant)
    tenants_svc.assert_tenant_active_for_login(tenant)
    tenant_id = tenant.id
    user = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant_id,
                m.User.email == payload.email,
            )
        )
    ).scalar_one_or_none()

    if user and user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(status_code=423, detail="Account temporarily locked")

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + __import__("datetime").timedelta(minutes=30)
                user.failed_login_attempts = 0
            await audit_svc.record_event(
                db,
                tenant_id=tenant_id,
                user_id=user.id,
                module="auth",
                action="login_failed",
                entity="user",
                entity_id=user.id,
                details={"email": payload.email},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.failed_login_attempts = 0
    user.locked_until = None

    from app import webauthn_svc as webauthn

    has_webauthn = await webauthn.user_has_webauthn(db, user.id)
    needs_2fa = bool(user.totp_enabled) or has_webauthn
    methods: list[str] = []
    if user.totp_enabled:
        methods.append("totp")
    if has_webauthn:
        methods.append("webauthn")

    # 2FA challenge when TOTP and/or passkeys are enrolled
    if needs_2fa:
        if payload.totp_code and user.totp_enabled:
            ok = await totp_svc.verify_user_second_factor(db, user, payload.totp_code)
            if not ok:
                user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
                await audit_svc.record_event(
                    db,
                    tenant_id=tenant_id,
                    user_id=user.id,
                    module="auth",
                    action="2fa_failed",
                    entity="user",
                    entity_id=user.id,
                    details={"email": user.email},
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )
                await db.commit()
                raise HTTPException(status_code=401, detail="Invalid 2FA code")
        elif not payload.totp_code:
            challenge = totp_svc.create_challenge_token(
                user_id=user.id, tenant_id=tenant_id, role=user.role
            )
            await audit_svc.record_event(
                db,
                tenant_id=tenant_id,
                user_id=user.id,
                module="auth",
                action="2fa_challenge",
                entity="user",
                entity_id=user.id,
                details={"email": user.email, "methods": methods},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            await db.commit()
            return env(
                {
                    "requires_2fa": True,
                    "challenge_token": challenge,
                    "expires_in": totp_svc.CHALLENGE_TTL_MINUTES * 60,
                    "methods": methods,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "role": user.role,
                        "tenant_id": tenant_id,
                    },
                },
                "2FA required",
            )
        elif payload.totp_code and not user.totp_enabled:
            raise HTTPException(
                status_code=400,
                detail="TOTP is not enabled; use a passkey to complete login",
            )

    access, refresh = await create_session(db, user=user, request=request)
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        module="auth",
        action="login",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "totp": bool(user.totp_enabled), "webauthn": has_webauthn},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    has_mfa = await webauthn.user_has_mfa(db, user)
    return env(
        {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_enroll_2fa": totp_svc.role_requires_2fa(user.role) and not has_mfa,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": tenant_id,
                "email_verified": user.email_verified,
                "totp_enabled": bool(user.totp_enabled),
                "webauthn_enabled": has_webauthn,
            },
        }
    )


@api.post("/auth/2fa/verify")
async def auth_2fa_verify(payload: TwoFactorVerify, request: Request, db: AsyncSession = Depends(get_db)):
    claims = totp_svc.decode_challenge_token(payload.challenge_token)
    user = await db.get(m.User, claims["sub"])
    if not user or not user.is_active or user.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=401, detail="Invalid 2FA challenge user")
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled for this user")
    ok = await totp_svc.verify_user_second_factor(db, user, payload.code)
    if not ok:
        await audit_svc.record_event(
            db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            module="auth",
            action="2fa_failed",
            entity="user",
            entity_id=user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid 2FA code")

    access, refresh = await create_session(db, user=user, request=request)
    await audit_svc.record_event(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        module="auth",
        action="login",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "totp": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_enroll_2fa": False,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": user.tenant_id,
                "email_verified": user.email_verified,
                "totp_enabled": True,
            },
        }
    )


@api.get("/auth/2fa/status")
async def auth_2fa_status(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    from app import webauthn_svc as webauthn

    user = await db.get(m.User, claims["sub"])
    payload = totp_svc.status_payload(user)
    count = await webauthn.count_credentials(db, user.id)
    has_mfa = await webauthn.user_has_mfa(db, user)
    payload.update(
        {
            "webauthn_enabled": count > 0,
            "webauthn_count": count,
            "must_enroll_2fa": totp_svc.role_requires_2fa(user.role) and not has_mfa,
            "methods": (
                (["totp"] if user.totp_enabled else [])
                + (["webauthn"] if count > 0 else [])
            ),
        }
    )
    return env(payload)


@api.post("/auth/webauthn/register/options")
async def webauthn_register_options(
    claims=Depends(current_claims), db: AsyncSession = Depends(get_db)
):
    from app import webauthn_svc as webauthn

    user = await db.get(m.User, claims["sub"])
    options = await webauthn.registration_options(db, user)
    await db.commit()
    return env(options)


@api.post("/auth/webauthn/register/verify")
async def webauthn_register_verify(
    payload: WebAuthnRegisterVerify,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    from app import webauthn_svc as webauthn

    user = await db.get(m.User, claims["sub"])
    row = await webauthn.verify_registration(
        db, user, credential=payload.credential, name=payload.name
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="webauthn_register",
        entity="webauthn_credential",
        entity_id=row.id,
        details={"name": row.name},
    )
    await db.commit()
    return env(webauthn.serialize_credential(row), "Passkey registered")


@api.get("/auth/webauthn/credentials")
async def webauthn_list_credentials(
    claims=Depends(current_claims), db: AsyncSession = Depends(get_db)
):
    from app import webauthn_svc as webauthn

    rows = await webauthn.list_credentials(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"]
    )
    return env([webauthn.serialize_credential(r) for r in rows])


@api.delete("/auth/webauthn/credentials/{credential_id}")
async def webauthn_delete_credential(
    credential_id: str,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    from app import webauthn_svc as webauthn

    await webauthn.delete_credential(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        credential_id=credential_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="webauthn_delete",
        entity="webauthn_credential",
        entity_id=credential_id,
    )
    await db.commit()
    return env({"id": credential_id}, "Passkey removed")


@api.post("/auth/webauthn/login/options")
async def webauthn_login_options(payload: WebAuthnLoginOptions, db: AsyncSession = Depends(get_db)):
    from app import webauthn_svc as webauthn

    claims = totp_svc.decode_challenge_token(payload.challenge_token)
    user = await db.get(m.User, claims["sub"])
    if not user or not user.is_active or user.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=401, detail="Invalid 2FA challenge user")
    options = await webauthn.authentication_options(db, user)
    await db.commit()
    return env(options)


@api.post("/auth/webauthn/login/verify")
async def webauthn_login_verify(
    payload: WebAuthnLoginVerify, request: Request, db: AsyncSession = Depends(get_db)
):
    from app import webauthn_svc as webauthn

    claims = totp_svc.decode_challenge_token(payload.challenge_token)
    user = await db.get(m.User, claims["sub"])
    if not user or not user.is_active or user.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=401, detail="Invalid 2FA challenge user")
    await webauthn.verify_authentication(db, user, credential=payload.credential)
    access, refresh = await create_session(db, user=user, request=request)
    await audit_svc.record_event(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        module="auth",
        action="login",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "webauthn": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_enroll_2fa": False,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": user.tenant_id,
                "email_verified": user.email_verified,
                "totp_enabled": bool(user.totp_enabled),
                "webauthn_enabled": True,
            },
        }
    )


@api.post("/auth/2fa/setup")
async def auth_2fa_setup(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    user = await db.get(m.User, claims["sub"])
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    data = await totp_svc.start_setup(db, user, tenant)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="2fa_setup_started",
        entity="user",
        entity_id=user.id,
    )
    await db.commit()
    return env(data, "Scan QR code and confirm with authenticator code")


@api.post("/auth/2fa/confirm")
async def auth_2fa_confirm(
    payload: TwoFactorConfirm,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(m.User, claims["sub"])
    codes = await totp_svc.confirm_setup(db, user, payload.code)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="2fa_enabled",
        entity="user",
        entity_id=user.id,
    )
    await db.commit()
    return env(
        {"enabled": True, "backup_codes": codes},
        "2FA enabled. Store backup codes securely; they are shown once.",
    )


@api.post("/auth/2fa/backup-codes")
async def auth_2fa_regenerate_backup_codes(
    payload: TwoFactorConfirm,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(m.User, claims["sub"])
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="Enable 2FA first")
    ok = await totp_svc.verify_user_second_factor(db, user, payload.code)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    codes = await totp_svc.replace_backup_codes(db, user)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="2fa_backup_codes_regenerated",
        entity="user",
        entity_id=user.id,
    )
    await db.commit()
    return env({"backup_codes": codes}, "New backup codes generated")


@api.post("/auth/2fa/disable")
async def auth_2fa_disable(
    payload: TwoFactorDisable,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(m.User, claims["sub"])
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    if totp_svc.role_requires_2fa(user.role):
        raise HTTPException(
            status_code=400,
            detail="2FA cannot be disabled for this role",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    ok = await totp_svc.verify_user_second_factor(db, user, payload.code)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    await totp_svc.disable_2fa(db, user)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="2fa_disabled",
        entity="user",
        entity_id=user.id,
    )
    await db.commit()
    return env({"enabled": False}, "2FA disabled")


@api.post("/auth/refresh")
async def refresh(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    session = (
        await db.execute(select(m.AuthSession).where(m.AuthSession.refresh_token_hash == token_hash))
    ).scalar_one_or_none()
    if not session or session.revoked_at is not None or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.get(m.User, session.user_id)
    if not user or not user.is_active or user.tenant_id != session.tenant_id:
        raise HTTPException(status_code=401, detail="Invalid session user")

    session.revoked_at = datetime.utcnow()
    access, refresh_raw = await create_session(db, user=user, request=request)
    await db.commit()
    return env(
        {
            "access_token": access,
            "refresh_token": refresh_raw,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@api.post("/auth/logout")
async def logout(request: Request, claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    jti = claims.get("jti")
    if jti:
        session = (
            await db.execute(
                select(m.AuthSession).where(
                    m.AuthSession.jti == jti,
                    m.AuthSession.tenant_id == claims["tenant_id"],
                )
            )
        ).scalar_one_or_none()
        if session and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="logout",
        entity="user",
        entity_id=claims["sub"],
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env({"revoked": True})


@api.get("/auth/sessions")
async def list_sessions(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(m.AuthSession)
            .where(
                m.AuthSession.tenant_id == claims["tenant_id"],
                m.AuthSession.user_id == claims["sub"],
                m.AuthSession.revoked_at.is_(None),
            )
            .order_by(m.AuthSession.created_at.desc())
        )
    ).scalars().all()
    return env(
        [
            {
                "id": s.id,
                "jti": s.jti,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "expires_at": s.expires_at,
                "created_at": s.created_at,
                "current": s.jti == claims.get("jti"),
            }
            for s in rows
        ]
    )


@api.delete("/auth/sessions/{session_id}")
async def revoke_session(session_id: str, claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    session = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.id == session_id,
                m.AuthSession.tenant_id == claims["tenant_id"],
                m.AuthSession.user_id == claims["sub"],
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.revoked_at = datetime.utcnow()
    await db.commit()
    return env({"id": session_id, "revoked": True})


@api.post("/auth/password-reset-request")
async def password_reset_request(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    tenant_id = await tenant_pk(db, payload.tenant_id)
    user = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == tenant_id, m.User.email == payload.email)
        )
    ).scalar_one_or_none()
    data: dict = {"requested": True}
    if user:
        raw, token_hash, expires = issue_one_time_token()
        db.add(
            m.AuthToken(
                tenant_id=tenant_id,
                user_id=user.id,
                purpose="password_reset",
                token_hash=token_hash,
                expires_at=expires,
            )
        )
        await db.commit()
        from app import emailer

        email_result = await emailer.send_password_reset_email(to=user.email, token=raw)
        data["email"] = {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        }
        if settings.DEBUG or settings.APP_ENV.lower() != "production":
            data["reset_token"] = raw
    return env(data, "If the account exists, a reset token was issued")


@api.post("/auth/password-reset")
async def password_reset(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    validate_password_strength(payload.new_password)
    token_hash = hash_token(payload.token)
    row = (
        await db.execute(
            select(m.AuthToken).where(
                m.AuthToken.token_hash == token_hash,
                m.AuthToken.purpose == "password_reset",
            )
        )
    ).scalar_one_or_none()
    if not row or row.used_at is not None or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = await db.get(m.User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    user.password_hash = hash_password(payload.new_password)
    row.used_at = datetime.utcnow()

    sessions = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.user_id == user.id,
                m.AuthSession.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    for session in sessions:
        session.revoked_at = datetime.utcnow()

    await db.commit()
    return env({"reset": True})


@api.post("/auth/verify-email")
async def verify_email(payload: EmailVerifyConfirm, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    row = (
        await db.execute(
            select(m.AuthToken).where(
                m.AuthToken.token_hash == token_hash,
                m.AuthToken.purpose == "email_verify",
            )
        )
    ).scalar_one_or_none()
    if not row or row.used_at is not None or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user = await db.get(m.User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    user.email_verified = True
    row.used_at = datetime.utcnow()
    await db.commit()
    return env({"verified": True})


@api.get("/me")
async def me(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    user = await db.get(m.User, claims["sub"])
    perms = user.permissions or permissions_for_role(user.role)
    return env(
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "email_verified": user.email_verified,
            "permissions": perms,
            "record_scope": record_scope_from_permissions(user.role, perms if isinstance(perms, dict) else None),
            **totp_svc.status_payload(user),
        }
    )


@api.patch("/me")
async def update_me(
    payload: ProfileUpdate,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    from app import sms as sms_svc

    user = await db.get(m.User, claims["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.full_name is not None:
        name = payload.full_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="full_name cannot be empty")
        user.full_name = name
    if payload.phone is not None:
        phone = payload.phone.strip()
        if phone == "":
            user.phone = None
        else:
            normalized = sms_svc.normalize_phone(phone)
            if not normalized:
                raise HTTPException(status_code=400, detail="Invalid phone number")
            user.phone = normalized if normalized.startswith("+") else phone.strip()
    await db.commit()
    return env(
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
        },
        "Profile updated",
    )


async def _get_tenant_user(db: AsyncSession, tenant_id: str, user_id: str) -> m.User:
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _revoke_user_sessions(db: AsyncSession, *, tenant_id: str, user_id: str) -> int:
    now = datetime.utcnow()
    sessions = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.tenant_id == tenant_id,
                m.AuthSession.user_id == user_id,
                m.AuthSession.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    for session in sessions:
        session.revoked_at = now
    return len(sessions)


@api.get("/roles")
async def roles_catalog(claims=Depends(require_permission("users", "read"))):
    return env(list_role_catalog())


@api.get("/roles/{role}")
async def role_detail(role: str, claims=Depends(require_permission("users", "read"))):
    if role not in VALID_ROLES:
        raise HTTPException(status_code=404, detail="Role not found")
    catalog = {row["role"]: row for row in list_role_catalog()}
    return env(catalog[role])


@api.get("/users")
async def users(claims=Depends(require_permission("users", "read")), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(m.User)
            .where(m.User.tenant_id == claims["tenant_id"])
            .order_by(m.User.full_name.asc())
        )
    ).scalars().all()
    return env([serialize_user(u) for u in rows])


@api.get("/users/{user_id}")
async def get_user(
    user_id: str,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_tenant_user(db, claims["tenant_id"], user_id)
    return env(serialize_user(user))


@api.post("/users")
async def add_user(
    payload: UserCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {sorted(VALID_ROLES)}")
    if payload.role == "super_admin" and claims.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can create super_admin users")
    validate_password_strength(payload.password)
    exists = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == claims["tenant_id"],
                m.User.email == payload.email,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="User email already exists in tenant")
    user = m.User(
        tenant_id=claims["tenant_id"],
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
        permissions=permissions_for_role(payload.role),
        email_verified=False,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=claims["tenant_id"],
            user_id=user.id,
            purpose="email_verify",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="user_created",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "role": user.role},
    )
    from app import emailer

    email_result = await emailer.send_verification_email(to=user.email, token=raw)
    await db.commit()
    data = {
        "id": user.id,
        "user": serialize_user(user),
        "email": {"sent": email_result.sent, "mode": email_result.mode},
    }
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["email_verification_token"] = raw
    return env(data, "User created; verification email dispatched")


@api.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_tenant_user(db, claims["tenant_id"], user_id)
    changes: dict = {}

    if payload.full_name is not None:
        name = payload.full_name.strip()
        if len(name) < 2:
            raise HTTPException(status_code=400, detail="full_name must be at least 2 characters")
        user.full_name = name
        changes["full_name"] = name

    if payload.phone is not None:
        user.phone = payload.phone.strip() or None
        changes["phone"] = user.phone

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {sorted(VALID_ROLES)}")
        if payload.role == "super_admin" and claims.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Only super_admin can assign super_admin")
        if user.id == claims["sub"] and payload.role != user.role:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        if user.role != payload.role:
            changes["role"] = {"from": user.role, "to": payload.role}
            prev_scope = None
            if isinstance(user.permissions, dict):
                prev_scope = user.permissions.get(RECORD_SCOPE_KEY)
            user.role = payload.role
            perms = permissions_for_role(payload.role)
            if prev_scope is not None:
                perms[RECORD_SCOPE_KEY] = prev_scope
            user.permissions = perms

    if payload.password is not None:
        validate_password_strength(payload.password)
        user.password_hash = hash_password(payload.password)
        changes["password_reset"] = True
        await _revoke_user_sessions(db, tenant_id=claims["tenant_id"], user_id=user.id)

    if payload.is_active is not None:
        if user.id == claims["sub"] and payload.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
        if bool(user.is_active) != bool(payload.is_active):
            user.is_active = bool(payload.is_active)
            changes["is_active"] = user.is_active
            if not user.is_active:
                await _revoke_user_sessions(db, tenant_id=claims["tenant_id"], user_id=user.id)

    if payload.record_scope is not None:
        try:
            scope = normalize_record_scope(payload.record_scope)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        perms = dict(user.permissions or permissions_for_role(user.role))
        if perms.get(RECORD_SCOPE_KEY) != scope:
            perms[RECORD_SCOPE_KEY] = scope
            user.permissions = perms
            changes["record_scope"] = scope

    if not changes:
        return env(serialize_user(user), "No changes")

    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="user_updated",
        entity="user",
        entity_id=user.id,
        details=changes,
    )
    await db.commit()
    return env(serialize_user(user), "User updated")


@api.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete: deactivate the user and revoke sessions (no hard delete)."""
    user = await _get_tenant_user(db, claims["tenant_id"], user_id)
    if user.id == claims["sub"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    if not user.is_active:
        return env(serialize_user(user), "User already inactive")
    user.is_active = False
    revoked = await _revoke_user_sessions(db, tenant_id=claims["tenant_id"], user_id=user.id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="user_deactivated",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "sessions_revoked": revoked},
    )
    await db.commit()
    return env(serialize_user(user), "User deactivated")


@api.get("/dashboard")
async def dashboard(claims=Depends(require_permission("dashboard", "read")), db: AsyncSession = Depends(get_db)):
    tid = claims["tenant_id"]

    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    sales = await scalar(
        select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
            m.Transaction.tenant_id == tid,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
        )
    )
    purchases = await scalar(
        select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
            m.Transaction.tenant_id == tid,
            m.Transaction.tx_type == "purchase",
        )
    )
    expenses = await scalar(
        select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
            m.Expense.tenant_id == tid,
            m.Expense.status == "approved",
        )
    )
    products = await scalar(select(func.count(m.Product.id)).where(m.Product.tenant_id == tid))
    low = await scalar(
        select(func.count(m.Product.id)).where(
            m.Product.tenant_id == tid,
            m.Product.stock_qty <= m.Product.reorder_level,
        )
    )
    customers = await scalar(
        select(func.count(m.Party.id)).where(m.Party.tenant_id == tid, m.Party.kind == "customer")
    )
    suppliers = await scalar(
        select(func.count(m.Party.id)).where(m.Party.tenant_id == tid, m.Party.kind == "supplier")
    )
    return env(
        {
            "total_sales": float(sales),
            "total_purchases": float(purchases),
            "total_expenses": float(expenses),
            "products": products,
            "low_stock": low,
            "customers": customers,
            "suppliers": suppliers,
        }
    )


@api.get("/products")
async def products(claims=Depends(require_permission("inventory", "read")), db: AsyncSession = Depends(get_db)):
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    rows = (
        await db.execute(
            select(m.Product)
            .where(m.Product.tenant_id == claims["tenant_id"])
            .order_by(m.Product.name)
        )
    ).scalars().all()
    return env([catalog_meta_svc.serialize_product(p) for p in rows])


@api.get("/inventory/products/lookup")
async def inventory_products_lookup(
    q: str = "",
    barcode: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Resolve SKU/barcode scans for inventory stock ops and counts (no POS permission required)."""
    rows = await product_lookup_svc.lookup_products(
        db, tenant_id=claims["tenant_id"], q=q, barcode=barcode
    )
    return env(rows)


@api.get("/products/import/template")
async def products_import_template(
    claims=Depends(require_permission("inventory", "read")),
):
    text = product_import_svc.template_csv()
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="product_import_template.csv"'},
    )


@api.post("/products/import")
async def products_import(
    file: UploadFile = File(...),
    dry_run: bool = True,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")
    result = await product_import_svc.import_products_csv(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        content=content,
        dry_run=dry_run,
    )
    if not dry_run and result["valid_rows"]:
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="inventory",
            action="product_import",
            entity="product",
            entity_id=None,
            details={
                "created": result["valid_rows"],
                "errors": result["error_rows"],
                "filename": file.filename,
            },
        )
        await db.commit()
    elif not dry_run:
        await db.commit()
    return env(
        result,
        "Dry-run complete" if dry_run else f"Imported {result['valid_rows']} products",
    )


@api.get("/inventory/stock/import/template")
async def stock_import_template(
    claims=Depends(require_permission("inventory", "read")),
):
    text = stock_import_svc.template_csv()
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="stock_import_template.csv"'},
    )


@api.post("/inventory/stock/import")
async def stock_import(
    file: UploadFile = File(...),
    dry_run: bool = True,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")
    result = await stock_import_svc.import_stock_csv(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        content=content,
        dry_run=dry_run,
    )
    if not dry_run and result["valid_rows"]:
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="inventory",
            action="stock_import",
            entity="stock_movement",
            entity_id=None,
            details={
                "applied": result["valid_rows"],
                "errors": result["error_rows"],
                "skipped": result["skipped_rows"],
                "filename": file.filename,
            },
        )
        await db.commit()
    elif not dry_run:
        await db.commit()
    return env(
        result,
        "Dry-run complete" if dry_run else f"Applied stock changes for {result['valid_rows']} rows",
    )


@api.post("/products")
async def add_product(
    payload: ProductCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump()
    category_id, brand_id, unit_id, category_label = await catalog_meta_svc.resolve_product_refs(
        db,
        claims["tenant_id"],
        category_id=data.pop("category_id", None),
        brand_id=data.pop("brand_id", None),
        unit_id=data.pop("unit_id", None),
        category_name=data.get("category"),
    )
    data["category"] = category_label
    data["category_id"] = category_id
    data["brand_id"] = brand_id
    data["unit_id"] = unit_id
    data["barcode"] = await barcode_svc.assert_barcode_available(
        db, tenant_id=claims["tenant_id"], barcode=data.get("barcode")
    )
    product = m.Product(tenant_id=claims["tenant_id"], **data)
    db.add(product)
    await db.flush()
    if float(product.stock_qty or 0) > 0:
        opening = float(product.stock_qty)
        product.stock_qty = 0
        await apply_stock_change(
            db,
            tenant_id=claims["tenant_id"],
            product_id=product.id,
            quantity_delta=opening,
            movement_type="opening_stock",
            user_id=claims["sub"],
            reference_type="product",
            reference_id=product.id,
            notes="Opening stock on product create",
        )
    await db.commit()
    await db.refresh(product)
    return env(catalog_meta_svc.serialize_product(product), "Product created")


@api.get("/products/{product_id}")
async def get_product(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id,
                m.Product.tenant_id == claims["tenant_id"],
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return env(catalog_meta_svc.serialize_product(product))


@api.patch("/products/{product_id}")
async def patch_product(
    product_id: str,
    payload: ProductUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id,
                m.Product.tenant_id == claims["tenant_id"],
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return env(catalog_meta_svc.serialize_product(product), "No changes")

    if any(k in data for k in ("category_id", "brand_id", "unit_id", "category")):
        category_id, brand_id, unit_id, category_label = await catalog_meta_svc.resolve_product_refs(
            db,
            claims["tenant_id"],
            category_id=data.get("category_id", product.category_id),
            brand_id=data.get("brand_id", product.brand_id),
            unit_id=data.get("unit_id", product.unit_id),
            category_name=data.get("category", product.category),
        )
        product.category_id = category_id
        product.brand_id = brand_id
        product.unit_id = unit_id
        product.category = category_label
        data.pop("category_id", None)
        data.pop("brand_id", None)
        data.pop("unit_id", None)
        data.pop("category", None)

    if "sku" in data and data["sku"]:
        sku = str(data["sku"]).strip()
        clash = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == claims["tenant_id"],
                    m.Product.sku == sku,
                    m.Product.id != product.id,
                )
            )
        ).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=409, detail="SKU already exists")
        product.sku = sku
        data.pop("sku")

    for key, value in data.items():
        if key == "name" and value is not None:
            name = str(value).strip()
            if len(name) < 1:
                raise HTTPException(status_code=400, detail="name is required")
            product.name = name
        elif key == "barcode":
            product.barcode = await barcode_svc.assert_barcode_available(
                db,
                tenant_id=claims["tenant_id"],
                barcode=value,
                exclude_product_id=product.id,
            )
        elif key in {"cost_price", "selling_price", "reorder_level"} and value is not None:
            setattr(product, key, float(value))
        elif key == "tax_rate_id":
            product.tax_rate_id = value
        elif key == "tax_exempt" and value is not None:
            product.tax_exempt = bool(value)
        elif key == "tracks_batches" and value is not None:
            product.tracks_batches = bool(value)
        elif key == "is_active" and value is not None:
            product.is_active = bool(value)

    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="product_update",
        entity="product",
        entity_id=product.id,
        details={"sku": product.sku, "fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    await db.commit()
    await db.refresh(product)
    return env(catalog_meta_svc.serialize_product(product), "Product updated")


@api.get("/catalog/categories")
async def catalog_categories(
    tree: bool = False,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    rows = await catalog_meta_svc.list_categories(db, claims["tenant_id"])
    if tree:
        return env(catalog_meta_svc.build_category_tree(rows))
    return env([catalog_meta_svc.serialize_category(r) for r in rows])


@api.post("/catalog/categories")
async def catalog_create_category(
    payload: ProductCategoryCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.create_category(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        parent_id=payload.parent_id,
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_category(row), "Category created")


@api.patch("/catalog/categories/{category_id}")
async def catalog_patch_category(
    category_id: str,
    payload: ProductCategoryUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    clear_parent = "parent_id" in data and data["parent_id"] is None
    row = await catalog_meta_svc.update_category(
        db,
        tenant_id=claims["tenant_id"],
        category_id=category_id,
        code=data.get("code"),
        name=data.get("name"),
        parent_id=data.get("parent_id"),
        is_active=data.get("is_active"),
        clear_parent=clear_parent,
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_category(row), "Category updated")


@api.delete("/catalog/categories/{category_id}")
async def catalog_delete_category(
    category_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.deactivate_category(
        db, tenant_id=claims["tenant_id"], category_id=category_id
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_category(row), "Category deactivated")


@api.get("/catalog/brands")
async def catalog_brands(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await catalog_meta_svc.list_brands(db, claims["tenant_id"])
    return env([catalog_meta_svc.serialize_brand(r) for r in rows])


@api.post("/catalog/brands")
async def catalog_create_brand(
    payload: BrandCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.create_brand(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        description=payload.description,
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_brand(row), "Brand created")


@api.patch("/catalog/brands/{brand_id}")
async def catalog_patch_brand(
    brand_id: str,
    payload: BrandUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    clear_description = "description" in data and data["description"] is None
    row = await catalog_meta_svc.update_brand(
        db,
        tenant_id=claims["tenant_id"],
        brand_id=brand_id,
        code=data.get("code"),
        name=data.get("name"),
        description=data.get("description"),
        is_active=data.get("is_active"),
        clear_description=clear_description,
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_brand(row), "Brand updated")


@api.delete("/catalog/brands/{brand_id}")
async def catalog_delete_brand(
    brand_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.deactivate_brand(
        db, tenant_id=claims["tenant_id"], brand_id=brand_id
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_brand(row), "Brand deactivated")


@api.get("/catalog/units")
async def catalog_units(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    rows = await catalog_meta_svc.list_units(db, claims["tenant_id"])
    return env([catalog_meta_svc.serialize_unit(r) for r in rows])


@api.post("/catalog/units")
async def catalog_create_unit(
    payload: UnitOfMeasureCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.create_unit(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_unit(row), "Unit created")


@api.patch("/catalog/units/{unit_id}")
async def catalog_patch_unit(
    unit_id: str,
    payload: UnitOfMeasureUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    row = await catalog_meta_svc.update_unit(
        db,
        tenant_id=claims["tenant_id"],
        unit_id=unit_id,
        code=data.get("code"),
        name=data.get("name"),
        is_active=data.get("is_active"),
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_unit(row), "Unit updated")


@api.delete("/catalog/units/{unit_id}")
async def catalog_delete_unit(
    unit_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.deactivate_unit(
        db, tenant_id=claims["tenant_id"], unit_id=unit_id
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_unit(row), "Unit deactivated")


@api.post("/products/{product_id}/image")
async def product_image_upload(
    product_id: str,
    file: UploadFile = File(...),
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="product_images",
        upload=file,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    await product_images_svc.add_product_image(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product.id,
        storage_key=stored.key,
        content_type=stored.content_type,
        original_filename=stored.original_filename,
        is_primary=True,
    )
    await db.commit()
    await db.refresh(product)
    return env(catalog_meta_svc.serialize_product(product), "Product image uploaded")


@api.get("/products/{product_id}/image")
async def product_image_get(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id,
                m.Product.tenant_id == claims["tenant_id"],
            )
        )
    ).scalar_one_or_none()
    if not product or not product.image_url:
        raise HTTPException(status_code=404, detail="Product image not found")
    return storage_svc.media_response(product.image_url, tenant_id=claims["tenant_id"])


@api.delete("/products/{product_id}/image")
async def product_image_delete(
    product_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = await product_images_svc.delete_primary_product_image(
        db, tenant_id=claims["tenant_id"], product_id=product_id
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_product(product), "Product image removed")


@api.get("/products/{product_id}/images")
async def product_images_list(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await product_images_svc.list_product_images(
        db, tenant_id=claims["tenant_id"], product_id=product_id
    )
    return env([product_images_svc.serialize_image(r) for r in rows])


@api.post("/products/{product_id}/images")
async def product_images_upload(
    product_id: str,
    file: UploadFile = File(...),
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="product_images",
        upload=file,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    row = await product_images_svc.add_product_image(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        storage_key=stored.key,
        content_type=stored.content_type,
        original_filename=stored.original_filename,
        is_primary=False,
    )
    await db.commit()
    return env(product_images_svc.serialize_image(row), "Product image added")


@api.patch("/products/{product_id}/images/{image_id}")
async def product_images_patch(
    product_id: str,
    image_id: str,
    payload: ProductImagePrimaryUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    if not payload.is_primary:
        raise HTTPException(status_code=400, detail="Only setting primary is supported")
    row = await product_images_svc.set_primary_product_image(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        image_id=image_id,
    )
    await db.commit()
    return env(product_images_svc.serialize_image(row), "Primary image updated")


@api.delete("/products/{product_id}/images/{image_id}")
async def product_images_delete(
    product_id: str,
    image_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    await product_images_svc.delete_product_image(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        image_id=image_id,
    )
    await db.commit()
    return env(None, "Product image removed")


@api.get("/inventory/low-stock")
async def lowstock(claims=Depends(require_permission("inventory", "read")), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == claims["tenant_id"],
                m.Product.stock_qty <= m.Product.reorder_level,
            )
        )
    ).scalars().all()
    return env(rows)


@api.get("/inventory/movements")
async def movements(
    product_id: str | None = None,
    warehouse_id: str | None = None,
    movement_type: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(m.StockMovement).where(m.StockMovement.tenant_id == claims["tenant_id"])
    if product_id:
        stmt = stmt.where(m.StockMovement.product_id == product_id)
    if warehouse_id:
        stmt = stmt.where(m.StockMovement.warehouse_id == warehouse_id)
    if movement_type:
        stmt = stmt.where(m.StockMovement.movement_type == movement_type)
    rows = (
        await db.execute(stmt.order_by(m.StockMovement.created_at.desc()).limit(200))
    ).scalars().all()
    return env(rows)


@api.get("/inventory/stock-counts")
async def list_stock_counts(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await stock_counts_svc.list_counts(db, claims["tenant_id"])
    out = []
    for row in rows:
        data = await stock_counts_svc.serialize_count(db, row)
        data.pop("items", None)
        out.append(data)
    return env(out)


@api.post("/inventory/stock-counts")
async def create_stock_count(
    payload: StockCountCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.create_count(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        warehouse_id=payload.warehouse_id,
        notes=payload.notes,
        product_ids=payload.product_ids,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="stock_count_create",
        entity="stock_count",
        entity_id=count.id,
        details={"warehouse_id": count.warehouse_id, "count_number": count.count_number},
    )
    await db.commit()
    return env(await stock_counts_svc.serialize_count(db, count), "Stock count created")


@api.get("/inventory/stock-counts/{count_id}")
async def get_stock_count(
    count_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.get_count(db, claims["tenant_id"], count_id)
    return env(await stock_counts_svc.serialize_count(db, count))


@api.patch("/inventory/stock-counts/{count_id}/items")
async def patch_stock_count_items(
    count_id: str,
    payload: StockCountItemsUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.update_count_items(
        db,
        tenant_id=claims["tenant_id"],
        count_id=count_id,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await stock_counts_svc.serialize_count(db, count), "Count lines updated")


@api.post("/inventory/stock-counts/{count_id}/complete")
async def complete_stock_count(
    count_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.complete_count(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        count_id=count_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="stock_count_complete",
        entity="stock_count",
        entity_id=count.id,
        details={"count_number": count.count_number, "warehouse_id": count.warehouse_id},
    )
    await db.commit()
    return env(await stock_counts_svc.serialize_count(db, count), "Stock count completed")


@api.post("/inventory/stock-counts/{count_id}/cancel")
async def cancel_stock_count(
    count_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.cancel_count(
        db, tenant_id=claims["tenant_id"], count_id=count_id
    )
    await db.commit()
    return env(await stock_counts_svc.serialize_count(db, count), "Stock count cancelled")


@api.post("/inventory/adjust/{product_id}")
async def adjust(
    product_id: str,
    payload: StockAdjust,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = await apply_stock_change(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        quantity_delta=float(payload.quantity),
        movement_type="adjustment",
        user_id=claims["sub"],
        notes=payload.notes or payload.reason,
        allow_negative=True,
    )
    await db.commit()
    return env({"product_id": product.id, "stock_qty": float(product.stock_qty)})


@api.post("/inventory/stock-in")
async def stock_in(
    payload: StockMove,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    result = await catalog_svc.stock_in_with_batch(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        product_id=payload.product_id,
        quantity=float(payload.quantity),
        notes=payload.notes,
        warehouse_id=payload.warehouse_id,
        variant_id=payload.variant_id,
        batch_number=payload.batch_number,
        manufacturing_date=payload.manufacturing_date,
        expiry_date=payload.expiry_date,
    )
    await db.commit()
    return env(result, "Stock in recorded")


@api.post("/inventory/stock-out")
async def stock_out(
    payload: StockMove,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    result = await catalog_svc.stock_out_with_batch(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        product_id=payload.product_id,
        quantity=float(payload.quantity),
        notes=payload.notes,
        warehouse_id=payload.warehouse_id,
        variant_id=payload.variant_id,
        batch_id=payload.batch_id,
    )
    await db.commit()
    return env(result, "Stock out recorded")


@api.get("/products/{product_id}/variants")
async def list_product_variants(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await catalog_svc.list_variants(db, claims["tenant_id"], product_id)
    return env([catalog_svc.serialize_variant(v) for v in rows])


@api.post("/products/{product_id}/barcode/generate")
async def generate_product_barcode(
    product_id: str,
    format: str = "code128",
    force: bool = False,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = await barcode_svc.assign_product_barcode(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        format=format,
        force=force,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="barcode_generate",
        entity="product",
        entity_id=product.id,
        details={"barcode": product.barcode, "format": format, "force": force},
    )
    await db.commit()
    await db.refresh(product)
    return env(catalog_meta_svc.serialize_product(product), "Barcode assigned")


@api.get("/products/{product_id}/labels")
async def product_barcode_labels(
    product_id: str,
    format: str = "html",
    copies: int = 1,
    include_price: bool = True,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    labels = await barcode_labels_svc.resolve_label_targets(
        db,
        tenant_id=claims["tenant_id"],
        items=[{"product_id": product_id, "copies": copies}],
    )
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    currency = tenant.currency or "GHS"
    if not include_price:
        for label in labels:
            label["price"] = None
    fmt = (format or "html").strip().lower()
    if fmt == "html":
        return HTMLResponse(barcode_labels_svc.build_labels_html(labels, currency=currency))
    if fmt == "png":
        png = barcode_labels_svc.build_labels_sheet_png(labels, currency=currency)
        return Response(
            content=png,
            media_type="image/png",
            headers={"Content-Disposition": 'inline; filename="barcode_labels.png"'},
        )
    if fmt == "pdf":
        pdf = barcode_labels_svc.build_labels_pdf(labels, currency=currency)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="barcode_labels.pdf"'},
        )
    raise HTTPException(status_code=400, detail="format must be html, png, or pdf")


@api.post("/inventory/labels")
async def print_barcode_labels(
    payload: BarcodeLabelPrintRequest,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    labels = await barcode_labels_svc.resolve_label_targets(
        db,
        tenant_id=claims["tenant_id"],
        items=[i.model_dump() for i in payload.items],
    )
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    currency = tenant.currency or "GHS"
    if not payload.include_price:
        for label in labels:
            label["price"] = None
    fmt = (payload.format or "html").strip().lower()
    if fmt == "html":
        return HTMLResponse(barcode_labels_svc.build_labels_html(labels, currency=currency))
    if fmt == "png":
        png = barcode_labels_svc.build_labels_sheet_png(
            labels, currency=currency, cols=payload.columns
        )
        return Response(
            content=png,
            media_type="image/png",
            headers={"Content-Disposition": 'inline; filename="barcode_labels.png"'},
        )
    if fmt == "pdf":
        pdf = barcode_labels_svc.build_labels_pdf(labels, currency=currency)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="barcode_labels.pdf"'},
        )
    raise HTTPException(status_code=400, detail="format must be html, png, or pdf")


@api.post("/products/{product_id}/variants")
async def create_product_variant(
    product_id: str,
    payload: ProductVariantCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump()
    data["barcode"] = await barcode_svc.assert_barcode_available(
        db, tenant_id=claims["tenant_id"], barcode=data.get("barcode")
    )
    variant = await catalog_svc.create_variant(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        **data,
    )
    await db.commit()
    return env(catalog_svc.serialize_variant(variant), "Variant created")


@api.patch("/products/{product_id}/variants/{variant_id}")
async def patch_product_variant(
    product_id: str,
    variant_id: str,
    payload: ProductVariantUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if "barcode" in data and data["barcode"] is not None:
        data["barcode"] = await barcode_svc.assert_barcode_available(
            db,
            tenant_id=claims["tenant_id"],
            barcode=data["barcode"],
            exclude_variant_id=variant_id,
        )
    variant = await catalog_svc.update_variant(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        variant_id=variant_id,
        name=data.get("name"),
        sku=data.get("sku"),
        barcode=data.get("barcode"),
        size=data.get("size"),
        color=data.get("color"),
        flavor=data.get("flavor"),
        cost_price=data.get("cost_price"),
        selling_price=data.get("selling_price"),
        is_active=data.get("is_active"),
        clear_barcode="barcode" in data and data["barcode"] is None,
        clear_size="size" in data and data["size"] is None,
        clear_color="color" in data and data["color"] is None,
        clear_flavor="flavor" in data and data["flavor"] is None,
    )
    await db.commit()
    return env(catalog_svc.serialize_variant(variant), "Variant updated")


@api.post("/products/{product_id}/variants/{variant_id}/barcode/generate")
async def generate_variant_barcode(
    product_id: str,
    variant_id: str,
    format: str = "code128",
    force: bool = False,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    variant = await barcode_svc.assign_variant_barcode(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        variant_id=variant_id,
        format=format,
        force=force,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="barcode_generate",
        entity="product_variant",
        entity_id=variant.id,
        details={"barcode": variant.barcode, "format": format, "force": force},
    )
    await db.commit()
    await db.refresh(variant)
    return env(catalog_svc.serialize_variant(variant), "Barcode assigned")


@api.delete("/products/{product_id}/variants/{variant_id}")
async def delete_product_variant(
    product_id: str,
    variant_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    variant = await catalog_svc.deactivate_variant(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        variant_id=variant_id,
    )
    await db.commit()
    return env(catalog_svc.serialize_variant(variant), "Variant deactivated")


@api.get("/products/{product_id}/batches")
async def list_product_batches(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    rows = await catalog_svc.list_batches(db, claims["tenant_id"], product_id=product_id)
    return env([catalog_svc.serialize_batch(b) for b in rows])


@api.get("/inventory/batches/expiring")
async def inventory_batches_expiring(
    days: int = 30,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await catalog_svc.list_expiring_batches(
        db, claims["tenant_id"], within_days=days
    )
    return env(
        {
            "within_days": days,
            "count": len(rows),
            "batches": [catalog_svc.serialize_batch(b) for b in rows],
        }
    )


async def party_list(kind: str, claims: dict, db: AsyncSession):
    rows = (
        await db.execute(
            select(m.Party).where(m.Party.tenant_id == claims["tenant_id"], m.Party.kind == kind)
        )
    ).scalars().all()
    return env(rows)


@api.get("/customers")
async def customers(claims=Depends(require_permission("sales", "read")), db: AsyncSession = Depends(get_db)):
    return await party_list("customer", claims, db)


@api.post("/customers")
async def add_customer(
    payload: PartyCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = m.Party(tenant_id=claims["tenant_id"], kind="customer", **payload.model_dump())
    db.add(party)
    await db.commit()
    return env({"id": party.id})


@api.get("/suppliers")
async def suppliers(claims=Depends(require_permission("purchasing", "read")), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(m.Party)
            .where(m.Party.tenant_id == claims["tenant_id"], m.Party.kind == "supplier")
            .order_by(m.Party.name)
        )
    ).scalars().all()
    out = []
    for row in rows:
        contacts = await suppliers_svc.list_contacts(db, claims["tenant_id"], row.id)
        out.append(suppliers_svc.serialize_supplier(row, contacts))
    return env(out)


@api.post("/suppliers")
async def add_supplier(
    payload: SupplierCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump()
    contacts = data.pop("contacts", None) or []
    party = await suppliers_svc.create_supplier(
        db,
        tenant_id=claims["tenant_id"],
        name=data["name"],
        code=data.get("code"),
        party_type=data.get("party_type"),
        category=data.get("category"),
        email=data.get("email"),
        phone=data.get("phone"),
        address=data.get("address"),
        notes=data.get("notes"),
        payment_terms_days=int(data.get("payment_terms_days") or 0),
        credit_limit=float(data.get("credit_limit") or 0),
        contacts=contacts,
    )
    await db.commit()
    contacts_rows = await suppliers_svc.list_contacts(db, claims["tenant_id"], party.id)
    return env(suppliers_svc.serialize_supplier(party, contacts_rows), "Supplier created")


@api.get("/suppliers/{supplier_id}")
async def get_supplier(
    supplier_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    party = await suppliers_svc.get_supplier(db, claims["tenant_id"], supplier_id)
    contacts = await suppliers_svc.list_contacts(db, claims["tenant_id"], party.id)
    return env(suppliers_svc.serialize_supplier(party, contacts))


@api.patch("/suppliers/{supplier_id}")
async def patch_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = await suppliers_svc.update_supplier(
        db,
        tenant_id=claims["tenant_id"],
        supplier_id=supplier_id,
        fields=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    contacts = await suppliers_svc.list_contacts(db, claims["tenant_id"], party.id)
    return env(suppliers_svc.serialize_supplier(party, contacts), "Supplier updated")


@api.delete("/suppliers/{supplier_id}")
async def delete_supplier(
    supplier_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = await suppliers_svc.deactivate_supplier(
        db, tenant_id=claims["tenant_id"], supplier_id=supplier_id
    )
    await db.commit()
    contacts = await suppliers_svc.list_contacts(db, claims["tenant_id"], party.id)
    return env(suppliers_svc.serialize_supplier(party, contacts), "Supplier deactivated")


@api.post("/suppliers/{supplier_id}/contacts")
async def add_supplier_contact(
    supplier_id: str,
    payload: SupplierContactCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    contact = await suppliers_svc.add_contact(
        db,
        tenant_id=claims["tenant_id"],
        supplier_id=supplier_id,
        **payload.model_dump(),
    )
    await db.commit()
    return env(suppliers_svc.serialize_contact(contact), "Contact added")


@api.delete("/suppliers/{supplier_id}/contacts/{contact_id}")
async def delete_supplier_contact(
    supplier_id: str,
    contact_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    await suppliers_svc.delete_contact(
        db,
        tenant_id=claims["tenant_id"],
        supplier_id=supplier_id,
        contact_id=contact_id,
    )
    await db.commit()
    return env(None, "Contact removed")


@api.get("/suppliers/{supplier_id}/history")
async def supplier_history(
    supplier_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    data = await suppliers_svc.supplier_history(
        db, tenant_id=claims["tenant_id"], supplier_id=supplier_id
    )
    return env(data)


async def tx_list(kind: str, claims: dict, db: AsyncSession):
    rows = (
        await db.execute(
            select(m.Transaction)
            .where(m.Transaction.tenant_id == claims["tenant_id"], m.Transaction.tx_type == kind)
            .order_by(m.Transaction.created_at.desc())
        )
    ).scalars().all()
    return env(rows)


async def tx_add(kind: str, payload: TransactionCreate, claims: dict, db: AsyncSession):
    items = [i.model_dump() for i in payload.items] or list(payload.payload.get("items") or [])
    if kind in {"sale", "pos_sale", "purchase"} and not items:
        raise HTTPException(
            status_code=400,
            detail="items are required for sale/purchase/pos so stock can be updated correctly",
        )

    if kind in {"sale", "pos_sale"} and payload.party_id:
        party = (
            await db.execute(
                select(m.Party).where(
                    m.Party.id == payload.party_id,
                    m.Party.tenant_id == claims["tenant_id"],
                    m.Party.kind == "customer",
                )
            )
        ).scalar_one_or_none()
        if party and float(party.credit_limit or 0) > 0:
            projected = float(party.balance or 0) + float(payload.total or 0)
            if projected > float(party.credit_limit):
                raise HTTPException(status_code=409, detail="CREDIT_LIMIT_EXCEEDED")

    ref = f"{kind.upper()}-{datetime.utcnow():%Y%m%d%H%M%S%f}"
    body = payload.model_dump()
    body.pop("items", None)
    body["payload"] = {**(body.get("payload") or {}), "items": items}
    tx = m.Transaction(tenant_id=claims["tenant_id"], tx_type=kind, reference=ref, **body)
    db.add(tx)
    await db.flush()

    outbound = kind in {"sale", "pos_sale"}
    await apply_line_items_stock(
        db,
        tenant_id=claims["tenant_id"],
        items=items,
        movement_type="stock_out" if outbound else "stock_in",
        user_id=claims["sub"],
        reference_type=kind,
        reference_id=tx.id,
        outbound=outbound,
    )

    if payload.party_id and kind in {"sale", "pos_sale"}:
        party = await db.get(m.Party, payload.party_id)
        if party and party.tenant_id == claims["tenant_id"]:
            party.balance = float(party.balance or 0) + float(payload.total or 0)
    if payload.party_id and kind == "purchase":
        party = await db.get(m.Party, payload.party_id)
        if party and party.tenant_id == claims["tenant_id"]:
            party.balance = float(party.balance or 0) + float(payload.total or 0)

    await db.commit()
    return env({"id": tx.id, "reference": ref})


@api.get("/sales")
async def sales(claims=Depends(require_permission("sales", "read")), db: AsyncSession = Depends(get_db)):
    return await tx_list("sale", claims, db)


@api.post("/sales")
async def sale(
    payload: TransactionCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    return await tx_add("sale", payload, claims, db)


@api.get("/sales/invoices")
async def list_sales_invoices(
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(m.SalesInvoice)
        .where(m.SalesInvoice.tenant_id == claims["tenant_id"])
        .order_by(m.SalesInvoice.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesInvoice, claims)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await sales_svc.serialize_invoice(db, inv) for inv in rows])


@api.post("/sales/invoices")
async def create_sales_invoice(
    payload: SalesInvoiceCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    invoice = await sales_svc.create_sales_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        customer_id=payload.customer_id,
        discount_amount=payload.discount_amount,
        notes=payload.notes,
        store_id=payload.store_id,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await sales_svc.serialize_invoice(db, invoice), "Sales invoice created as draft")


@api.get("/sales/invoices/{invoice_id}")
async def get_sales_invoice(
    invoice_id: str,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    invoice = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, invoice.created_by)
    return env(await sales_svc.serialize_invoice(db, invoice))


@api.post("/sales/invoices/{invoice_id}/post")
async def post_sales_invoice(
    invoice_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    invoice = await sales_svc.post_sales_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], invoice_id=invoice_id
    )
    await db.commit()
    return env(await sales_svc.serialize_invoice(db, invoice), "Invoice posted; stock and AR updated")


@api.post("/sales/invoices/{invoice_id}/cancel")
async def cancel_sales_invoice(
    invoice_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    invoice = await sales_svc.cancel_sales_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], invoice_id=invoice_id
    )
    await db.commit()
    return env(await sales_svc.serialize_invoice(db, invoice), "Draft invoice cancelled")


@api.get("/sales/quotations")
async def list_quotations(
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.SalesQuotation)
            .where(m.SalesQuotation.tenant_id == claims["tenant_id"])
            .order_by(m.SalesQuotation.created_at.desc())
        )
    ).scalars().all()
    return env([await sales_docs_svc.serialize_quotation(db, q) for q in rows])


@api.post("/sales/quotations")
async def create_quotation(
    payload: SalesQuotationCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    quote = await sales_docs_svc.create_quotation(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        customer_id=payload.customer_id,
        discount_amount=payload.discount_amount,
        notes=payload.notes,
        valid_days=payload.valid_days,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_quotation(db, quote), "Quotation created")


@api.get("/sales/quotations/{quotation_id}")
async def get_quotation(
    quotation_id: str,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    quote = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    return env(await sales_docs_svc.serialize_quotation(db, quote))


@api.post("/sales/quotations/{quotation_id}/send")
async def send_quotation(
    quotation_id: str,
    to: str | None = None,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    quote, delivery = await sales_docs_svc.send_quotation(
        db, claims["tenant_id"], quotation_id, to=to
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="sales",
        action="quotation_email",
        entity="sales_quotation",
        entity_id=quote.id,
        details=delivery,
    )
    await db.commit()
    data = await sales_docs_svc.serialize_quotation(db, quote)
    data["delivery"] = delivery
    return env(data, f"Quotation emailed to {delivery['to']} ({delivery['mode']})")


@api.post("/sales/quotations/{quotation_id}/accept")
async def accept_quotation(
    quotation_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    quote = await sales_docs_svc.accept_quotation(db, claims["tenant_id"], quotation_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_quotation(db, quote), "Quotation accepted")


@api.post("/sales/quotations/{quotation_id}/reject")
async def reject_quotation(
    quotation_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    quote = await sales_docs_svc.reject_quotation(db, claims["tenant_id"], quotation_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_quotation(db, quote), "Quotation rejected")


@api.post("/sales/quotations/{quotation_id}/convert-order")
async def convert_quotation_order(
    quotation_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    order = await sales_docs_svc.convert_quotation_to_order(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], quotation_id=quotation_id
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Converted to sales order")


@api.post("/sales/quotations/{quotation_id}/convert-invoice")
async def convert_quotation_invoice(
    quotation_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    invoice = await sales_docs_svc.convert_quotation_to_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], quotation_id=quotation_id
    )
    await db.commit()
    return env(await sales_svc.serialize_invoice(db, invoice), "Converted to draft invoice")


@api.get("/sales/orders")
async def list_sales_orders(
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.SalesOrder)
            .where(m.SalesOrder.tenant_id == claims["tenant_id"])
            .order_by(m.SalesOrder.created_at.desc())
        )
    ).scalars().all()
    return env([await sales_docs_svc.serialize_order(db, o) for o in rows])


@api.post("/sales/orders")
async def create_sales_order(
    payload: SalesOrderCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    order = await sales_docs_svc.create_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        customer_id=payload.customer_id,
        quotation_id=payload.quotation_id,
        discount_amount=payload.discount_amount,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Sales order created")


@api.get("/sales/orders/{order_id}")
async def get_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    order = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    return env(await sales_docs_svc.serialize_order(db, order))


@api.post("/sales/orders/{order_id}/confirm")
async def confirm_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    order = await sales_docs_svc.confirm_order(db, claims["tenant_id"], order_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order confirmed")


@api.post("/sales/orders/{order_id}/cancel")
async def cancel_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    order = await sales_docs_svc.cancel_order(db, claims["tenant_id"], order_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order cancelled")


@api.post("/sales/orders/{order_id}/convert-invoice")
async def convert_order_invoice(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    invoice = await sales_docs_svc.convert_order_to_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], order_id=order_id
    )
    await db.commit()
    return env(await sales_svc.serialize_invoice(db, invoice), "Converted to draft invoice")


@api.get("/sales/returns")
async def list_sales_returns(
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.SalesReturn)
            .where(m.SalesReturn.tenant_id == claims["tenant_id"])
            .order_by(m.SalesReturn.created_at.desc())
        )
    ).scalars().all()
    return env([await sales_docs_svc.serialize_return(db, r) for r in rows])


@api.post("/sales/returns")
async def create_sales_return(
    payload: SalesReturnCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    ret = await sales_docs_svc.create_return(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        sales_invoice_id=payload.sales_invoice_id,
        reason=payload.reason,
        restock=payload.restock,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_return(db, ret), "Sales return created as draft")


@api.get("/sales/returns/{return_id}")
async def get_sales_return(
    return_id: str,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    ret = await sales_docs_svc.get_return(db, claims["tenant_id"], return_id)
    return env(await sales_docs_svc.serialize_return(db, ret))


@api.post("/sales/returns/{return_id}/post")
async def post_sales_return(
    return_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    ret = await sales_docs_svc.post_return(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], return_id=return_id
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_return(db, ret), "Return posted; stock/AR/journal updated")


@api.post("/sales/payments")
async def record_sales_payment(
    payload: CustomerPaymentCreate,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    from app.rbac import has_permission

    role = claims.get("role", "")
    perms = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    allowed = has_permission(role, "credit", "write", overrides=perms) or has_permission(
        role, "sales", "write", overrides=perms
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Missing permission: sales:write or credit:write")
    payment = await sales_svc.record_customer_payment(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        customer_id=payload.customer_id,
        amount=payload.amount,
        sales_invoice_id=payload.sales_invoice_id,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        cheque_number=payload.cheque_number,
        bank_name=payload.bank_name,
        cheque_date=payload.cheque_date,
        apply_early_discount=payload.apply_early_discount,
        liquid_account_id=payload.liquid_account_id,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
    )
    await db.commit()
    return env(
        {
            "id": payment.id,
            "payment_number": payment.payment_number,
            "amount": float(payment.amount),
            "sales_invoice_id": payment.sales_invoice_id,
            "currency": getattr(payment, "currency", None) or "",
            "exchange_rate": float(getattr(payment, "exchange_rate", None) or 1),
            "fx_gain_loss": float(getattr(payment, "fx_gain_loss", 0) or 0),
        },
        "Payment recorded",
    )


@api.get("/purchases")
async def purchases(claims=Depends(require_permission("purchasing", "read")), db: AsyncSession = Depends(get_db)):
    return await tx_list("purchase", claims, db)


@api.post("/purchases")
async def purchase(
    payload: TransactionCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    return await tx_add("purchase", payload, claims, db)


@api.get("/purchasing/requests")
async def list_purchase_requests(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.PurchaseRequest)
            .where(m.PurchaseRequest.tenant_id == claims["tenant_id"])
            .order_by(m.PurchaseRequest.created_at.desc())
        )
    ).scalars().all()
    return env([await purchasing_svc.serialize_pr(db, pr) for pr in rows])


@api.get("/purchasing/settings")
async def get_purchasing_settings(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await purchasing_svc.get_pr_approval_settings(db, claims["tenant_id"]))


@api.patch("/purchasing/settings")
async def patch_purchasing_settings(
    payload: PurchaseRequestApprovalSettingsUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    # Company admins configure matrix; store managers have purchasing write — restrict to admin roles.
    if claims.get("role") not in {"company_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only company admins can update purchasing settings")
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    data = await purchasing_svc.update_pr_approval_settings(
        db,
        tenant,
        levels=[lvl.model_dump(exclude_none=True) for lvl in payload.levels],
    )
    await db.commit()
    return env(data, "Purchasing approval settings updated")


@api.post("/purchasing/requests")
async def create_purchase_request(
    payload: PurchaseRequestCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    pr = await purchasing_svc.create_purchase_request(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        supplier_id=payload.supplier_id,
        warehouse_id=payload.warehouse_id,
        department=payload.department,
        required_date=payload.required_date,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await purchasing_svc.serialize_pr(db, pr), "Purchase request created")


@api.get("/purchasing/requests/{request_id}")
async def get_purchase_request(
    request_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    pr = await purchasing_svc.get_purchase_request(db, claims["tenant_id"], request_id)
    return env(await purchasing_svc.serialize_pr(db, pr))


@api.post("/purchasing/requests/{request_id}/submit")
async def submit_purchase_request(
    request_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    pr = await purchasing_svc.submit_purchase_request(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], request_id=request_id
    )
    await db.commit()
    data = await purchasing_svc.serialize_pr(db, pr)
    msg = (
        "Purchase request auto-approved"
        if pr.status == "approved"
        else "Purchase request submitted"
    )
    return env(data, msg)


@api.post("/purchasing/requests/{request_id}/approve")
async def approve_purchase_request(
    request_id: str,
    payload: PurchaseRequestDecision = PurchaseRequestDecision(),
    claims=Depends(require_permission("purchasing", "approve")),
    db: AsyncSession = Depends(get_db),
):
    pr = await purchasing_svc.approve_purchase_request(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        request_id=request_id,
        comment=payload.comment,
        actor_role=claims.get("role"),
    )
    await db.commit()
    data = await purchasing_svc.serialize_pr(db, pr)
    msg = (
        "Purchase request approved"
        if pr.status == "approved"
        else f"Level {int(pr.approval_step) - 1} approved; awaiting next level"
    )
    return env(data, msg)


@api.post("/purchasing/requests/{request_id}/reject")
async def reject_purchase_request(
    request_id: str,
    payload: PurchaseRequestReject = PurchaseRequestReject(),
    claims=Depends(require_permission("purchasing", "approve")),
    db: AsyncSession = Depends(get_db),
):
    pr = await purchasing_svc.reject_purchase_request(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        request_id=request_id,
        reason=payload.reason,
        actor_role=claims.get("role"),
    )
    await db.commit()
    return env(await purchasing_svc.serialize_pr(db, pr), "Purchase request rejected")


@api.post("/purchasing/requests/{request_id}/cancel")
async def cancel_purchase_request(
    request_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    pr = await purchasing_svc.cancel_purchase_request(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], request_id=request_id
    )
    await db.commit()
    return env(await purchasing_svc.serialize_pr(db, pr), "Purchase request cancelled")


@api.post("/purchasing/requests/{request_id}/convert")
async def convert_purchase_request(
    request_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    pr, po = await purchasing_svc.convert_purchase_request_to_po(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], request_id=request_id
    )
    await db.commit()
    return env(
        {
            "request": await purchasing_svc.serialize_pr(db, pr),
            "purchase_order": await purchasing_svc.serialize_po(db, po),
        },
        "Purchase request converted to PO",
    )


@api.get("/purchasing/orders")
async def list_purchase_orders(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.PurchaseOrder)
            .where(m.PurchaseOrder.tenant_id == claims["tenant_id"])
            .order_by(m.PurchaseOrder.created_at.desc())
        )
    ).scalars().all()
    return env([await purchasing_svc.serialize_po(db, po) for po in rows])


@api.post("/purchasing/orders")
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    po = await purchasing_svc.create_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        supplier_id=payload.supplier_id,
        warehouse_id=payload.warehouse_id,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await purchasing_svc.serialize_po(db, po), "Purchase order created")


@api.get("/purchasing/orders/{po_id}")
async def get_purchase_order(
    po_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    po = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    return env(await purchasing_svc.serialize_po(db, po))


@api.patch("/purchasing/orders/{po_id}")
async def patch_purchase_order(
    po_id: str,
    payload: PurchaseOrderUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    po = await purchasing_svc.update_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        items=[i for i in (data.get("items") or [])] if "items" in data else None,
        warehouse_id=data.get("warehouse_id") if "warehouse_id" in data else None,
        notes=data.get("notes") if "notes" in data else None,
        reason=data.get("reason"),
        track_amendment=False if data.get("reason") is None else None,
    )
    await db.commit()
    return env(await purchasing_svc.serialize_po(db, po), "Purchase order updated")


@api.post("/purchasing/orders/{po_id}/amend")
async def amend_purchase_order(
    po_id: str,
    payload: PurchaseOrderAmend,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    po = await purchasing_svc.amend_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        reason=payload.reason,
        items=data.get("items"),
        warehouse_id=data.get("warehouse_id") if "warehouse_id" in data else None,
        notes=data.get("notes") if "notes" in data else None,
    )
    await db.commit()
    return env(await purchasing_svc.serialize_po(db, po), f"Purchase order amended to revision {po.revision}")


@api.get("/purchasing/orders/{po_id}/amendments")
async def list_purchase_order_amendments(
    po_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    rows = await purchasing_svc.list_po_amendments(db, claims["tenant_id"], po_id)
    return env([purchasing_svc.serialize_po_amendment(r) for r in rows])


@api.post("/purchasing/orders/{po_id}/send")
async def send_purchase_order(
    po_id: str,
    email: bool | None = None,
    to: str | None = None,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    po, delivery = await purchasing_svc.send_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        email=email,
        to=to,
    )
    await db.commit()
    data = await purchasing_svc.serialize_po(db, po)
    if delivery:
        data["delivery"] = delivery
    msg = "Purchase order sent"
    if delivery and delivery.get("sent"):
        msg = f"Purchase order sent and emailed to {delivery['to']}"
    return env(data, msg)


@api.get("/purchasing/orders/{po_id}/print")
async def print_purchase_order(
    po_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    po = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    supplier = await purchasing_svc.get_supplier(db, claims["tenant_id"], po.supplier_id)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    data = await purchasing_svc.serialize_po(db, po)
    text = purchasing_svc.render_po_text(
        data,
        supplier_name=supplier.name,
        company_name=tenant.company_name,
    )
    return env({"po": data, "text": text, "supplier_name": supplier.name})


@api.post("/purchasing/orders/{po_id}/cancel")
async def cancel_purchase_order(
    po_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    po = await purchasing_svc.cancel_purchase_order(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], po_id=po_id
    )
    await db.commit()
    return env(await purchasing_svc.serialize_po(db, po), "Purchase order cancelled")


@api.get("/purchasing/grn")
async def list_grns(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.GoodsReceipt)
            .where(m.GoodsReceipt.tenant_id == claims["tenant_id"])
            .order_by(m.GoodsReceipt.created_at.desc())
        )
    ).scalars().all()
    return env([await purchasing_svc.serialize_grn(db, g) for g in rows])


@api.post("/purchasing/grn")
async def create_grn(
    payload: GrnCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    grn = await purchasing_svc.create_grn(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        purchase_order_id=payload.purchase_order_id,
        warehouse_id=payload.warehouse_id,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await purchasing_svc.serialize_grn(db, grn), "GRN posted and stock updated")


@api.get("/purchasing/grn/{grn_id}")
async def get_grn(
    grn_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    grn = await purchasing_svc.get_grn(db, claims["tenant_id"], grn_id)
    return env(await purchasing_svc.serialize_grn(db, grn))


@api.get("/purchasing/returns")
async def list_purchase_returns(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.PurchaseReturn)
            .where(m.PurchaseReturn.tenant_id == claims["tenant_id"])
            .order_by(m.PurchaseReturn.created_at.desc())
        )
    ).scalars().all()
    return env([await purchasing_svc.serialize_purchase_return(db, r) for r in rows])


@api.post("/purchasing/returns")
async def create_purchase_return(
    payload: PurchaseReturnCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    ret = await purchasing_svc.create_purchase_return(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        goods_receipt_id=payload.goods_receipt_id,
        reason=payload.reason,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_return(db, ret), "Purchase return created as draft")


@api.get("/purchasing/returns/{return_id}")
async def get_purchase_return(
    return_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    ret = await purchasing_svc.get_purchase_return(db, claims["tenant_id"], return_id)
    return env(await purchasing_svc.serialize_purchase_return(db, ret))


@api.post("/purchasing/returns/{return_id}/post")
async def post_purchase_return(
    return_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    ret = await purchasing_svc.post_purchase_return(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], return_id=return_id
    )
    await db.commit()
    return env(
        await purchasing_svc.serialize_purchase_return(db, ret),
        "Return posted; stock/AP/journal updated",
    )


@api.get("/purchasing/invoices")
async def list_purchase_invoices(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.PurchaseInvoice)
            .where(m.PurchaseInvoice.tenant_id == claims["tenant_id"])
            .order_by(m.PurchaseInvoice.created_at.desc())
        )
    ).scalars().all()
    return env([await purchasing_svc.serialize_purchase_invoice(db, r) for r in rows])


@api.post("/purchasing/invoices")
async def create_purchase_invoice(
    payload: PurchaseInvoiceCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.create_purchase_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        supplier_id=payload.supplier_id,
        goods_receipt_id=payload.goods_receipt_id,
        purchase_order_id=payload.purchase_order_id,
        supplier_invoice_number=payload.supplier_invoice_number,
        discount_amount=payload.discount_amount,
        attachment_url=payload.attachment_url,
        notes=payload.notes,
        is_reverse_charge=bool(payload.is_reverse_charge),
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        items=[i.model_dump() for i in payload.items] if payload.items else None,
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Purchase invoice drafted")


@api.get("/purchasing/invoices/{invoice_id}")
async def get_purchase_invoice(
    invoice_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv))


@api.patch("/purchasing/invoices/{invoice_id}")
async def patch_purchase_invoice(
    invoice_id: str,
    payload: PurchaseInvoiceUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import purchase_ocr as purchase_ocr_svc

    inv = await purchase_ocr_svc.update_purchase_invoice_draft(
        db,
        tenant_id=claims["tenant_id"],
        invoice_id=invoice_id,
        supplier_invoice_number=payload.supplier_invoice_number,
        notes=payload.notes,
        invoice_date=payload.invoice_date,
        due_date=payload.due_date,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="purchase_invoice_update",
        entity="purchase_invoice",
        entity_id=inv.id,
        details={"invoice_number": inv.invoice_number},
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Purchase invoice updated")


@api.post("/purchasing/invoices/{invoice_id}/ocr-suggest")
async def purchase_invoice_ocr_suggest(
    invoice_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import purchase_ocr as purchase_ocr_svc

    result = await purchase_ocr_svc.suggest_for_purchase_invoice(
        db, tenant_id=claims["tenant_id"], invoice_id=invoice_id
    )
    return env(result, "OCR suggestions ready — review before applying")


@api.post("/purchasing/invoices/{invoice_id}/approve")
async def approve_purchase_invoice(
    invoice_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.approve_purchase_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], invoice_id=invoice_id
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Purchase invoice approved")


@api.post("/purchasing/invoices/{invoice_id}/cancel")
async def cancel_purchase_invoice(
    invoice_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.cancel_purchase_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], invoice_id=invoice_id
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Purchase invoice cancelled")


@api.post("/purchasing/invoices/{invoice_id}/attachment")
async def upload_purchase_invoice_attachment(
    invoice_id: str,
    file: UploadFile = File(...),
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="purchase_invoices",
        upload=file,
        allowed_types=storage_svc.ATTACHMENT_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_ATTACHMENT_BYTES),
    )
    if inv.attachment_url:
        storage_svc.delete_key(inv.attachment_url, tenant_id=claims["tenant_id"])
    inv.attachment_url = stored.key
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="invoice_attachment_upload",
        entity="purchase_invoice",
        entity_id=inv.id,
        details={"key": stored.key, "size": stored.size, "content_type": stored.content_type},
    )
    await db.commit()
    data = await purchasing_svc.serialize_purchase_invoice(db, inv)
    data["uploaded"] = {
        "key": stored.key,
        "size": stored.size,
        "content_type": stored.content_type,
        "filename": stored.original_filename,
    }
    return env(data, "Attachment uploaded")


@api.get("/purchasing/invoices/{invoice_id}/attachment")
async def download_purchase_invoice_attachment(
    invoice_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    if not inv.attachment_url:
        raise HTTPException(status_code=404, detail="No attachment uploaded")
    # External URLs (legacy client-supplied) are not served from local media
    if "://" in inv.attachment_url:
        raise HTTPException(
            status_code=400,
            detail="Attachment is an external URL; open attachment_url directly",
        )
    return storage_svc.media_response(
        inv.attachment_url, tenant_id=claims["tenant_id"], as_attachment=True
    )


@api.delete("/purchasing/invoices/{invoice_id}/attachment")
async def delete_purchase_invoice_attachment(
    invoice_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    if not inv.attachment_url:
        raise HTTPException(status_code=404, detail="No attachment uploaded")
    storage_svc.delete_key(inv.attachment_url, tenant_id=claims["tenant_id"])
    inv.attachment_url = None
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="invoice_attachment_delete",
        entity="purchase_invoice",
        entity_id=inv.id,
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Attachment removed")


@api.post("/pos/sessions/open")
async def pos_open_session(
    payload: PosSessionOpen,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    session = await pos_svc.open_session(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        store_id=payload.store_id,
        opening_cash=payload.opening_cash,
    )
    await db.commit()
    return env(await pos_svc.serialize_session(session), "POS shift opened")


@api.get("/pos/sessions/current")
async def pos_current_session(
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    session = await pos_svc.get_open_session_for_user(db, claims["tenant_id"], claims["sub"])
    if not session:
        return env(None, "No open POS shift")
    return env(await pos_svc.serialize_session(session))


@api.get("/pos/sessions")
async def pos_list_sessions(
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.PosSession)
            .where(m.PosSession.tenant_id == claims["tenant_id"])
            .order_by(m.PosSession.opened_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return env([await pos_svc.serialize_session(s) for s in rows])


@api.post("/pos/sessions/{session_id}/close")
async def pos_close_session(
    session_id: str,
    payload: PosSessionClose,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    session = await pos_svc.close_session(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        session_id=session_id,
        actual_cash=payload.actual_cash,
        notes=payload.notes,
    )
    await db.commit()
    return env(await pos_svc.serialize_session(session), "POS shift closed")


@api.get("/pos/sessions/{session_id}/drawer")
async def pos_session_drawer(
    session_id: str,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    session = await pos_svc.get_session(db, claims["tenant_id"], session_id)
    summary = await pos_svc.drawer_summary(session)
    cfg = await cash_drawer_svc.resolve_config(
        db, tenant_id=claims["tenant_id"], store_id=session.store_id
    )
    return env({**summary, "hardware": cfg, "kick_base64": cash_drawer_svc.kick_base64()})


@api.post("/pos/sessions/{session_id}/drawer/open")
async def pos_open_cash_drawer(
    session_id: str,
    payload: PosDrawerOpen,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    session = await pos_svc.get_session(db, claims["tenant_id"], session_id)
    if session.status != "open":
        raise HTTPException(status_code=400, detail="POS session is not open")
    if session.user_id != claims["sub"] and claims.get("role") not in {
        "company_admin",
        "super_admin",
        "store_manager",
    }:
        raise HTTPException(status_code=403, detail="Not your POS session")
    result = await cash_drawer_svc.open_drawer(
        db,
        tenant_id=claims["tenant_id"],
        store_id=session.store_id,
        reason=payload.reason or "manual",
        user_id=claims.get("sub"),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="pos",
        action="drawer_open",
        entity="pos_session",
        entity_id=session.id,
        details={"reason": payload.reason, "result": result},
    )
    await db.commit()
    return env(result, result.get("message") or "Drawer command issued")


@api.get("/pos/sessions/{session_id}/report")
async def pos_session_report(
    session_id: str,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    session = await pos_svc.get_session(db, claims["tenant_id"], session_id)
    return env(await pos_svc.shift_report(db, session))


@api.post("/pos/sales")
async def pos_sale(
    payload: PosSaleCreate,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    session = await pos_svc.require_open_session(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        session_id=payload.session_id,
    )
    items = [i.model_dump() for i in payload.items]
    payment_method = pos_svc.normalize_payment_method(payload.payment_method)
    from app.tax import resolve_product_tax
    from app.catalog import resolve_sale_line

    subtotal = 0.0
    tax_total = 0.0
    priced_items = []
    for item in items:
        product, variant, unit_price = await resolve_sale_line(db, claims["tenant_id"], item)
        spec = await resolve_product_tax(db, claims["tenant_id"], product)
        line_sub, line_tax, line_gross = spec.compute_amounts(
            float(item["quantity"]) * float(unit_price)
        )
        subtotal += line_sub
        if not spec.is_reverse_charge:
            tax_total += line_tax
        priced_items.append(
            {
                **item,
                "variant_id": variant.id if variant else item.get("variant_id"),
                "name": variant.name if variant else product.name,
                "sku": variant.sku if variant else product.sku,
                "unit_price": unit_price,
                "tax_rate": spec.rate_pct,
                "line_subtotal": line_sub,
                "line_tax": 0.0 if spec.is_reverse_charge else line_tax,
                "line_total": line_gross,
                "is_reverse_charge": spec.is_reverse_charge,
            }
        )
    total = round(subtotal + tax_total, 2)

    if payload.party_id:
        party = (
            await db.execute(
                select(m.Party).where(
                    m.Party.id == payload.party_id,
                    m.Party.tenant_id == claims["tenant_id"],
                    m.Party.kind == "customer",
                )
            )
        ).scalar_one_or_none()
        if party and float(party.credit_limit or 0) > 0:
            projected = float(party.balance or 0) + float(total)
            if projected > float(party.credit_limit):
                raise HTTPException(status_code=409, detail="CREDIT_LIMIT_EXCEEDED")

    ref = f"POS_SALE-{datetime.utcnow():%Y%m%d%H%M%S%f}"
    body = payload.model_dump()
    body.pop("items", None)
    body.pop("session_id", None)
    body.pop("payment_method", None)
    body["payload"] = {
        **(body.get("payload") or {}),
        "items": priced_items,
        "payment_method": payment_method,
        "session_id": session.id,
    }
    tx = m.Transaction(
        tenant_id=claims["tenant_id"],
        tx_type="pos_sale",
        reference=ref,
        party_id=payload.party_id,
        session_id=session.id,
        subtotal=round(subtotal, 2),
        tax=round(tax_total, 2),
        total=total,
        status=payload.status,
        payload=body["payload"],
    )
    db.add(tx)
    await db.flush()

    warehouse_id = None
    if session.store_id:
        wh = await stores_svc.warehouse_for_store(db, claims["tenant_id"], session.store_id)
        warehouse_id = wh.id

    await apply_line_items_stock(
        db,
        tenant_id=claims["tenant_id"],
        items=items,
        movement_type="stock_out",
        user_id=claims["sub"],
        reference_type="pos_sale",
        reference_id=tx.id,
        outbound=True,
        warehouse_id=warehouse_id,
    )
    await pos_svc.apply_sale_to_session(session, total=total, payment_method=payment_method)

    if payload.party_id and payment_method == "credit":
        party = await db.get(m.Party, payload.party_id)
        if party and party.tenant_id == claims["tenant_id"]:
            party.balance = float(party.balance or 0) + float(total)

    from app.accounting import post_pos_sale_journal

    await post_pos_sale_journal(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        tx=tx,
        payment_method=payment_method,
    )

    from app import cash_drawer as cash_drawer_svc

    drawer = await cash_drawer_svc.maybe_open_on_cash_sale(
        db,
        tenant_id=claims["tenant_id"],
        store_id=session.store_id,
        payment_method=payment_method,
        sale_id=tx.id,
        user_id=claims.get("sub"),
    )
    await db.commit()
    payload_out = {
        "id": tx.id,
        "reference": ref,
        "session_id": session.id,
        "subtotal": float(tx.subtotal),
        "tax": float(tx.tax),
        "total": float(tx.total),
        "payment_method": payment_method,
    }
    if drawer is not None:
        payload_out["drawer"] = drawer
    return env(payload_out, "POS sale recorded")


@api.get("/pos/products/search")
async def pos_search(
    q: str = "",
    barcode: str | None = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    out = await product_lookup_svc.lookup_products(
        db, tenant_id=claims["tenant_id"], q=q, barcode=barcode
    )
    return env(out)


@api.get("/pos/sales/{sale_id}/receipt")
async def pos_receipt(
    sale_id: str,
    format: str = "json",
    paper: str = "80mm",
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import receipts as receipts_svc

    receipt = await receipts_svc.build_sale_receipt(
        db,
        tenant_id=claims["tenant_id"],
        sale_id=sale_id,
        user_id=claims.get("sub"),
    )
    fmt = (format or "json").lower()
    paper = paper if paper in {"58mm", "80mm"} else "80mm"
    if fmt == "json":
        receipt["paper"] = paper
        receipt["text"] = receipts_svc.render_thermal_text(receipt, paper=paper)
        from app import cash_drawer as cash_drawer_svc

        receipt["drawer_kick_base64"] = cash_drawer_svc.kick_base64()
        receipt["drawer_kick_hex"] = cash_drawer_svc.kick_hex()
        return env(receipt)
    if fmt == "text":
        text = receipts_svc.render_thermal_text(receipt, paper=paper)
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
    if fmt == "pdf":
        pdf = receipts_svc.to_thermal_pdf(receipt, paper=paper)
        filename = f"receipt_{receipt['reference']}.pdf".replace("/", "-")
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    raise HTTPException(status_code=400, detail="format must be json, text, or pdf")


@api.post("/pos/sales/{sale_id}/receipt/send")
async def pos_receipt_send(
    sale_id: str,
    channel: str = "email",
    to: str | None = None,
    paper: str = "80mm",
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Send digital receipt via email or SMS."""
    from app import receipts as receipts_svc
    from app import emailer
    from app import sms as sms_svc

    receipt = await receipts_svc.build_sale_receipt(
        db,
        tenant_id=claims["tenant_id"],
        sale_id=sale_id,
        user_id=claims.get("sub"),
    )
    paper = paper if paper in {"58mm", "80mm"} else "80mm"
    text = receipts_svc.render_thermal_text(receipt, paper=paper)
    channel = (channel or "email").lower()

    if channel == "email":
        user = await db.get(m.User, claims["sub"])
        recipient = to or (user.email if user else None)
        if not recipient:
            raise HTTPException(status_code=400, detail="No email recipient")
        result = await emailer.send_email(
            to=recipient,
            subject=f"Receipt {receipt['reference']}",
            text_body=text,
            html_body=f"<pre style=\"font-family:monospace\">{text}</pre>",
        )
        await db.commit()
        if not result.sent and result.mode == "smtp":
            raise HTTPException(status_code=502, detail=result.error or "Email send failed")
        return env(
            {"channel": "email", "to": recipient, "sent": result.sent, "mode": result.mode},
            "Receipt emailed",
        )

    if channel == "sms":
        user = await db.get(m.User, claims["sub"])
        recipient = to or (user.phone if user else None)
        if not recipient:
            raise HTTPException(status_code=400, detail="No SMS recipient phone")
        body = (
            f"RIBDIGI receipt {receipt['reference']}: "
            f"{receipt.get('currency', '')} {_money_safe(receipt.get('total'))} "
            f"via {receipt.get('payment_method')}"
        )
        result = await sms_svc.send_sms(to=recipient, body=body)
        await db.commit()
        if not result.sent and result.mode == "twilio":
            raise HTTPException(status_code=502, detail=result.error or "SMS send failed")
        return env(
            {
                "channel": "sms",
                "to": result.recipients,
                "sent": result.sent,
                "mode": result.mode,
            },
            "Receipt SMS sent",
        )

    raise HTTPException(status_code=400, detail="channel must be email or sms")


def _money_safe(value) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


@api.get("/expenses/categories")
async def list_expense_categories(
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    await expenses_svc.ensure_default_categories(db, claims["tenant_id"])
    await db.commit()
    rows = (
        await db.execute(
            select(m.ExpenseCategory)
            .where(m.ExpenseCategory.tenant_id == claims["tenant_id"])
            .order_by(m.ExpenseCategory.name)
        )
    ).scalars().all()
    return env(
        [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "budget_amount": float(c.budget_amount or 0),
                "is_active": c.is_active,
            }
            for c in rows
        ]
    )


@api.post("/expenses/categories")
async def create_expense_category(
    payload: ExpenseCategoryCreate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    cat = m.ExpenseCategory(
        tenant_id=claims["tenant_id"],
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        budget_amount=payload.budget_amount,
    )
    db.add(cat)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Category code already exists") from exc
    return env({"id": cat.id, "code": cat.code, "name": cat.name})


@api.get("/expenses/settings")
async def expense_settings(
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await expenses_svc.get_approval_settings(db, claims["tenant_id"]))


@api.patch("/expenses/settings")
async def update_expense_settings(
    payload: ExpenseThresholdUpdate,
    claims=Depends(require_permission("expenses", "approve")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.levels is None and payload.expense_approval_threshold is None and payload.expense_l2_threshold is None:
        raise HTTPException(status_code=400, detail="No settings fields provided")
    levels_payload = None
    if payload.levels is not None:
        levels_payload = [lvl.model_dump() for lvl in payload.levels]
    data = await expenses_svc.update_approval_settings(
        db,
        tenant,
        expense_approval_threshold=payload.expense_approval_threshold,
        expense_l2_threshold=payload.expense_l2_threshold,
        levels=levels_payload,
    )
    await db.commit()
    return env(data, "Expense approval settings updated")


@api.get("/expenses/recurring")
async def list_recurring_expenses(
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.RecurringExpense)
            .where(m.RecurringExpense.tenant_id == claims["tenant_id"])
            .order_by(m.RecurringExpense.created_at.desc())
        )
    ).scalars().all()
    return env(
        [
            {
                "id": r.id,
                "category": r.category,
                "category_id": r.category_id,
                "description": r.description,
                "amount": float(r.amount),
                "frequency": r.frequency,
                "payment_method": r.payment_method,
                "payee": r.payee,
                "next_run_at": r.next_run_at,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    )


@api.post("/expenses/recurring")
async def create_recurring_expense(
    payload: RecurringExpenseCreate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await expenses_svc.create_recurring(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        amount=payload.amount,
        frequency=payload.frequency,
        description=payload.description,
        category_id=payload.category_id,
        category=payload.category,
        payment_method=payload.payment_method,
        payee=payload.payee,
    )
    await db.commit()
    return env({"id": row.id, "next_run_at": row.next_run_at}, "Recurring expense created")


@api.post("/expenses/recurring/generate")
async def generate_recurring_expenses(
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    created = await expenses_svc.generate_due_recurring(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"]
    )
    await db.commit()
    return env(
        [expenses_svc.serialize_expense(e) for e in created],
        f"Generated {len(created)} expense(s)",
    )


@api.get("/expenses")
async def expenses(claims=Depends(require_permission("expenses", "read")), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(m.Expense)
        .where(m.Expense.tenant_id == claims["tenant_id"])
        .order_by(m.Expense.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.Expense, claims)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await expenses_svc.serialize_expense_full(db, e) for e in rows])


@api.post("/expenses")
async def add_expense(
    payload: ExpenseCreate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.create_expense(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        amount=payload.amount,
        description=payload.description,
        category_id=payload.category_id,
        category=payload.category,
        payment_method=payload.payment_method,
        reference=payload.reference,
        payee=payload.payee,
        store_id=payload.store_id,
        liquid_account_id=payload.liquid_account_id,
        expense_date=payload.expense_date,
    )
    await db.commit()
    return env(await expenses_svc.serialize_expense_full(db, expense), "Expense recorded")


@api.get("/expenses/{expense_id}")
async def get_expense(
    expense_id: str,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    return env(await expenses_svc.serialize_expense_full(db, expense))


@api.patch("/expenses/{expense_id}")
async def patch_expense(
    expense_id: str,
    payload: ExpenseUpdate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, existing.created_by)
    expense = await expenses_svc.update_expense(
        db,
        tenant_id=claims["tenant_id"],
        expense_id=expense_id,
        user_id=claims["sub"],
        amount=payload.amount,
        description=payload.description,
        payee=payload.payee,
        reference=payload.reference,
        expense_date=payload.expense_date,
        payment_method=payload.payment_method,
        category_id=payload.category_id,
        category=payload.category,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="expenses",
        action="expense_update",
        entity="expense",
        entity_id=expense.id,
        details={"status": expense.status, "amount": float(expense.amount)},
    )
    await db.commit()
    return env(await expenses_svc.serialize_expense_full(db, expense), "Expense updated")


@api.post("/expenses/{expense_id}/ocr-suggest")
async def expense_ocr_suggest(
    expense_id: str,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import expense_ocr as ocr_svc

    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    result = await ocr_svc.suggest_for_expense(
        db, tenant_id=claims["tenant_id"], expense_id=expense_id
    )
    return env(result, "OCR suggestions ready — review before applying")


@api.post("/expenses/{expense_id}/attachment")
async def upload_expense_attachment(
    expense_id: str,
    file: UploadFile = File(...),
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="expenses",
        upload=file,
        allowed_types=storage_svc.ATTACHMENT_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_ATTACHMENT_BYTES),
    )
    if expense.attachment_url and "://" not in expense.attachment_url:
        storage_svc.delete_key(expense.attachment_url, tenant_id=claims["tenant_id"])
    expense.attachment_url = stored.key
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="expenses",
        action="expense_attachment_upload",
        entity="expense",
        entity_id=expense.id,
        details={"key": stored.key, "size": stored.size, "content_type": stored.content_type},
    )
    await db.commit()
    data = expenses_svc.serialize_expense(expense)
    data["uploaded"] = {
        "key": stored.key,
        "size": stored.size,
        "content_type": stored.content_type,
        "filename": stored.original_filename,
    }
    return env(data, "Attachment uploaded")


@api.get("/expenses/{expense_id}/attachment")
async def download_expense_attachment(
    expense_id: str,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    if not expense.attachment_url:
        raise HTTPException(status_code=404, detail="No attachment uploaded")
    if "://" in expense.attachment_url:
        raise HTTPException(
            status_code=400,
            detail="Attachment is an external URL; open attachment_url directly",
        )
    return storage_svc.media_response(
        expense.attachment_url, tenant_id=claims["tenant_id"], as_attachment=True
    )


@api.delete("/expenses/{expense_id}/attachment")
async def delete_expense_attachment(
    expense_id: str,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    if not expense.attachment_url:
        raise HTTPException(status_code=404, detail="No attachment uploaded")
    if "://" not in expense.attachment_url:
        storage_svc.delete_key(expense.attachment_url, tenant_id=claims["tenant_id"])
    expense.attachment_url = None
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="expenses",
        action="expense_attachment_delete",
        entity="expense",
        entity_id=expense.id,
    )
    await db.commit()
    return env(expenses_svc.serialize_expense(expense), "Attachment removed")


@api.post("/expenses/{expense_id}/approve")
async def approve_expense(
    expense_id: str,
    payload: ExpenseDecision = ExpenseDecision(),
    claims=Depends(require_permission("expenses", "approve")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.approve_expense(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        expense_id=expense_id,
        comment=payload.comment,
        actor_role=claims.get("role"),
    )
    await db.commit()
    msg = "Expense approved" if expense.status == "approved" else f"Level {int(expense.approval_step) - 1} approved; awaiting next level"
    return env(await expenses_svc.serialize_expense_full(db, expense), msg)


@api.post("/expenses/{expense_id}/reject")
async def reject_expense(
    expense_id: str,
    payload: ExpenseDecision,
    claims=Depends(require_permission("expenses", "approve")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.reject_expense(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        expense_id=expense_id,
        reason=payload.reason or payload.comment or "",
        actor_role=claims.get("role"),
    )
    await db.commit()
    return env(await expenses_svc.serialize_expense_full(db, expense), "Expense rejected")


@api.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: str,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    if expense.status == "approved":
        raise HTTPException(status_code=409, detail="Approved expenses cannot be deleted")
    if expense.attachment_url and "://" not in expense.attachment_url:
        storage_svc.delete_key(expense.attachment_url, tenant_id=claims["tenant_id"])
    await db.delete(expense)
    await db.commit()
    return env({"id": expense_id}, "Expense deleted")


@api.get("/accounting/accounts")
async def accounts(claims=Depends(require_permission("accounting", "read")), db: AsyncSession = Depends(get_db)):
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    await ensure_default_accounts(db, claims["tenant_id"])
    await db.commit()
    rows = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == claims["tenant_id"]).order_by(m.Account.code)
        )
    ).scalars().all()
    return env([bank_recon_svc.serialize_account(r) for r in rows])


@api.get("/accounting/liquid-accounts")
async def liquid_accounts(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    await ensure_default_accounts(db, claims["tenant_id"])
    await db.commit()
    rows = await bank_recon_svc.list_liquid_accounts(db, claims["tenant_id"])
    return env([bank_recon_svc.serialize_account(r) for r in rows])


@api.get("/settings/bank-feed")
async def bank_feed_settings(claims=Depends(require_permission("accounting", "read"))):
    from app import bank_connectors as bank_connectors_svc

    return env(bank_connectors_svc.settings_payload())


@api.get("/accounting/bank-connections")
async def list_bank_connections(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_connectors as bank_connectors_svc

    rows = await bank_connectors_svc.list_connections(db, claims["tenant_id"])
    return env([bank_connectors_svc.serialize_connection(r) for r in rows])


@api.post("/accounting/bank-connections")
async def create_bank_connection(
    payload: BankConnectionCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts
    from app import bank_connectors as bank_connectors_svc
    from app import audit as audit_svc

    await ensure_default_accounts(db, claims["tenant_id"])
    row = await bank_connectors_svc.create_connection(
        db,
        tenant_id=claims["tenant_id"],
        account_id=payload.account_id,
        provider=payload.provider,
        display_name=payload.display_name,
        external_account_id=payload.external_account_id,
        feed_url=payload.feed_url,
        access_token=payload.access_token,
        auto_sync=payload.auto_sync,
        auto_match_after_sync=payload.auto_match_after_sync,
        sync_lookback_days=payload.sync_lookback_days,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="bank_connection_create",
        entity="bank_account_connection",
        entity_id=row.id,
        details={"provider": row.provider, "account_id": row.account_id},
    )
    await db.commit()
    return env(bank_connectors_svc.serialize_connection(row), "Bank connection created")


@api.patch("/accounting/bank-connections/{connection_id}")
async def update_bank_connection(
    connection_id: str,
    payload: BankConnectionUpdate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_connectors as bank_connectors_svc

    row = await bank_connectors_svc.update_connection(
        db,
        tenant_id=claims["tenant_id"],
        connection_id=connection_id,
        payload=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return env(bank_connectors_svc.serialize_connection(row), "Bank connection updated")


@api.delete("/accounting/bank-connections/{connection_id}")
async def delete_bank_connection(
    connection_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_connectors as bank_connectors_svc
    from app import audit as audit_svc

    await bank_connectors_svc.delete_connection(
        db, tenant_id=claims["tenant_id"], connection_id=connection_id
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="bank_connection_delete",
        entity="bank_account_connection",
        entity_id=connection_id,
    )
    await db.commit()
    return env({"id": connection_id}, "Bank connection removed")


@api.post("/accounting/bank-connections/{connection_id}/sync")
async def sync_bank_connection(
    connection_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts
    from app import bank_connectors as bank_connectors_svc
    from app import audit as audit_svc

    await ensure_default_accounts(db, claims["tenant_id"])
    result = await bank_connectors_svc.sync_connection(
        db,
        tenant_id=claims["tenant_id"],
        connection_id=connection_id,
        user_id=claims.get("sub"),
        force=True,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="bank_connection_sync",
        entity="bank_account_connection",
        entity_id=connection_id,
        details={
            "imported": result.get("imported"),
            "statement_id": result.get("statement_id"),
            "provider": result.get("provider"),
        },
    )
    await db.commit()
    return env(result, "Bank feed synced")


@api.get("/accounting/bank-statements")
async def list_bank_statements(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    rows = await bank_recon_svc.list_statements(db, claims["tenant_id"])
    out = []
    for row in rows:
        lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], row.id)
        out.append(bank_recon_svc.serialize_statement(row, lines))
    return env(out)


@api.post("/accounting/bank-statements")
async def create_bank_statement(
    payload: dict,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    await ensure_default_accounts(db, claims["tenant_id"])
    stmt = await bank_recon_svc.create_statement(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        account_id=payload.get("account_id") or "",
        statement_date=payload.get("statement_date"),
        opening_balance=float(payload.get("opening_balance") or 0),
        closing_balance=float(payload.get("closing_balance") or 0),
        notes=payload.get("notes"),
        lines=payload.get("lines") or [],
    )
    await db.commit()
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], stmt.id)
    return env(bank_recon_svc.serialize_statement(stmt, lines), "Bank statement created")


@api.post("/accounting/bank-statements/import")
async def import_bank_statement(
    account_id: str,
    file: UploadFile = File(...),
    opening_balance: float | None = None,
    closing_balance: float | None = None,
    statement_date: str | None = None,
    notes: str | None = None,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Import a CSV or OFX/QFX bank statement file into a reconcilable statement."""
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    await ensure_default_accounts(db, claims["tenant_id"])
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")

    stmt, meta = await bank_recon_svc.import_statement_from_feed(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        account_id=account_id,
        content=content,
        filename=file.filename,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        statement_date=statement_date,
        notes=notes,
    )
    await db.commit()
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], stmt.id)
    data = bank_recon_svc.serialize_statement(stmt, lines)
    data["import"] = meta
    return env(data, f"Imported {meta['format'].upper()} statement ({meta['line_count']} lines)")


@api.get("/accounting/bank-statements/{statement_id}")
async def get_bank_statement(
    statement_id: str,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], statement_id)
    data = bank_recon_svc.serialize_statement(stmt, lines)
    data["unmatched_book_lines"] = await bank_recon_svc.unmatched_book_lines(
        db, tenant_id=claims["tenant_id"], account_id=stmt.account_id
    )
    data["suggestions"] = await bank_recon_svc.auto_match_suggestions(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    data["clearing_groups"] = await bank_recon_svc.list_clearing_groups(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    return env(data)


@api.post("/accounting/bank-statements/{statement_id}/clear-group")
async def clear_bank_statement_group(
    statement_id: str,
    payload: dict,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Clear N bank lines against M book lines when totals match."""
    from app import bank_recon as bank_recon_svc

    result = await bank_recon_svc.create_clearing_group(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        statement_id=statement_id,
        statement_line_ids=list(payload.get("statement_line_ids") or []),
        journal_line_ids=list(payload.get("journal_line_ids") or []),
        notes=payload.get("notes"),
    )
    await db.commit()
    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], statement_id)
    data = bank_recon_svc.serialize_statement(stmt, lines)
    data["clear_result"] = result
    data["clearing_groups"] = await bank_recon_svc.list_clearing_groups(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    data["unmatched_book_lines"] = await bank_recon_svc.unmatched_book_lines(
        db, tenant_id=claims["tenant_id"], account_id=stmt.account_id
    )
    data["suggestions"] = await bank_recon_svc.auto_match_suggestions(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    return env(data, "Clearing group applied")


@api.post("/accounting/bank-statements/{statement_id}/clear-groups/{group_id}/dissolve")
async def dissolve_bank_clearing_group(
    statement_id: str,
    group_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    result = await bank_recon_svc.dissolve_clearing_group(
        db, tenant_id=claims["tenant_id"], group_id=group_id
    )
    await db.commit()
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], statement_id)
    data = bank_recon_svc.serialize_statement(stmt, lines)
    data["dissolve"] = result
    data["clearing_groups"] = await bank_recon_svc.list_clearing_groups(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    return env(data, "Clearing group dissolved")


@api.post("/accounting/bank-statements/{statement_id}/auto-clear")
async def auto_clear_bank_statement(
    statement_id: str,
    payload: dict | None = None,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Apply high-confidence (default) bank↔book matches in one shot."""
    from app import bank_recon as bank_recon_svc

    body = payload or {}
    result = await bank_recon_svc.apply_auto_matches(
        db,
        tenant_id=claims["tenant_id"],
        statement_id=statement_id,
        min_confidence=str(body.get("min_confidence") or "high"),
        date_window_days=int(body.get("date_window_days") or 7),
    )
    await db.commit()
    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], statement_id)
    data = bank_recon_svc.serialize_statement(stmt, lines)
    data["auto_clear"] = result
    data["suggestions"] = await bank_recon_svc.auto_match_suggestions(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    return env(data, f"Auto-cleared {result['applied_count']} line(s)")


@api.post("/accounting/bank-statements/{statement_id}/lines/{line_id}/match")
async def match_bank_statement_line(
    statement_id: str,
    line_id: str,
    payload: dict,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    line = await bank_recon_svc.match_line(
        db,
        tenant_id=claims["tenant_id"],
        line_id=line_id,
        journal_line_id=payload.get("journal_line_id") or "",
    )
    if line.statement_id != stmt.id:
        raise HTTPException(status_code=404, detail="Statement line not found")
    await db.commit()
    return env(bank_recon_svc.serialize_line(line), "Line matched")


@api.post("/accounting/bank-statements/{statement_id}/lines/{line_id}/unmatch")
async def unmatch_bank_statement_line(
    statement_id: str,
    line_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    line = await bank_recon_svc.unmatch_line(db, tenant_id=claims["tenant_id"], line_id=line_id)
    if line.statement_id != stmt.id:
        raise HTTPException(status_code=404, detail="Statement line not found")
    await db.commit()
    return env(bank_recon_svc.serialize_line(line), "Line unmatched")


@api.post("/accounting/bank-statements/{statement_id}/lines/{line_id}/ignore")
async def ignore_bank_statement_line(
    statement_id: str,
    line_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    line = await bank_recon_svc.ignore_line(db, tenant_id=claims["tenant_id"], line_id=line_id)
    if line.statement_id != stmt.id:
        raise HTTPException(status_code=404, detail="Statement line not found")
    await db.commit()
    return env(bank_recon_svc.serialize_line(line), "Line ignored")


@api.post("/accounting/bank-statements/{statement_id}/complete")
async def complete_bank_statement(
    statement_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.complete_statement(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    await db.commit()
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], stmt.id)
    return env(bank_recon_svc.serialize_statement(stmt, lines), "Statement reconciled")


@api.get("/accounting/cheques")
async def list_cheques(
    direction: str | None = None,
    status: str | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await cheques_svc.list_cheques(
        db, claims["tenant_id"], direction=direction, status=status
    )
    return env([cheques_svc.serialize_cheque(r) for r in rows])


@api.get("/accounting/cheques/{cheque_id}")
async def get_cheque_detail(
    cheque_id: str,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.get_cheque(db, claims["tenant_id"], cheque_id)
    return env(cheques_svc.serialize_cheque(row))


@api.post("/accounting/cheques/{cheque_id}/deposit")
async def deposit_cheque_api(
    cheque_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.deposit_cheque(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], cheque_id=cheque_id
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque deposited to bank")


@api.post("/accounting/cheques/{cheque_id}/clear")
async def clear_cheque_api(
    cheque_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.clear_cheque(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], cheque_id=cheque_id
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque cleared")


@api.post("/accounting/cheques/{cheque_id}/bounce")
async def bounce_cheque_api(
    cheque_id: str,
    reason: str | None = None,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.bounce_cheque(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        cheque_id=cheque_id,
        reason=reason,
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque bounced")


@api.post("/accounting/cheques/{cheque_id}/cancel")
async def cancel_cheque_api(
    cheque_id: str,
    reason: str | None = None,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.cancel_cheque(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        cheque_id=cheque_id,
        reason=reason,
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque cancelled")


@api.get("/accounting/journal-entries")
async def list_journals(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    rows = (
        await db.execute(
            select(m.JournalEntry)
            .where(m.JournalEntry.tenant_id == claims["tenant_id"])
            .order_by(m.JournalEntry.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return env([await accounting_svc.serialize_journal(db, e) for e in rows])


@api.post("/accounting/journal-entries")
async def create_journal(
    payload: JournalCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.post_journal_entry(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        description=payload.description,
        reference=payload.reference,
        lines=[ln.model_dump() for ln in payload.lines],
    )
    await db.commit()
    return env(await accounting_svc.serialize_journal(db, entry), "Journal entry posted")


@api.get("/accounting/trial-balance")
async def get_trial_balance(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts, trial_balance

    await ensure_default_accounts(db, claims["tenant_id"])
    await db.commit()
    return env(await trial_balance(db, claims["tenant_id"]))


@api.get("/accounting/profit-loss")
async def get_profit_loss(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts, profit_and_loss

    await ensure_default_accounts(db, claims["tenant_id"])
    await db.commit()
    return env(await profit_and_loss(db, claims["tenant_id"]))


@api.get("/reports/profit-loss")
async def report_profit_loss(
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return await get_profit_loss(claims, db)


@api.get("/reports/trial-balance")
async def report_trial_balance(
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return await get_trial_balance(claims, db)


@api.get("/reports/cash-flow")
async def report_cash_flow(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.cash_flow(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/balance-sheet")
async def report_balance_sheet(
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await reports_svc.balance_sheet(db, claims["tenant_id"]))


@api.get("/reports/export")
async def reports_export(
    report_type: str,
    format: str = "csv",
    from_date: str | None = None,
    to_date: str | None = None,
    date: str | None = None,
    year: int | None = None,
    month: int | None = None,
    warehouse_id: str | None = None,
    jurisdiction: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    content, media, filename = await report_export_svc.export_report(
        db,
        claims["tenant_id"],
        report_type,
        format,
        from_date=from_date,
        to_date=to_date,
        date=date,
        year=year,
        month=month,
        warehouse_id=warehouse_id,
        jurisdiction=jurisdiction,
    )
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/reports/exportable")
async def reports_exportable(claims=Depends(require_permission("reports", "read"))):
    return env(
        {
            "types": sorted(report_export_svc.EXPORTABLE),
            "formats": sorted(report_export_svc.EXPORT_FORMATS),
        }
    )


@api.get("/reports/schedules")
async def report_schedules_list(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = await report_schedules_svc.list_schedules(db, claims["tenant_id"])
    return env([report_schedules_svc.serialize_schedule(r) for r in rows])


@api.post("/reports/schedules")
async def report_schedules_create(
    payload: dict,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await report_schedules_svc.create_schedule(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        name=payload.get("name") or "",
        report_type=payload.get("report_type") or "",
        format=payload.get("format") or "xlsx",
        frequency=payload.get("frequency") or "daily",
        weekday=payload.get("weekday"),
        hour_utc=int(payload.get("hour_utc", 6)),
        recipients=payload.get("recipients"),
        enabled=bool(payload.get("enabled", True)),
    )
    await db.commit()
    return env(report_schedules_svc.serialize_schedule(row), "Report schedule created")


@api.patch("/reports/schedules/{schedule_id}")
async def report_schedules_patch(
    schedule_id: str,
    payload: dict,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await report_schedules_svc.update_schedule(
        db,
        claims["tenant_id"],
        schedule_id,
        name=payload.get("name"),
        report_type=payload.get("report_type"),
        format=payload.get("format"),
        frequency=payload.get("frequency"),
        weekday=payload.get("weekday"),
        hour_utc=payload.get("hour_utc"),
        recipients=payload.get("recipients"),
        enabled=payload.get("enabled"),
    )
    await db.commit()
    return env(report_schedules_svc.serialize_schedule(row), "Report schedule updated")


@api.delete("/reports/schedules/{schedule_id}")
async def report_schedules_delete(
    schedule_id: str,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await report_schedules_svc.delete_schedule(db, claims["tenant_id"], schedule_id)
    await db.commit()
    return env({"id": schedule_id}, "Report schedule deleted")


@api.post("/reports/schedules/{schedule_id}/run")
async def report_schedules_run(
    schedule_id: str,
    force: bool = True,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await report_schedules_svc.get_schedule(db, claims["tenant_id"], schedule_id)
    result = await report_schedules_svc.run_schedule(
        db,
        tenant_id=claims["tenant_id"],
        schedule=row,
        force=force,
    )
    await db.commit()
    if result.get("ran"):
        return env(result, "Report emailed")
    return env(result)


@api.post("/reports/schedules/run-due")
async def report_schedules_run_due(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await report_schedules_svc.run_due_schedules_for_tenant(db, claims["tenant_id"])
    await db.commit()
    return env(result)


@api.get("/reports/sales/daily")
async def report_sales_daily(
    date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await reports_svc.sales_daily(db, claims["tenant_id"], reports_svc.parse_date(date)))


@api.get("/reports/sales/monthly")
async def report_sales_monthly(
    year: int | None = None,
    month: int | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    return env(
        await reports_svc.sales_monthly(
            db, claims["tenant_id"], year or now.year, month or now.month
        )
    )


@api.get("/reports/sales/products")
async def report_sales_products(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.sales_by_product(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/sales/salesperson")
async def report_sales_salesperson(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.sales_by_salesperson(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/sales/by-store")
async def report_sales_by_store(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.sales_by_store(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/inventory/balance")
async def report_inventory_balance(
    warehouse_id: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await reports_svc.inventory_balance(db, claims["tenant_id"], warehouse_id))


@api.get("/reports/inventory/movements")
async def report_inventory_movements(
    product_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.inventory_movements(
            db,
            claims["tenant_id"],
            product_id=product_id,
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/inventory/low-stock")
async def report_low_stock(
    store_id: str | None = None,
    warehouse_id: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.inventory_low_stock(
            db, claims["tenant_id"], store_id=store_id, warehouse_id=warehouse_id
        )
    )


@api.get("/reports/inventory/expiry")
async def report_inventory_expiry(
    days: int = 30,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await reports_svc.inventory_expiry(db, claims["tenant_id"], within_days=days))


@api.get("/reports/purchases/summary")
async def report_purchases_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.purchases_summary(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/purchases/suppliers")
async def report_purchases_suppliers(
    supplier_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.purchases_by_supplier(
            db,
            claims["tenant_id"],
            supplier_id=supplier_id,
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/expenses/summary")
async def report_expenses_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    category_id: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.expenses_summary(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            category_id=category_id,
        )
    )


@api.get("/credit/aging")
async def credit_aging(
    kind: str = "receivable",
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    if kind == "payable":
        return env(await credit_svc.ap_aging(db, claims["tenant_id"]))
    return env(await credit_svc.ar_aging(db, claims["tenant_id"]))


@api.get("/credit/settings")
async def credit_settings(
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(credit_svc.early_pay_settings(tenant))


@api.patch("/credit/settings")
async def update_credit_settings(
    payload: EarlyPaySettingsUpdate,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    tenant.early_pay_discount_pct = payload.early_pay_discount_pct
    tenant.early_pay_discount_days = payload.early_pay_discount_days
    await db.commit()
    return env(credit_svc.early_pay_settings(tenant), "Early payment terms updated")


@api.get("/credit/exchange-rates")
async def list_exchange_rates(
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import fx as fx_svc

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == claims["tenant_id"]))
    ).scalar_one()
    base = await fx_svc.get_base_currency(db, claims["tenant_id"])
    rows = await fx_svc.list_rates(db, claims["tenant_id"])
    return env(
        {
            "base_currency": base,
            "fx_auto_refresh": bool(getattr(tenant, "fx_auto_refresh", True)),
            "fx_provider": settings.FX_PROVIDER,
            "rates": [fx_svc.serialize_rate(r) for r in rows],
        }
    )


@api.post("/credit/exchange-rates/refresh")
async def refresh_exchange_rates(
    payload: ExchangeRateRefresh = ExchangeRateRefresh(),
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import fx as fx_svc

    result = await fx_svc.refresh_tenant_rates(
        db,
        tenant_id=claims["tenant_id"],
        currencies=payload.currencies,
        create_missing=True,
    )
    await db.commit()
    return env(result, "Exchange rates refreshed from live feed")


@api.patch("/credit/exchange-rates/settings")
async def update_fx_auto_refresh(
    payload: FxAutoRefreshUpdate,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == claims["tenant_id"]))
    ).scalar_one()
    tenant.fx_auto_refresh = bool(payload.fx_auto_refresh)
    await db.commit()
    return env(
        {"fx_auto_refresh": bool(tenant.fx_auto_refresh)},
        "FX auto-refresh updated",
    )


@api.put("/credit/exchange-rates/{currency_code}")
async def upsert_exchange_rate(
    currency_code: str,
    payload: ExchangeRateUpsert,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import fx as fx_svc

    row = await fx_svc.upsert_rate(
        db,
        tenant_id=claims["tenant_id"],
        currency_code=payload.currency_code or currency_code,
        rate_to_base=payload.rate_to_base,
        source="manual",
    )
    await db.commit()
    return env(fx_svc.serialize_rate(row), "Exchange rate saved")


@api.delete("/credit/exchange-rates/{currency_code}")
async def delete_exchange_rate(
    currency_code: str,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import fx as fx_svc

    await fx_svc.delete_rate(db, claims["tenant_id"], currency_code)
    await db.commit()
    return env({"currency_code": currency_code.upper()}, "Exchange rate deleted")


@api.get("/credit/invoices/{invoice_id}/early-discount")
async def invoice_early_discount_quote(
    invoice_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    ep = credit_svc.early_pay_settings(tenant)
    inv = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    quote = credit_svc.invoice_early_discount(
        inv,
        pct=ep["early_pay_discount_pct"],
        days=ep["early_pay_discount_days"],
    )
    return env({"invoice_id": inv.id, "invoice_number": inv.invoice_number, **quote})


@api.get("/credit/purchase-invoices/{invoice_id}/early-discount")
async def purchase_invoice_early_discount_quote(
    invoice_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    ep = credit_svc.early_pay_settings(tenant)
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    quote = credit_svc.purchase_invoice_early_discount(
        inv,
        pct=ep["early_pay_discount_pct"],
        days=ep["early_pay_discount_days"],
    )
    return env({"invoice_id": inv.id, "invoice_number": inv.invoice_number, **quote})


@api.get("/credit/customers/{customer_id}/statement")
async def customer_credit_statement(
    customer_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await credit_svc.customer_statement(db, claims["tenant_id"], customer_id))


@api.get("/credit/suppliers/{supplier_id}/statement")
async def supplier_credit_statement(
    supplier_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await credit_svc.supplier_statement(db, claims["tenant_id"], supplier_id))


@api.patch("/customers/{customer_id}/credit-limit")
async def update_customer_credit_limit(
    customer_id: str,
    payload: CreditLimitUpdate,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    customer = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == customer_id,
                m.Party.tenant_id == claims["tenant_id"],
                m.Party.kind == "customer",
            )
        )
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.credit_limit = payload.credit_limit
    await db.commit()
    return env(
        {
            "id": customer.id,
            "name": customer.name,
            "credit_limit": float(customer.credit_limit),
            "balance": float(customer.balance or 0),
        }
    )


@api.get("/customers/{customer_id}/outstanding")
async def customer_outstanding(
    customer_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == claims["tenant_id"],
                m.SalesInvoice.customer_id == customer_id,
                m.SalesInvoice.status.in_(["posted", "partial"]),
            )
        )
    ).scalars().all()
    rows = []
    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        rows.append(
            {
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": due,
                "due_date": inv.due_date,
                "status": inv.status,
            }
        )
    return env(rows)


@api.post("/customers/{customer_id}/payments")
async def customer_payment_alias(
    customer_id: str,
    payload: CustomerPaymentCreate,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    payment = await sales_svc.record_customer_payment(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        customer_id=customer_id,
        amount=payload.amount,
        sales_invoice_id=payload.sales_invoice_id,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        cheque_number=payload.cheque_number,
        bank_name=payload.bank_name,
        cheque_date=payload.cheque_date,
        apply_early_discount=payload.apply_early_discount,
        liquid_account_id=payload.liquid_account_id,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
    )
    await db.commit()
    return env(
        {
            "id": payment.id,
            "payment_number": payment.payment_number,
            "currency": getattr(payment, "currency", None) or "",
            "exchange_rate": float(getattr(payment, "exchange_rate", None) or 1),
            "fx_gain_loss": float(getattr(payment, "fx_gain_loss", 0) or 0),
        },
        "Payment recorded",
    )


@api.get("/suppliers/{supplier_id}/outstanding")
async def supplier_outstanding(
    supplier_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    orders = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == claims["tenant_id"],
                m.PurchaseOrder.supplier_id == supplier_id,
                m.PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
            )
        )
    ).scalars().all()
    invoices = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == claims["tenant_id"],
                m.PurchaseInvoice.supplier_id == supplier_id,
                m.PurchaseInvoice.status.in_(["unpaid", "partial", "overdue"]),
            )
        )
    ).scalars().all()
    out = []
    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        out.append(
            {
                "purchase_invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "purchase_order_id": inv.purchase_order_id,
                "amount": due,
                "due_date": inv.due_date,
                "status": inv.status,
                "document_type": "purchase_invoice",
            }
        )
    invoiced_pos = {i.purchase_order_id for i in invoices if i.purchase_order_id}
    for po in orders:
        if po.id in invoiced_pos:
            continue
        due = max(float(po.total_amount) - float(po.paid_amount or 0), 0)
        if due <= 0:
            continue
        out.append(
            {
                "purchase_order_id": po.id,
                "po_number": po.po_number,
                "amount": due,
                "due_date": po.due_date,
                "status": po.status,
                "document_type": "purchase_order",
            }
        )
    return env(out)


@api.post("/suppliers/{supplier_id}/payments")
async def supplier_payment(
    supplier_id: str,
    payload: SupplierPaymentCreate,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    payment = await purchasing_svc.record_supplier_payment(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        supplier_id=supplier_id,
        amount=payload.amount,
        purchase_order_id=payload.purchase_order_id,
        purchase_invoice_id=payload.purchase_invoice_id,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        cheque_number=payload.cheque_number,
        bank_name=payload.bank_name,
        cheque_date=payload.cheque_date,
        liquid_account_id=payload.liquid_account_id,
        apply_early_discount=payload.apply_early_discount,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
    )
    await db.commit()
    return env(
        {
            "id": payment.id,
            "payment_number": payment.payment_number,
            "amount": float(payment.amount),
            "early_payment_discount": float(getattr(payment, "early_payment_discount", 0) or 0),
            "currency": getattr(payment, "currency", None) or "",
            "exchange_rate": float(getattr(payment, "exchange_rate", None) or 1),
            "fx_gain_loss": float(getattr(payment, "fx_gain_loss", 0) or 0),
        },
        "Supplier payment recorded",
    )


@api.get("/tax/rates")
async def taxes(claims=Depends(require_permission("tax", "read")), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(m.TaxRate)
            .where(m.TaxRate.tenant_id == claims["tenant_id"])
            .order_by(m.TaxRate.name)
        )
    ).scalars().all()
    return env([tax_svc.serialize_tax_rate(r) for r in rows])


@api.post("/tax/rates")
async def add_tax(
    payload: TaxCreate,
    claims=Depends(require_permission("tax", "write")),
    db: AsyncSession = Depends(get_db),
):
    if payload.is_default:
        await tax_svc.clear_default_flags(db, claims["tenant_id"])
    data = payload.model_dump()
    comps = tax_svc.normalize_components(data.pop("components", None))
    if comps:
        data["components"] = comps
        data["rate"] = tax_svc.effective_rate_from_components(comps, data.get("rate") or 0)
    else:
        data["components"] = None
    tax = m.TaxRate(tenant_id=claims["tenant_id"], **data)
    db.add(tax)
    await db.commit()
    return env(tax_svc.serialize_tax_rate(tax), "Tax rate created")


@api.get("/tax/rates/{rate_id}")
async def get_tax_rate(
    rate_id: str,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    rate = await tax_svc.get_tax_rate(db, claims["tenant_id"], rate_id)
    return env(tax_svc.serialize_tax_rate(rate))


@api.post("/tax/rates/{rate_id}/default")
async def set_default_tax(
    rate_id: str,
    claims=Depends(require_permission("tax", "write")),
    db: AsyncSession = Depends(get_db),
):
    rate = await tax_svc.get_tax_rate(db, claims["tenant_id"], rate_id)
    await tax_svc.clear_default_flags(db, claims["tenant_id"])
    rate.is_default = True
    rate.is_active = True
    await db.commit()
    return env(tax_svc.serialize_tax_rate(rate), "Default tax rate updated")


@api.post("/tax/calculate")
async def calculate_tax(
    payload: TaxCalculateRequest,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    mode = payload.pricing_mode or "exclusive"
    rate_pct = payload.rate
    components = payload.components
    is_rc = bool(payload.is_reverse_charge) if payload.is_reverse_charge is not None else False
    if payload.tax_rate_id:
        row = await tax_svc.get_tax_rate(db, claims["tenant_id"], payload.tax_rate_id)
        rate_pct = float(row.rate)
        mode = payload.pricing_mode or row.pricing_mode
        if components is None:
            components = row.components
        if payload.is_reverse_charge is None:
            is_rc = bool(row.is_reverse_charge)
    if rate_pct is None and not components:
        default = await tax_svc.get_default_tax_rate(db, claims["tenant_id"])
        if not default:
            raise HTTPException(status_code=400, detail="No tax rate available")
        rate_pct = float(default.rate)
        mode = payload.pricing_mode or default.pricing_mode
        if components is None:
            components = default.components
        if payload.is_reverse_charge is None:
            is_rc = bool(default.is_reverse_charge)
    if rate_pct is None:
        rate_pct = tax_svc.effective_rate_from_components(
            tax_svc.normalize_components(components), 0
        )
    detail = tax_svc.compute_tax_breakdown(
        payload.amount,
        rate_pct,
        mode,
        components=components,
        is_reverse_charge=is_rc,
    )
    return env(
        {
            "net": detail["net"],
            "tax": detail["tax"],
            "gross": detail["gross"],
            "rate": detail["effective_rate"],
            "pricing_mode": mode,
            "is_reverse_charge": detail["is_reverse_charge"],
            "components": detail["components"],
        }
    )


@api.get("/reports/tax")
async def reports_tax(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await tax_svc.tax_report(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/tax/filing")
async def reports_tax_filing(
    from_date: str | None = None,
    to_date: str | None = None,
    jurisdiction: str | None = None,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tax_filings as tax_filings_svc

    fd = reports_svc.parse_date(from_date)
    td = reports_svc.parse_date(to_date, end_of_day=True)
    if jurisdiction:
        return env(
            await tax_filings_svc.government_filing_pack(
                db,
                claims["tenant_id"],
                from_date=fd,
                to_date=td,
                jurisdiction=jurisdiction,
            )
        )
    # Default: neutral pack + government section for tenant jurisdiction when supported
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    juris = (getattr(tenant, "tax_jurisdiction", None) or "GH").upper() if tenant else "GH"
    try:
        return env(
            await tax_filings_svc.government_filing_pack(
                db,
                claims["tenant_id"],
                from_date=fd,
                to_date=td,
                jurisdiction=juris,
            )
        )
    except HTTPException as exc:
        if exc.status_code == 400:
            pack = await tax_svc.tax_filing_pack(
                db, claims["tenant_id"], from_date=fd, to_date=td
            )
            pack["jurisdiction"] = juris
            pack["government"] = None
            pack["supported_jurisdictions"] = tax_filings_svc.list_supported()
            return env(pack)
        raise


@api.get("/taxes/rates")
async def taxes_alias(claims=Depends(require_permission("tax", "read")), db: AsyncSession = Depends(get_db)):
    return await taxes(claims, db)


@api.get("/stores")
async def stores(claims=Depends(require_permission("stores", "read")), db: AsyncSession = Depends(get_db)):
    from app import cash_drawer as cash_drawer_svc

    rows = (
        await db.execute(select(m.Store).where(m.Store.tenant_id == claims["tenant_id"]))
    ).scalars().all()
    return env(
        [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "address": s.address,
                "phone": s.phone,
                "manager_id": s.manager_id,
                "is_active": s.is_active,
                **{k: v for k, v in cash_drawer_svc.serialize_drawer_settings(s).items() if k != "source"},
            }
            for s in rows
        ]
    )


@api.post("/stores")
async def add_store(
    payload: StoreCreate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    store = await stores_svc.create_store(
        db,
        tenant_id=claims["tenant_id"],
        name=payload.name,
        code=payload.code,
        address=payload.address,
        phone=payload.phone,
        manager_id=payload.manager_id,
    )
    await db.commit()
    return env({"id": store.id, "code": store.code}, "Store created with warehouse")


@api.patch("/stores/{store_id}/drawer")
async def update_store_drawer(
    store_id: str,
    payload: StoreDrawerSettingsUpdate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    store = await stores_svc.get_store(db, claims["tenant_id"], store_id)
    data = payload.model_dump(exclude_unset=True)
    if "drawer_mode" in data and data["drawer_mode"] is not None:
        store.drawer_mode = cash_drawer_svc.normalize_mode(data["drawer_mode"])
    if "drawer_host" in data:
        store.drawer_host = (data["drawer_host"] or "").strip() or None
    if "drawer_port" in data and data["drawer_port"] is not None:
        store.drawer_port = int(data["drawer_port"])
    if "drawer_open_on_cash" in data and data["drawer_open_on_cash"] is not None:
        store.drawer_open_on_cash = bool(data["drawer_open_on_cash"])
    if store.drawer_mode == "network" and not store.drawer_host:
        raise HTTPException(status_code=400, detail="drawer_host is required for network mode")
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="stores",
        action="drawer_settings_update",
        entity="store",
        entity_id=store.id,
        details=cash_drawer_svc.serialize_drawer_settings(store),
    )
    await db.commit()
    return env(
        {
            "id": store.id,
            **{k: v for k, v in cash_drawer_svc.serialize_drawer_settings(store).items() if k != "source"},
        },
        "Cash drawer settings updated",
    )


@api.get("/stores/{store_id}/inventory")
async def store_inventory(
    store_id: str,
    include_zero: bool = False,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await stores_svc.store_inventory(
            db, claims["tenant_id"], store_id, include_zero=include_zero
        )
    )


@api.put("/stores/{store_id}/reorder-policy")
async def set_store_reorder_policy(
    store_id: str,
    payload: StoreReorderPolicyUpdate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await stores_svc.set_store_reorder_policy(
        db,
        tenant_id=claims["tenant_id"],
        store_id=store_id,
        product_id=payload.product_id,
        reorder_level=payload.reorder_level,
        reorder_qty=payload.reorder_qty,
    )
    await db.commit()
    return env(row, "Store reorder policy saved")


@api.get("/inventory/settings")
async def inventory_settings(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(
        {
            "fefo_strict_warehouse": bool(getattr(tenant, "fefo_strict_warehouse", False)),
        }
    )


@api.patch("/inventory/settings")
async def update_inventory_settings(
    payload: InventoryFefoSettingsUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    tenant.fefo_strict_warehouse = bool(payload.fefo_strict_warehouse)
    await db.commit()
    return env(
        {"fefo_strict_warehouse": tenant.fefo_strict_warehouse},
        "Inventory FEFO settings updated",
    )


@api.get("/stores/transfers")
async def list_transfers(
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.StockTransfer)
            .where(m.StockTransfer.tenant_id == claims["tenant_id"])
            .order_by(m.StockTransfer.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return env([await stores_svc.serialize_transfer(db, t) for t in rows])


@api.post("/stores/transfers")
async def create_transfer(
    payload: StockTransferCreate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.create_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        from_store_id=payload.from_store_id,
        to_store_id=payload.to_store_id,
        items=[i.model_dump() for i in payload.items],
        notes=payload.notes,
        submit=payload.submit,
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer created")


@api.get("/stores/transfers/{transfer_id}")
async def get_transfer(
    transfer_id: str,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    # Transfers are operationally shared (ship/receive); record scope is not applied.
    transfer = await stores_svc.get_transfer(db, claims["tenant_id"], transfer_id)
    return env(await stores_svc.serialize_transfer(db, transfer))


@api.post("/stores/transfers/{transfer_id}/submit")
async def submit_transfer(
    transfer_id: str,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.submit_transfer(
        db, tenant_id=claims["tenant_id"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer requested")


@api.post("/stores/transfers/{transfer_id}/ship")
async def ship_transfer(
    transfer_id: str,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.ship_transfer(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer shipped")


@api.post("/stores/transfers/{transfer_id}/receive")
async def receive_transfer(
    transfer_id: str,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.receive_transfer(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer received")


@api.post("/stores/transfers/{transfer_id}/cancel")
async def cancel_transfer(
    transfer_id: str,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.cancel_transfer(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer cancelled")


@api.get("/warehouses")
async def warehouses(claims=Depends(require_permission("inventory", "read")), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(m.Warehouse).where(m.Warehouse.tenant_id == claims["tenant_id"]))
    ).scalars().all()
    return env(rows)


@api.post("/warehouses")
async def add_warehouse(
    payload: WarehouseCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    warehouse = m.Warehouse(tenant_id=claims["tenant_id"], **payload.model_dump())
    db.add(warehouse)
    await db.commit()
    return env({"id": warehouse.id})


@api.get("/reports/summary")
async def report(claims=Depends(require_permission("reports", "read")), db: AsyncSession = Depends(get_db)):
    dash = await dashboard(claims, db)
    now = datetime.utcnow()
    daily = await reports_svc.sales_daily(db, claims["tenant_id"], now)
    monthly = await reports_svc.sales_monthly(db, claims["tenant_id"], now.year, now.month)
    low = await reports_svc.inventory_low_stock(db, claims["tenant_id"])
    expenses = await reports_svc.expenses_summary(db, claims["tenant_id"])
    return env(
        {
            **(dash.get("data") if isinstance(dash, dict) and "data" in dash else {}),
            "today_sales": daily,
            "month_sales": {
                "total_revenue": monthly["total_revenue"],
                "change_pct": monthly["change_pct"],
                "invoice_count": monthly["invoice_count"],
                "pos_count": monthly["pos_count"],
            },
            "low_stock_report": low,
            "expenses_summary": {
                "total_amount": expenses["total_amount"],
                "count": expenses["count"],
            },
        }
    )


@api.get("/notifications")
async def notifications(
    status: str | None = None,
    category: str | None = None,
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await notifications_svc.list_notifications(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        status=status,
        category=category,
    )
    return env([notifications_svc.serialize_notification(n) for n in rows])


@api.get("/notifications/unread-count")
async def notifications_unread_count(
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    count = await notifications_svc.unread_count(db, claims["tenant_id"], claims["sub"])
    return env({"count": count})


@api.patch("/notifications/{nid}/read")
async def notification_read(
    nid: str,
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    note = await notifications_svc.mark_read(
        db, tenant_id=claims["tenant_id"], notification_id=nid, user_id=claims["sub"]
    )
    await db.commit()
    return env(notifications_svc.serialize_notification(note), "Marked read")


@api.post("/notifications/read-all")
async def notifications_read_all(
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    count = await notifications_svc.mark_all_read(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"]
    )
    await db.commit()
    return env({"marked": count}, "All notifications marked read")


@api.get("/notifications/settings")
async def notification_settings(
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    prefs = await notifications_svc.get_preferences(db, claims["tenant_id"], claims["sub"])
    return env(prefs)


@api.patch("/notifications/settings")
async def update_notification_settings(
    payload: NotificationPreferencesUpdate,
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    prefs = await notifications_svc.update_preferences(
        db, claims["tenant_id"], claims["sub"], payload.preferences
    )
    await db.commit()
    return env(prefs, "Notification preferences updated")


@api.post("/notifications/scan-due")
async def scan_due_notifications(
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    created = await notifications_svc.scan_payment_due(db, claims["tenant_id"])
    await db.commit()
    return env({"created": created}, f"Created {created} payment-due notification(s)")


@api.get("/jobs")
async def list_jobs(claims=Depends(require_roles("super_admin", "company_admin"))):
    from app.config import settings as app_settings
    from app import jobs as jobs_svc

    return env(
        {
            "celery_enabled": bool(app_settings.CELERY_ENABLED),
            "broker": app_settings.celery_broker_url,
            "result_backend": app_settings.celery_result_backend,
            "task_always_eager": bool(app_settings.CELERY_TASK_ALWAYS_EAGER),
            "jobs": sorted(jobs_svc.JOB_HANDLERS.keys()),
            "beat": {
                "scan_low_stock_minutes": app_settings.CELERY_LOW_STOCK_INTERVAL_MINUTES,
                "scan_payment_due_minutes": app_settings.CELERY_PAYMENT_DUE_INTERVAL_MINUTES,
                "generate_recurring_expenses_minutes": app_settings.CELERY_RECURRING_INTERVAL_MINUTES,
                "run_due_backups_minutes": app_settings.CELERY_BACKUP_INTERVAL_MINUTES,
                "run_due_report_emails_minutes": app_settings.CELERY_REPORT_EMAIL_INTERVAL_MINUTES,
            },
        }
    )


@api.post("/jobs/{job_name}/run")
async def run_job_now(
    job_name: str,
    enqueue: bool = False,
    claims=Depends(require_roles("super_admin")),
):
    """Run a scheduled job immediately (sync) or enqueue to Celery."""
    from app import jobs as jobs_svc
    from app.config import settings as app_settings

    if job_name not in jobs_svc.JOB_HANDLERS:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}")

    if enqueue:
        if not app_settings.CELERY_ENABLED:
            raise HTTPException(status_code=503, detail="CELERY_ENABLED is false")
        from app.tasks import run_named_job

        async_result = run_named_job.delay(job_name)
        return env(
            {"job": job_name, "enqueued": True, "task_id": async_result.id},
            "Job enqueued",
        )

    result = await jobs_svc.run_job(job_name)
    return env(result, f"Job {job_name} completed")


@api.get("/audit-logs")
async def audit_logs(
    user_id: str | None = None,
    module: str | None = None,
    action: str | None = None,
    entity: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 200,
    claims=Depends(require_permission("audit", "read")),
    db: AsyncSession = Depends(get_db),
):
    role = claims.get("role", "")
    scoped_user = user_id
    if role not in {"super_admin", "company_admin", "store_manager", "accountant"}:
        scoped_user = claims["sub"]
    rows = await audit_svc.query_logs(
        db,
        tenant_id=claims["tenant_id"],
        user_id=scoped_user,
        module=module,
        action=action,
        entity=entity,
        from_date=reports_svc.parse_date(from_date),
        to_date=reports_svc.parse_date(to_date, end_of_day=True),
        limit=limit,
    )
    return env([audit_svc.serialize_audit(r) for r in rows])


@api.get("/audit-logs/export")
async def audit_logs_export(
    user_id: str | None = None,
    module: str | None = None,
    action: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("audit", "read")),
    db: AsyncSession = Depends(get_db),
):
    role = claims.get("role", "")
    scoped_user = user_id
    if role not in {"super_admin", "company_admin", "store_manager", "accountant"}:
        scoped_user = claims["sub"]
    rows = await audit_svc.query_logs(
        db,
        tenant_id=claims["tenant_id"],
        user_id=scoped_user,
        module=module,
        action=action,
        from_date=reports_svc.parse_date(from_date),
        to_date=reports_svc.parse_date(to_date, end_of_day=True),
        limit=1000,
    )
    # Reverse for chronological CSV
    csv_text = audit_svc.to_csv(list(reversed(rows)))
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )


@api.get("/audit-logs/verify")
async def audit_logs_verify(
    claims=Depends(require_permission("audit", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await audit_svc.verify_chain(db, claims["tenant_id"]))


@api.delete("/audit-logs/{log_id}")
async def audit_logs_delete_blocked(
    log_id: str,
    claims=Depends(require_permission("audit", "read")),
):
    audit_svc.reject_mutation()


@api.patch("/audit-logs/{log_id}")
async def audit_logs_patch_blocked(
    log_id: str,
    claims=Depends(require_permission("audit", "read")),
):
    audit_svc.reject_mutation()


@api.get("/backup/settings")
async def backup_settings_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await backup_svc.get_or_create_settings(db, claims["tenant_id"])
    await db.commit()
    return env(backup_svc.serialize_settings(row))


@api.patch("/backup/settings")
async def backup_settings_patch(
    payload: dict,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await backup_svc.update_settings(
        db,
        claims["tenant_id"],
        enabled=payload.get("enabled"),
        frequency=payload.get("frequency"),
        retention_count=payload.get("retention_count"),
        hour_utc=payload.get("hour_utc"),
    )
    await db.commit()
    return env(backup_svc.serialize_settings(row), "Backup settings updated")


@api.get("/backup")
async def backup_list(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = await backup_svc.list_backups(db, claims["tenant_id"])
    return env([backup_svc.serialize_job(r) for r in rows])


@api.post("/backup")
async def backup_create(
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    backup_svc.ensure_backup_dir_writable()
    notes = (payload or {}).get("notes")
    job = await backup_svc.create_backup(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        notes=notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="backup",
        action="create",
        entity="backup_job",
        entity_id=job.id,
        details={"filename": job.filename, "size_bytes": job.size_bytes, "checksum": job.checksum_sha256},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(backup_svc.serialize_job(job), "Backup created")


@api.post("/backup/run-due")
async def backup_run_due(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Run a backup when schedule is enabled and due (manual/cron trigger)."""
    result = await backup_svc.run_scheduled_backup_if_due(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub")
    )
    await db.commit()
    if result.get("ran"):
        return env(result, "Scheduled backup created")
    return env(result)


@api.get("/backup/{backup_id}")
async def backup_get(
    backup_id: str,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    job = await backup_svc.get_backup(db, claims["tenant_id"], backup_id)
    return env(backup_svc.serialize_job(job))


@api.get("/backup/{backup_id}/download")
async def backup_download(
    backup_id: str,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    job = await backup_svc.get_backup(db, claims["tenant_id"], backup_id)
    data = await backup_svc.read_backup_bytes(job)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="backup",
        action="download",
        entity="backup_job",
        entity_id=job.id,
        details={"filename": job.filename, "checksum": job.checksum_sha256},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{job.filename}"',
            "X-Checksum-SHA256": job.checksum_sha256,
        },
    )


@api.post("/backup/{backup_id}/restore")
async def backup_restore(
    backup_id: str,
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    body = payload or {}
    dry_run = bool(body.get("dry_run", True))
    confirm = bool(body.get("confirm", False))
    if confirm and not dry_run and body.get("confirm_text") != "RESTORE":
        raise HTTPException(
            status_code=400,
            detail='Destructive restore requires confirm=true, dry_run=false, and confirm_text="RESTORE"',
        )
    report = await backup_svc.restore_backup(
        db,
        tenant_id=claims["tenant_id"],
        backup_id=backup_id,
        dry_run=dry_run or not confirm,
        confirm=confirm and not dry_run,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="backup",
        action="restore_dry_run" if report.get("dry_run") else "restore_apply",
        entity="backup_job",
        entity_id=backup_id,
        details={"applied": report.get("applied"), "counts": report.get("record_counts")},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    msg = "Restore dry-run completed" if report.get("dry_run") else "Restore applied"
    return env(report, msg)


@api.post("/ai/chat")
async def ai_chat(payload: dict, claims=Depends(require_permission("ai", "write"))):
    raise HTTPException(
        status_code=503,
        detail="AI Business Assistant is not configured. Configure an approved AI provider before enabling this feature.",
    )


@api.get("/ai/insights")
async def insights(claims=Depends(require_permission("ai", "read")), db: AsyncSession = Depends(get_db)):
    dash = (await dashboard(claims, db))["data"]
    notes = []
    if dash["low_stock"] > 0:
        notes.append(f"{dash['low_stock']} product(s) are at or below reorder level.")
    if dash["total_expenses"] > dash["total_sales"] and dash["total_sales"] > 0:
        notes.append("Expenses currently exceed recorded sales.")
    return env(
        {
            "insights": notes
            or ["No urgent anomaly detected from the currently configured business rules."]
        }
    )
