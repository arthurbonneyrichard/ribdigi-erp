from __future__ import annotations

from datetime import datetime, timedelta

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
    normalize_record_scope,
    permissions_for_role,
    record_scope_from_permissions,
    serialize_user,
)
from app import roles as roles_svc
from app import org_units as org_units_svc
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
from app import user_import as user_import_svc
from app import product_lookup as product_lookup_svc
from app import stock_import as stock_import_svc
from app import barcode_labels as barcode_labels_svc
from app import suppliers as suppliers_svc
from app import customers as customers_svc
from app import ai_chat as ai_chat_svc
from app.config import settings
from app.schemas import (
    BarcodeLabelPrintRequest,
    BrandCreate,
    BrandUpdate,
    CreditLimitUpdate,
    CreditLimitOverrideRequest,
    CustomerPaymentCreate,
    EarlyPaySettingsUpdate,
    EmailVerifyConfirm,
    EmailVerificationResend,
    ExchangeRateRefresh,
    ExchangeRateUpsert,
    FxAutoRefreshUpdate,
    BankConnectionCreate,
    BankConnectionUpdate,
    ExpenseCategoryCreate,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseDecision,
    ExpenseThresholdUpdate,
    ExpenseUpdate,
    GrnCreate,
    JournalCreate,
    CoaAccountCreate,
    CoaAccountUpdate,
    OpeningBalanceCreate,
    LiquidAccountCreate,
    LiquidAccountUpdate,
    LiquidTransferCreate,
    Login,
    NotificationPreferencesUpdate,
    CustomerContactCreate,
    CustomerCreate,
    CustomerGroupCreate,
    CustomerGroupUpdate,
    CustomerUpdate,
    SupplierContactCreate,
    SupplierCreate,
    SupplierUpdate,
    PasswordResetConfirm,
    ChangePasswordRequest,
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
    RecurringExpenseUpdate,
    RefreshRequest,
    SalesInvoiceCreate,
    SalesOrderCreate,
    SalesOrderUpdate,
    SalesQuotationCreate,
    SalesReturnCreate,
    InvoiceSendRequest,
    SmsTestRequest,
    OpeningStockRequest,
    StockAdjust,
    StockMove,
    StockTransferCreate,
    WarehouseStockTransferCreate,
    LowStockReorderPoCreate,
    StoreCreate,
    StoreUpdate,
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
    EmailSettingsUpdate,
    TwoFactorConfirm,
    TwoFactorDisable,
    TwoFactorVerify,
    WebAuthnLoginOptions,
    WebAuthnLoginVerify,
    WebAuthnRegisterVerify,
    UserCreate,
    UserUpdate,
    CustomRoleCreate,
    CustomRoleUpdate,
    CustomRolePermissionsUpdate,
    BranchCreate,
    BranchUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    ProductUpdate,
    StockCountCreate,
    StockCountItemsUpdate,
    WarehouseCreate,
    WarehouseUpdate,
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
    await customers_svc.ensure_default_customer_groups(db, tenant_id)
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


def _assert_email_verified(user: m.User) -> None:
    """BR-19.1: email must be verified before first login."""
    if not bool(user.email_verified):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "EMAIL_NOT_VERIFIED",
                "message": "Email address is not verified. Check your inbox or request a new verification email.",
            },
        )


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
        timezone=(payload.timezone or "Africa/Accra").strip() or "Africa/Accra",
        tax_jurisdiction=(payload.tax_jurisdiction or "GH").strip().upper() or "GH",
        status="trial",
        trial_ends_at=tenants_svc.default_trial_ends_at(),
        trial_notices={},
    )
    db.add(tenant)
    await db.flush()

    admin_name = (payload.admin_full_name or "Company Administrator").strip() or "Company Administrator"
    admin = m.User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        full_name=admin_name,
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
    previous_plan = (getattr(tenant, "plan_code", None) or "trial").strip().lower()
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
        document_numbering=(
            payload.document_numbering.model_dump(exclude_unset=True)
            if payload.document_numbering is not None
            else None
        ),
        invoice_print_template=payload.invoice_print_template,
        receipt_print_template=payload.receipt_print_template,
        document_header=payload.document_header,
        document_footer=payload.document_footer,
        plan_code=payload.plan_code,
        legal_name=payload.legal_name,
        registration_number=payload.registration_number,
        billing_address=payload.billing_address,
        shipping_address=payload.shipping_address,
        warehouse_address=payload.warehouse_address,
        contact_person_name=payload.contact_person_name,
        contact_person_email=(
            str(payload.contact_person_email) if payload.contact_person_email is not None else None
        ),
        contact_person_phone=payload.contact_person_phone,
        inactivity_timeout_minutes=payload.inactivity_timeout_minutes,
        date_format=payload.date_format,
        number_format=payload.number_format,
        time_format=payload.time_format,
    )
    new_plan = (getattr(tenant, "plan_code", None) or "trial").strip().lower()
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="profile_update",
        entity="tenant",
        entity_id=tenant.id,
        details={"company_name": tenant.company_name, "plan_code": new_plan},
    )
    if payload.plan_code is not None and new_plan != previous_plan:
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="tenants",
            action="plan_code_changed",
            entity="tenant",
            entity_id=tenant.id,
            details={
                "from": previous_plan,
                "to": new_plan,
                "billing_deferred": True,
                "payment_processed": False,
            },
        )
    await db.commit()
    data = tenants_svc.serialize_tenant(tenant)
    msg = "Company profile updated"
    if payload.plan_code is not None and new_plan != previous_plan:
        msg = "Plan metadata updated (billing deferred; no payment processed)"
    return env(data, msg)


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
    db: AsyncSession = Depends(get_db),
):
    from app import emailer

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(emailer.email_status(tenant))


@api.patch("/settings/email")
async def settings_email_update(
    payload: EmailSettingsUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import emailer

    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    tenant = await tenants_svc.update_smtp_settings(
        db,
        tenant,
        smtp_enabled=payload.smtp_enabled,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port,
        smtp_username=payload.smtp_username,
        smtp_password=payload.smtp_password,
        clear_password=payload.clear_password,
        smtp_from_email=str(payload.smtp_from_email) if payload.smtp_from_email is not None else None,
        smtp_from_name=payload.smtp_from_name,
        smtp_use_tls=payload.smtp_use_tls,
        smtp_use_ssl=payload.smtp_use_ssl,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="settings",
        action="email_settings_update",
        entity="tenant",
        entity_id=tenant.id,
        details={
            "smtp_enabled": tenant.smtp_enabled,
            "smtp_host": tenant.smtp_host,
            "smtp_from_email": tenant.smtp_from_email,
        },
    )
    await db.commit()
    return env(emailer.email_status(tenant), "Email settings updated")


@api.post("/settings/email/test")
async def settings_email_test(
    payload: EmailTestRequest | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import emailer

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    user = await db.get(m.User, claims["sub"])
    to = str(payload.to) if payload and payload.to else (user.email if user else None)
    if not to:
        raise HTTPException(status_code=400, detail="No recipient email available")
    result = await emailer.send_test_email(to=to, tenant=tenant)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="settings",
        action="email_test",
        entity="email",
        details={"to": to, "sent": result.sent, "mode": result.mode, "source": emailer.resolve_smtp_config(tenant).get("source")},
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

    if not bool(user.email_verified):
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            module="auth",
            action="login_blocked_unverified",
            entity="user",
            entity_id=user.id,
            details={"email": user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        await db.commit()
        _assert_email_verified(user)

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
    _assert_email_verified(user)
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
    _assert_email_verified(user)
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


@api.post("/auth/idle-logout")
async def idle_logout(
    request: Request,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Server-side revoke of the current session after client inactivity (BR-19.3)."""
    jti = claims.get("jti")
    revoked = False
    session_id = None
    if jti:
        session = (
            await db.execute(
                select(m.AuthSession).where(
                    m.AuthSession.jti == jti,
                    m.AuthSession.tenant_id == claims["tenant_id"],
                    m.AuthSession.user_id == claims["sub"],
                )
            )
        ).scalar_one_or_none()
        if session and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
            revoked = True
            session_id = session.id
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="idle_logout",
        entity="auth_session",
        entity_id=session_id,
        details={"jti": jti, "revoked": revoked},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env({"revoked": revoked}, "Session ended due to inactivity")


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
async def revoke_session(
    session_id: str,
    request: Request,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
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
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="auth",
        action="session_revoked",
        entity="auth_session",
        entity_id=session_id,
        details={"jti": session.jti},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env({"id": session_id, "revoked": True})


@api.post("/auth/password-reset-request")
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            module="auth",
            action="password_reset_request",
            entity="user",
            entity_id=user.id,
            details={"email": user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
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
async def password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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

    await audit_svc.record_event(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        module="auth",
        action="password_reset",
        entity="user",
        entity_id=user.id,
        details={"sessions_revoked": len(sessions), "email": user.email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env({"reset": True})


@api.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Authenticated password change (BR-19.1 password management)."""
    tenants_svc.assert_writable(claims)
    user = await db.get(m.User, claims["sub"])
    if not user or user.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    if not verify_password(payload.current_password, user.password_hash):
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=user.id,
            module="auth",
            action="password_change_failed",
            entity="user",
            entity_id=user.id,
            details={"reason": "bad_current_password"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        await db.commit()
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password",
        )
    validate_password_strength(payload.new_password)
    user.password_hash = hash_password(payload.new_password)

    current_jti = claims.get("jti")
    sessions = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.user_id == user.id,
                m.AuthSession.tenant_id == claims["tenant_id"],
                m.AuthSession.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    revoked = 0
    for session in sessions:
        if current_jti and session.jti == current_jti:
            continue
        session.revoked_at = datetime.utcnow()
        revoked += 1

    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=user.id,
        module="auth",
        action="password_changed",
        entity="user",
        entity_id=user.id,
        details={"sessions_revoked": revoked},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        {"changed": True, "sessions_revoked": revoked},
        "Password updated; other sessions revoked",
    )


@api.post("/auth/verify-email")
async def verify_email(
    payload: EmailVerifyConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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
    await audit_svc.record_event(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        module="auth",
        action="email_verified",
        entity="user",
        entity_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env({"verified": True}, "Email verified")


@api.post("/auth/resend-verification")
async def resend_verification(
    payload: EmailVerificationResend,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Re-issue email verification token (tenant-scoped; no existence leak)."""
    try:
        tenant = await tenants_svc.resolve_tenant(db, payload.tenant_id)
    except HTTPException:
        return env({"requested": True}, "If the account exists, a verification email was sent")
    user = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant.id,
                m.User.email == str(payload.email),
            )
        )
    ).scalar_one_or_none()
    data: dict = {"requested": True}
    if user and user.is_active and not bool(user.email_verified):
        raw, token_hash, expires = issue_one_time_token()
        db.add(
            m.AuthToken(
                tenant_id=tenant.id,
                user_id=user.id,
                purpose="email_verify",
                token_hash=token_hash,
                expires_at=expires,
            )
        )
        await audit_svc.record_event(
            db,
            tenant_id=tenant.id,
            user_id=user.id,
            module="auth",
            action="email_verification_resent",
            entity="user",
            entity_id=user.id,
            details={"email": user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        await db.commit()
        from app import emailer

        email_result = await emailer.send_verification_email(
            to=user.email, token=raw, company_name=tenant.company_name
        )
        data["email"] = {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        }
        if settings.DEBUG or settings.APP_ENV.lower() != "production":
            data["email_verification_token"] = raw
    return env(data, "If the account exists, a verification email was sent")


@api.get("/me")
async def me(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    user = await db.get(m.User, claims["sub"])
    if isinstance(user.permissions, dict) and user.permissions:
        perms = user.permissions
    elif user.role in VALID_ROLES:
        perms = permissions_for_role(user.role)
    else:
        perms = await roles_svc.permissions_for_assignment(db, user.tenant_id, user.role)
    tenant = await db.get(m.Tenant, claims["tenant_id"])
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
            "inactivity_timeout_minutes": int(
                getattr(tenant, "inactivity_timeout_minutes", None) or 30
            )
            if tenant
            else 30,
            "date_format": (getattr(tenant, "date_format", None) or "DD/MM/YYYY") if tenant else "DD/MM/YYYY",
            "number_format": (getattr(tenant, "number_format", None) or "1,234.56") if tenant else "1,234.56",
            "time_format": (getattr(tenant, "time_format", None) or "24h") if tenant else "24h",
            "timezone": (getattr(tenant, "timezone", None) or "Africa/Accra") if tenant else "Africa/Accra",
            # ADR-006 / BR-2.7 — English MVP; i18n scaffold on frontend
            "locale": "en",
            "preferred_language": "en",
            "supported_locales": ["en"],
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
    if payload.preferred_language is not None:
        lang = payload.preferred_language.strip().lower()
        if lang != "en":
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "LOCALE_UNSUPPORTED",
                    "message": "Only English (en) is available in the commercial MVP. Additional language packs are deferred (ADR-006).",
                    "supported_locales": ["en"],
                },
            )
    await db.commit()
    return env(
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
            "locale": "en",
            "preferred_language": "en",
            "supported_locales": ["en"],
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
async def roles_catalog(
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await roles_svc.list_role_catalog(db, claims["tenant_id"]))


@api.get("/roles/{role}")
async def role_detail(
    role: str,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    if role in VALID_ROLES:
        return env(roles_svc.role_detail_payload(role))
    custom = await roles_svc.get_custom_role(db, claims["tenant_id"], role)
    return env(roles_svc.serialize_custom_role(custom))


@api.post("/roles")
async def create_custom_role(
    payload: CustomRoleCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    try:
        row = await roles_svc.create_custom_role(
            db,
            tenant_id=claims["tenant_id"],
            slug=payload.slug,
            label=payload.label,
            description=payload.description,
            base_role=payload.base_role,
            permissions=payload.permissions,
            record_scope=payload.record_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="custom_role_created",
        entity="custom_role",
        entity_id=row.id,
        details={"slug": row.slug, "label": row.label},
    )
    await db.commit()
    return env(roles_svc.serialize_custom_role(row), "Custom role created")


@api.patch("/roles/{role}")
async def update_custom_role(
    role: str,
    payload: CustomRoleUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    if role in VALID_ROLES:
        raise HTTPException(status_code=400, detail="System roles cannot be modified")
    try:
        row = await roles_svc.update_custom_role(
            db,
            tenant_id=claims["tenant_id"],
            slug=role,
            label=payload.label,
            description=payload.description,
            permissions=payload.permissions,
            record_scope=payload.record_scope,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="custom_role_updated",
        entity="custom_role",
        entity_id=row.id,
        details={"slug": row.slug},
    )
    await db.commit()
    return env(roles_svc.serialize_custom_role(row), "Custom role updated")


@api.put("/roles/{role}/permissions")
async def put_custom_role_permissions(
    role: str,
    payload: CustomRolePermissionsUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    if role in VALID_ROLES:
        raise HTTPException(status_code=400, detail="System roles cannot be modified")
    try:
        row = await roles_svc.update_custom_role(
            db,
            tenant_id=claims["tenant_id"],
            slug=role,
            permissions=payload.permissions,
            record_scope=payload.record_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="custom_role_permissions_updated",
        entity="custom_role",
        entity_id=row.id,
        details={"slug": row.slug},
    )
    await db.commit()
    return env(roles_svc.serialize_custom_role(row), "Role permissions updated")


@api.delete("/roles/{role}")
async def delete_custom_role(
    role: str,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    if role in VALID_ROLES:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")
    custom = await roles_svc.get_custom_role(db, claims["tenant_id"], role)
    role_id = custom.id
    await roles_svc.delete_custom_role(db, tenant_id=claims["tenant_id"], slug=role)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="custom_role_deleted",
        entity="custom_role",
        entity_id=role_id,
        details={"slug": role},
    )
    await db.commit()
    return env({"role": role}, "Custom role deleted")


@api.get("/branches")
async def list_branches(
    active_only: bool = False,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await org_units_svc.list_branches(
        db, claims["tenant_id"], active_only=active_only
    )
    return env([org_units_svc.serialize_branch(r) for r in rows])


@api.post("/branches")
async def create_branch(
    payload: BranchCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    row = await org_units_svc.create_branch(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        address=payload.address,
        phone=payload.phone,
        email=str(payload.email) if payload.email is not None else None,
        manager_id=payload.manager_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="branch_created",
        entity="branch",
        entity_id=row.id,
        details={"code": row.code},
    )
    await db.commit()
    return env(org_units_svc.serialize_branch(row), "Branch created")


@api.patch("/branches/{branch_id}")
async def update_branch(
    branch_id: str,
    payload: BranchUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    row = await org_units_svc.update_branch(
        db,
        tenant_id=claims["tenant_id"],
        branch_id=branch_id,
        name=payload.name,
        address=payload.address,
        phone=payload.phone,
        email=str(payload.email) if payload.email is not None else None,
        manager_id=payload.manager_id,
        clear_manager=payload.clear_manager,
        is_active=payload.is_active,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="branch_updated",
        entity="branch",
        entity_id=row.id,
        details={"code": row.code, "is_active": bool(row.is_active)},
    )
    await db.commit()
    return env(org_units_svc.serialize_branch(row), "Branch updated")


@api.get("/departments")
async def list_departments(
    branch_id: str | None = None,
    active_only: bool = False,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await org_units_svc.list_departments(
        db, claims["tenant_id"], branch_id=branch_id, active_only=active_only
    )
    return env([org_units_svc.serialize_department(r) for r in rows])


@api.post("/departments")
async def create_department(
    payload: DepartmentCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    row = await org_units_svc.create_department(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        branch_id=payload.branch_id,
        head_user_id=payload.head_user_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="department_created",
        entity="department",
        entity_id=row.id,
        details={"code": row.code},
    )
    await db.commit()
    return env(org_units_svc.serialize_department(row), "Department created")


@api.patch("/departments/{department_id}")
async def update_department(
    department_id: str,
    payload: DepartmentUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    row = await org_units_svc.update_department(
        db,
        tenant_id=claims["tenant_id"],
        department_id=department_id,
        name=payload.name,
        branch_id=payload.branch_id,
        clear_branch=payload.clear_branch,
        head_user_id=payload.head_user_id,
        clear_head=payload.clear_head,
        is_active=payload.is_active,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="department_updated",
        entity="department",
        entity_id=row.id,
        details={"code": row.code, "is_active": bool(row.is_active)},
    )
    await db.commit()
    return env(org_units_svc.serialize_department(row), "Department updated")


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
    role = await roles_svc.assert_assignable_role(
        db, claims["tenant_id"], payload.role, actor_role=claims.get("role")
    )
    validate_password_strength(payload.password)
    branch_id, department_id = await org_units_svc.assert_user_org_assignment(
        db,
        claims["tenant_id"],
        branch_id=payload.branch_id,
        department_id=payload.department_id,
    )
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
    perms = await roles_svc.permissions_for_assignment(db, claims["tenant_id"], role)
    if payload.record_scope is not None:
        try:
            perms[RECORD_SCOPE_KEY] = normalize_record_scope(payload.record_scope)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = m.User(
        tenant_id=claims["tenant_id"],
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=role,
        branch_id=branch_id,
        department_id=department_id,
        permissions=perms,
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


@api.get("/users/import/template")
async def users_import_template(
    claims=Depends(require_permission("users", "read")),
):
    text = user_import_svc.template_csv()
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="user_import_template.csv"'},
    )


@api.post("/users/import")
async def users_import(
    file: UploadFile = File(...),
    dry_run: bool = True,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")
    result = await user_import_svc.import_users_csv(
        db,
        tenant_id=claims["tenant_id"],
        actor_id=claims["sub"],
        actor_role=claims.get("role"),
        content=content,
        dry_run=dry_run,
    )
    if not dry_run and result["valid_rows"]:
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="users",
            action="user_import",
            entity="user",
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
        "Dry-run complete" if dry_run else f"Imported {result['valid_rows']} users",
    )


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
        new_role = await roles_svc.assert_assignable_role(
            db, claims["tenant_id"], payload.role, actor_role=claims.get("role")
        )
        if user.id == claims["sub"] and new_role != user.role:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        if user.role != new_role:
            changes["role"] = {"from": user.role, "to": new_role}
            prev_scope = None
            if isinstance(user.permissions, dict):
                prev_scope = user.permissions.get(RECORD_SCOPE_KEY)
            user.role = new_role
            perms = await roles_svc.permissions_for_assignment(db, claims["tenant_id"], new_role)
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

    if payload.clear_branch or payload.clear_department or payload.branch_id is not None or payload.department_id is not None:
        next_branch = None if payload.clear_branch else (
            payload.branch_id if payload.branch_id is not None else user.branch_id
        )
        next_dept = None if payload.clear_department else (
            payload.department_id if payload.department_id is not None else user.department_id
        )
        branch_id, department_id = await org_units_svc.assert_user_org_assignment(
            db,
            claims["tenant_id"],
            branch_id=next_branch,
            department_id=next_dept,
        )
        if user.branch_id != branch_id:
            user.branch_id = branch_id
            changes["branch_id"] = branch_id
        if user.department_id != department_id:
            user.department_id = department_id
            changes["department_id"] = department_id

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
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 1:
        prior_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        prior_month_start = month_start.replace(month=month_start.month - 1)
    expiry_horizon = now + timedelta(days=30)

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
    # Prefer posted sales invoices for purchases when purchase txs unused.
    if float(purchases) == 0:
        purchases = await scalar(
            select(func.coalesce(func.sum(m.PurchaseInvoice.total_amount), 0)).where(
                m.PurchaseInvoice.tenant_id == tid,
                m.PurchaseInvoice.status.in_(["unpaid", "partial", "paid", "overdue"]),
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
    out_of_stock = await scalar(
        select(func.count(m.Product.id)).where(
            m.Product.tenant_id == tid,
            m.Product.stock_qty <= 0,
        )
    )
    expiring_batches = await scalar(
        select(func.count(m.ProductBatch.id)).where(
            m.ProductBatch.tenant_id == tid,
            m.ProductBatch.expiry_date.is_not(None),
            m.ProductBatch.expiry_date >= now,
            m.ProductBatch.expiry_date <= expiry_horizon,
            m.ProductBatch.quantity > 0,
        )
    )
    customers = await scalar(
        select(func.count(m.Party.id)).where(m.Party.tenant_id == tid, m.Party.kind == "customer")
    )
    suppliers = await scalar(
        select(func.count(m.Party.id)).where(m.Party.tenant_id == tid, m.Party.kind == "supplier")
    )
    daily_revenue = await scalar(
        select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
            m.Transaction.tenant_id == tid,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
            m.Transaction.created_at >= day_start,
        )
    )
    monthly_revenue = await scalar(
        select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
            m.Transaction.tenant_id == tid,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
            m.Transaction.created_at >= month_start,
        )
    )
    prior_month_revenue = await scalar(
        select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
            m.Transaction.tenant_id == tid,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
            m.Transaction.created_at >= prior_month_start,
            m.Transaction.created_at < month_start,
        )
    )
    # Also include posted invoice totals for the day/month when POS txs alone understate sales.
    inv_daily = await scalar(
        select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
            m.SalesInvoice.tenant_id == tid,
            m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
            m.SalesInvoice.posted_at >= day_start,
        )
    )
    inv_monthly = await scalar(
        select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
            m.SalesInvoice.tenant_id == tid,
            m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
            m.SalesInvoice.posted_at >= month_start,
        )
    )
    inv_prior = await scalar(
        select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
            m.SalesInvoice.tenant_id == tid,
            m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
            m.SalesInvoice.posted_at >= prior_month_start,
            m.SalesInvoice.posted_at < month_start,
        )
    )
    daily_revenue = float(daily_revenue) + float(inv_daily)
    monthly_revenue = float(monthly_revenue) + float(inv_monthly)
    prior_month_revenue = float(prior_month_revenue) + float(inv_prior)
    mom_change_pct = None
    if prior_month_revenue > 0:
        mom_change_pct = round(((monthly_revenue - prior_month_revenue) / prior_month_revenue) * 100, 2)

    recent_sales = (
        await db.execute(
            select(m.Transaction)
            .where(
                m.Transaction.tenant_id == tid,
                m.Transaction.tx_type.in_(["sale", "pos_sale"]),
            )
            .order_by(m.Transaction.created_at.desc())
            .limit(8)
        )
    ).scalars().all()
    recent_invoices = (
        await db.execute(
            select(m.SalesInvoice)
            .where(
                m.SalesInvoice.tenant_id == tid,
                m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
            )
            .order_by(m.SalesInvoice.posted_at.desc())
            .limit(8)
        )
    ).scalars().all()
    recent = [
        *[
            {
                "source": "pos",
                "reference": t.reference,
                "total": float(t.total or 0),
                "at": t.created_at,
            }
            for t in recent_sales
        ],
        *[
            {
                "source": "invoice",
                "reference": inv.invoice_number,
                "total": float(inv.total_amount or 0),
                "at": inv.posted_at or inv.created_at,
            }
            for inv in recent_invoices
        ],
    ]
    recent.sort(key=lambda r: r.get("at") or datetime.min, reverse=True)
    recent = recent[:10]

    top_rows = (
        await db.execute(
            select(
                m.Product.id,
                m.Product.name,
                m.Product.sku,
                func.coalesce(func.sum(m.SalesInvoiceItem.quantity), 0).label("qty"),
                func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).label("revenue"),
            )
            .join(m.SalesInvoiceItem, m.SalesInvoiceItem.product_id == m.Product.id)
            .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
            .where(
                m.Product.tenant_id == tid,
                m.SalesInvoice.tenant_id == tid,
                m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
            )
            .group_by(m.Product.id, m.Product.name, m.Product.sku)
            .order_by(func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).desc())
            .limit(5)
        )
    ).all()
    top_products = [
        {
            "id": row.id,
            "name": row.name,
            "sku": row.sku,
            "quantity": float(row.qty or 0),
            "revenue": float(row.revenue or 0),
        }
        for row in top_rows
    ]

    from app import dashboard_charts as dashboard_charts_svc

    chart_series = await dashboard_charts_svc.load_revenue_chart_series(
        db, tenant_id=tid, now=now
    )

    return env(
        {
            "total_sales": float(sales) + float(
                await scalar(
                    select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                        m.SalesInvoice.tenant_id == tid,
                        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
                    )
                )
            ),
            "total_purchases": float(purchases),
            "total_expenses": float(expenses),
            "products": products,
            "low_stock": low,
            "out_of_stock": out_of_stock,
            "expiring_batches": expiring_batches,
            "customers": customers,
            "suppliers": suppliers,
            "daily_revenue": daily_revenue,
            "monthly_revenue": monthly_revenue,
            "prior_month_revenue": prior_month_revenue,
            "mom_change_pct": mom_change_pct,
            "recent_sales": recent,
            "top_products": top_products,
            "daily_revenue_series": chart_series["daily_revenue_series"],
            "monthly_revenue_series": chart_series["monthly_revenue_series"],
            # BR-4.1 click-through targets (Stage 1 F17)
            "kpi_links": {
                "total_sales": "/sales?tab=invoices",
                "total_purchases": "/purchasing?tab=invoices",
                "total_expenses": "/expenses",
                "customers": "/sales?tab=customers",
                "suppliers": "/purchasing?tab=suppliers",
                "products": "/inventory?tab=products",
                "low_stock": "/inventory?tab=lowstock",
                "out_of_stock": "/inventory?tab=lowstock",
                "expiring_batches": "/inventory?tab=expiry",
                "daily_revenue": "/reports?tab=sales",
                "monthly_revenue": "/reports?tab=sales",
                "prior_month_revenue": "/reports?tab=sales",
                "mom_change_pct": "/reports?tab=sales",
            },
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
        elif key in {"cost_price", "selling_price", "reorder_level", "minimum_stock"} and value is not None:
            setattr(product, key, float(value))
        elif key in {"weight", "length", "width", "height"}:
            if value is None:
                setattr(product, key, None)
            else:
                num = float(value)
                if num < 0:
                    raise HTTPException(status_code=400, detail=f"{key} cannot be negative")
                setattr(product, key, num)
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


@api.post("/catalog/brands/{brand_id}/logo")
async def catalog_brand_logo_upload(
    brand_id: str,
    file: UploadFile = File(...),
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    brand = await catalog_meta_svc.get_brand(db, claims["tenant_id"], brand_id)
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="brand_logos",
        upload=file,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    if brand.logo_url:
        storage_svc.delete_key(brand.logo_url, tenant_id=claims["tenant_id"])
    brand.logo_url = stored.key
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="brand_logo_upload",
        entity="brand",
        entity_id=brand.id,
        details={"key": stored.key, "size": stored.size, "content_type": stored.content_type},
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_brand(brand), "Brand logo uploaded")


@api.get("/catalog/brands/{brand_id}/logo")
async def catalog_brand_logo_get(
    brand_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    brand = await catalog_meta_svc.get_brand(db, claims["tenant_id"], brand_id)
    if not brand.logo_url:
        raise HTTPException(status_code=404, detail="No brand logo uploaded")
    return storage_svc.media_response(brand.logo_url, tenant_id=claims["tenant_id"])


@api.delete("/catalog/brands/{brand_id}/logo")
async def catalog_brand_logo_delete(
    brand_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    brand = await catalog_meta_svc.get_brand(db, claims["tenant_id"], brand_id)
    if not brand.logo_url:
        raise HTTPException(status_code=404, detail="No brand logo uploaded")
    storage_svc.delete_key(brand.logo_url, tenant_id=claims["tenant_id"])
    brand.logo_url = None
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="brand_logo_delete",
        entity="brand",
        entity_id=brand.id,
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_brand(brand), "Brand logo removed")


@api.get("/catalog/units")
async def catalog_units(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    rows = await catalog_meta_svc.list_units(db, claims["tenant_id"])
    return env([catalog_meta_svc.serialize_unit(r) for r in rows])


@api.get("/catalog/units/convert")
async def catalog_convert_units(
    from_unit_id: str,
    to_unit_id: str,
    quantity: float = 1,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    result = await catalog_meta_svc.convert_quantity(
        db,
        tenant_id=claims["tenant_id"],
        from_unit_id=from_unit_id,
        to_unit_id=to_unit_id,
        quantity=quantity,
    )
    return env(result)


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
        base_unit_id=payload.base_unit_id,
        conversion_factor=payload.conversion_factor,
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
        base_unit_id=data.get("base_unit_id"),
        conversion_factor=data.get("conversion_factor"),
        is_active=data.get("is_active"),
        clear_base_unit=bool(data.get("clear_base_unit")),
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
    from app.inventory import compute_stock_status, effective_warehouse_thresholds

    products = (
        await db.execute(
            select(m.Product)
            .where(
                m.Product.tenant_id == claims["tenant_id"],
                m.Product.is_active == True,  # noqa: E712,
            )
            .order_by(m.Product.stock_qty.asc())
        )
    ).scalars().all()
    out: list[dict] = []
    for p in products:
        qty = float(p.stock_qty or 0)
        minimum = float(getattr(p, "minimum_stock", 0) or 0)
        reorder = float(p.reorder_level or 0)
        status = compute_stock_status(qty, minimum, reorder)
        if status == "green":
            continue
        out.append(
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "stock_qty": qty,
                "minimum_stock": minimum,
                "reorder_level": reorder,
                "stock_status": status,
                "cost_price": float(p.cost_price or 0),
                "scope": "product",
                "warehouse_id": None,
                "suggested_order_qty": max(
                    1.0,
                    round(reorder - qty, 3) if reorder > qty else max(reorder, 1.0),
                ),
            }
        )

    wh_rows = (
        await db.execute(
            select(m.WarehouseStock, m.Product, m.Warehouse)
            .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
            .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
            .where(
                m.WarehouseStock.tenant_id == claims["tenant_id"],
                m.Product.is_active == True,  # noqa: E712
            )
            .order_by(m.WarehouseStock.quantity.asc())
        )
    ).all()
    for stock, product, wh in wh_rows:
        qty = float(stock.quantity or 0)
        minimum, reorder = effective_warehouse_thresholds(stock, product)
        status = compute_stock_status(qty, minimum, reorder)
        if status == "green":
            continue
        # Skip duplicate when warehouse has no local policy and product already listed
        w_min = float(getattr(stock, "minimum_stock", 0) or 0)
        w_ro = float(stock.reorder_level or 0)
        if w_min <= 0 and w_ro <= 0:
            continue
        out.append(
            {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_qty": qty,
                "minimum_stock": minimum,
                "reorder_level": reorder,
                "stock_status": status,
                "cost_price": float(product.cost_price or 0),
                "scope": "warehouse",
                "warehouse_id": wh.id,
                "warehouse_code": wh.code,
                "suggested_order_qty": max(
                    1.0,
                    float(stock.reorder_qty or 0)
                    or (round(reorder - qty, 3) if reorder > qty else max(reorder, 1.0)),
                ),
            }
        )
    return env(out)


@api.post("/inventory/low-stock/reorder-po")
async def low_stock_reorder_po(
    payload: LowStockReorderPoCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft purchase order from a low-stock product suggestion."""
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == payload.product_id,
                m.Product.tenant_id == claims["tenant_id"],
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    supplier = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == payload.supplier_id,
                m.Party.tenant_id == claims["tenant_id"],
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if payload.warehouse_id:
        from app.inventory import get_warehouse

        await get_warehouse(db, claims["tenant_id"], payload.warehouse_id)

    suggested = max(
        1.0,
        round(float(product.reorder_level or 0) - float(product.stock_qty or 0), 3)
        if float(product.reorder_level or 0) > float(product.stock_qty or 0)
        else max(float(product.reorder_level or 0), 1.0),
    )
    qty = float(payload.quantity) if payload.quantity is not None else suggested
    if qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    unit_price = (
        float(payload.unit_price)
        if payload.unit_price is not None
        else float(product.cost_price or 0)
    )
    po = await purchasing_svc.create_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        supplier_id=supplier.id,
        warehouse_id=payload.warehouse_id,
        notes=payload.notes or f"Reorder from low stock: {product.sku}",
        items=[{"product_id": product.id, "quantity": qty, "unit_price": unit_price}],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="low_stock_reorder_po",
        entity="purchase_order",
        entity_id=po.id,
        details={
            "product_id": product.id,
            "sku": product.sku,
            "quantity": qty,
            "supplier_id": supplier.id,
            "po_number": po.po_number,
        },
    )
    await db.commit()
    return env(await purchasing_svc.serialize_po(db, po), "Draft purchase order created from low stock")


@api.get("/inventory/movements")
async def movements(
    product_id: str | None = None,
    warehouse_id: str | None = None,
    movement_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import reports as reports_svc
    from app.inventory import list_movements_serialized

    rows = await list_movements_serialized(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        from_dt=reports_svc.parse_date(from_date),
        to_dt=reports_svc.parse_date(to_date, end_of_day=True),
        limit=200,
    )
    return env(rows)


@api.get("/products/{product_id}/warehouse-stock")
async def product_warehouse_stock(
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
    rows = (
        await db.execute(
            select(m.WarehouseStock, m.Warehouse)
            .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
            .where(
                m.WarehouseStock.tenant_id == claims["tenant_id"],
                m.WarehouseStock.product_id == product_id,
            )
            .order_by(m.Warehouse.code)
        )
    ).all()
    from app.inventory import compute_stock_status, effective_warehouse_thresholds

    p_min = float(getattr(product, "minimum_stock", 0) or 0)
    p_ro = float(product.reorder_level or 0)
    p_qty = float(product.stock_qty or 0)
    warehouses_out = []
    for stock, wh in rows:
        qty = float(stock.quantity or 0)
        minimum, reorder = effective_warehouse_thresholds(stock, product)
        warehouses_out.append(
            {
                "warehouse_id": wh.id,
                "code": wh.code,
                "name": wh.name,
                "quantity": qty,
                "reserved_qty": float(getattr(stock, "reserved_qty", 0) or 0),
                "available_qty": max(qty - float(getattr(stock, "reserved_qty", 0) or 0), 0.0),
                "minimum_stock": minimum,
                "reorder_level": reorder,
                "stock_status": compute_stock_status(qty, minimum, reorder),
                "reorder_qty": float(stock.reorder_qty or 0),
            }
        )
    return env(
        {
            "product_id": product.id,
            "stock_qty": p_qty,
            "minimum_stock": p_min,
            "reorder_level": p_ro,
            "stock_status": compute_stock_status(p_qty, p_min, p_ro),
            "reserved_qty": float(getattr(product, "reserved_qty", 0) or 0),
            "available_qty": max(p_qty - float(getattr(product, "reserved_qty", 0) or 0), 0.0),
            "warehouses": warehouses_out,
        }
    )


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


@api.get("/inventory/stock-counts/{count_id}/variance-report")
async def stock_count_variance_report(
    count_id: str,
    format: str = "csv",
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-5.2 — export completed count variance (CSV or PDF)."""
    report = await stock_counts_svc.build_variance_report(
        db, tenant_id=claims["tenant_id"], count_id=count_id
    )
    fmt = (format or "csv").strip().lower()
    safe_num = "".join(c if c.isalnum() or c in "-_" else "_" for c in report["count_number"])
    if fmt == "json":
        return env(report)
    if fmt == "pdf":
        pdf_bytes = stock_counts_svc.variance_report_pdf(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="stock-count-{safe_num}-variance.pdf"'
            },
        )
    if fmt != "csv":
        raise HTTPException(status_code=400, detail="format must be csv, pdf, or json")
    csv_text = stock_counts_svc.variance_report_csv(report)
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="stock-count-{safe_num}-variance.csv"'
        },
    )


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
    from app.inventory import normalize_adjustment_reason

    reason = normalize_adjustment_reason(payload.reason)
    product = await apply_stock_change(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        quantity_delta=float(payload.quantity),
        movement_type="adjustment",
        user_id=claims["sub"],
        reason=reason,
        notes=payload.notes,
        warehouse_id=payload.warehouse_id,
        allow_negative=True,
    )
    await db.commit()
    return env(
        {
            "product_id": product.id,
            "stock_qty": float(product.stock_qty),
            "reason": reason,
        }
    )


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


@api.post("/inventory/opening-stock")
async def opening_stock(
    payload: OpeningStockRequest,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-5.2 Opening Stock — initialize levels for existing products / fiscal start."""
    if payload.items:
        result = await catalog_svc.record_opening_stock_batch(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            items=[item.model_dump() for item in payload.items],
            fiscal_period=payload.fiscal_period,
        )
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="inventory",
            action="opening_stock_batch",
            entity="stock_movement",
            entity_id=None,
            details={"count": result["count"], "fiscal_period": payload.fiscal_period},
        )
        await db.commit()
        return env(result, "Opening stock recorded")

    if not payload.product_id or payload.quantity is None:
        raise HTTPException(
            status_code=400, detail="product_id and quantity required for single-line opening stock"
        )
    result = await catalog_svc.record_opening_stock(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        product_id=payload.product_id,
        quantity=float(payload.quantity),
        mode=payload.mode,
        notes=payload.notes,
        warehouse_id=payload.warehouse_id,
        variant_id=payload.variant_id,
        batch_number=payload.batch_number,
        manufacturing_date=payload.manufacturing_date,
        expiry_date=payload.expiry_date,
        fiscal_period=payload.fiscal_period,
    )
    await db.commit()
    return env(result, "Opening stock recorded")


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


async def _serialize_customer_response(
    db: AsyncSession, tenant_id: str, party: m.Party
) -> dict:
    contacts = await customers_svc.list_contacts(db, tenant_id, party.id)
    group = None
    if party.customer_group_id:
        groups = await customers_svc.load_group_map(
            db, tenant_id, [party.customer_group_id]
        )
        group = groups.get(party.customer_group_id)
    return customers_svc.serialize_customer(party, contacts, group)


@api.get("/customers/groups")
async def list_customer_groups(
    active_only: bool = False,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await customers_svc.list_groups(
        db, claims["tenant_id"], active_only=active_only
    )
    await db.commit()
    return env([customers_svc.serialize_group(r) for r in rows])


@api.post("/customers/groups")
async def create_customer_group(
    payload: CustomerGroupCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await customers_svc.create_group(
        db,
        tenant_id=claims["tenant_id"],
        name=payload.name,
        discount_percent=float(payload.discount_percent or 0),
    )
    await db.commit()
    return env(customers_svc.serialize_group(row), "Customer group created")


@api.get("/customers/groups/{group_id}")
async def get_customer_group(
    group_id: str,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await customers_svc.get_customer_group(db, claims["tenant_id"], group_id)
    return env(customers_svc.serialize_group(row))


@api.patch("/customers/groups/{group_id}")
async def patch_customer_group(
    group_id: str,
    payload: CustomerGroupUpdate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await customers_svc.update_group(
        db,
        tenant_id=claims["tenant_id"],
        group_id=group_id,
        fields=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return env(customers_svc.serialize_group(row), "Customer group updated")


@api.delete("/customers/groups/{group_id}")
async def delete_customer_group(
    group_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await customers_svc.deactivate_group(
        db, tenant_id=claims["tenant_id"], group_id=group_id
    )
    await db.commit()
    return env(customers_svc.serialize_group(row), "Customer group deactivated")


@api.get("/customers")
async def customers(
    active_only: bool = False,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    await customers_svc.ensure_default_customer_groups(db, claims["tenant_id"])
    stmt = (
        select(m.Party)
        .where(m.Party.tenant_id == claims["tenant_id"], m.Party.kind == "customer")
        .order_by(m.Party.name)
    )
    if active_only:
        stmt = stmt.where(m.Party.status == "active")
    rows = (await db.execute(stmt)).scalars().all()
    group_map = await customers_svc.load_group_map(
        db, claims["tenant_id"], [r.customer_group_id for r in rows if r.customer_group_id]
    )
    out = []
    for row in rows:
        contacts = await customers_svc.list_contacts(db, claims["tenant_id"], row.id)
        out.append(
            customers_svc.serialize_customer(
                row, contacts, group_map.get(row.customer_group_id) if row.customer_group_id else None
            )
        )
    await db.commit()
    return env(out)


@api.post("/customers")
async def add_customer(
    payload: CustomerCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump()
    contacts = data.pop("contacts", None) or []
    party = await customers_svc.create_customer(
        db,
        tenant_id=claims["tenant_id"],
        name=data["name"],
        code=data.get("code"),
        party_type=data.get("party_type") or "registered",
        category=data.get("category"),
        customer_group_id=data.get("customer_group_id"),
        customer_group=data.get("customer_group"),
        email=data.get("email"),
        phone=data.get("phone"),
        address=data.get("address"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        notes=data.get("notes"),
        payment_terms_days=int(data.get("payment_terms_days") or 0),
        credit_limit=float(data.get("credit_limit") or 0),
        contacts=contacts,
    )
    await db.commit()
    return env(
        await _serialize_customer_response(db, claims["tenant_id"], party),
        "Customer created",
    )


@api.get("/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    party = await customers_svc.get_customer(db, claims["tenant_id"], customer_id)
    return env(await _serialize_customer_response(db, claims["tenant_id"], party))


@api.patch("/customers/{customer_id}")
async def patch_customer(
    customer_id: str,
    payload: CustomerUpdate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = await customers_svc.update_customer(
        db,
        tenant_id=claims["tenant_id"],
        customer_id=customer_id,
        fields=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return env(
        await _serialize_customer_response(db, claims["tenant_id"], party),
        "Customer updated",
    )


@api.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = await customers_svc.deactivate_customer(
        db, tenant_id=claims["tenant_id"], customer_id=customer_id
    )
    await db.commit()
    return env(
        await _serialize_customer_response(db, claims["tenant_id"], party),
        "Customer deactivated",
    )


@api.post("/customers/{customer_id}/contacts")
async def add_customer_contact(
    customer_id: str,
    payload: CustomerContactCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    contact = await customers_svc.add_contact(
        db,
        tenant_id=claims["tenant_id"],
        customer_id=customer_id,
        **payload.model_dump(),
    )
    await db.commit()
    return env(customers_svc.serialize_contact(contact), "Contact added")


@api.delete("/customers/{customer_id}/contacts/{contact_id}")
async def delete_customer_contact(
    customer_id: str,
    contact_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    await customers_svc.delete_contact(
        db,
        tenant_id=claims["tenant_id"],
        customer_id=customer_id,
        contact_id=contact_id,
    )
    await db.commit()
    return env(None, "Contact removed")


@api.get("/customers/{customer_id}/history")
async def customer_history(
    customer_id: str,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    data = await customers_svc.customer_history(
        db, tenant_id=claims["tenant_id"], customer_id=customer_id
    )
    return env(data)


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
        early_pay_discount_pct=data.get("early_pay_discount_pct"),
        early_pay_discount_days=data.get("early_pay_discount_days"),
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
    out = [await sales_svc.serialize_invoice(db, inv) for inv in rows]
    await db.commit()  # persist any overdue status refreshes from serialize
    return env(out)


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
    data = await sales_svc.serialize_invoice(db, invoice)
    await db.commit()
    return env(data)


@api.get("/sales/invoices/{invoice_id}/print")
async def print_sales_invoice(
    invoice_id: str,
    template: str | None = None,
    format: str = "text",
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    invoice = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, invoice.created_by)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    customer = await sales_svc.get_customer(db, claims["tenant_id"], invoice.customer_id)
    tpl = (template or getattr(tenant, "invoice_print_template", None) or "a4").strip().lower()
    if tpl not in sales_svc.INVOICE_PRINT_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"template must be one of: {sorted(sales_svc.INVOICE_PRINT_TEMPLATES)}",
        )
    fmt = (format or "text").strip().lower()
    if fmt not in sales_svc.INVOICE_PRINT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of: {sorted(sales_svc.INVOICE_PRINT_FORMATS)}",
        )
    data = await sales_svc.serialize_invoice(db, invoice)
    currency = data.get("currency") or tenant.currency or "GHS"
    product_ids = [str(i.get("product_id")) for i in (data.get("items") or []) if i.get("product_id")]
    item_labels: dict[str, str] = {}
    if product_ids:
        products = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == claims["tenant_id"],
                    m.Product.id.in_(product_ids),
                )
            )
        ).scalars().all()
        item_labels = {p.id: p.name for p in products}
    from app.print_branding import tenant_document_brand

    doc_brand = tenant_document_brand(tenant)
    brand = dict(
        company_name=doc_brand["company_name"],
        customer_name=customer.name,
        template=tpl,
        currency=currency,
        company_address=doc_brand["company_address"],
        company_phone=doc_brand["company_phone"],
        company_email=doc_brand["company_email"],
        tax_registration_number=doc_brand["tax_registration_number"],
        customer_address=getattr(customer, "address", None),
        item_labels=item_labels,
        logo_data_url=doc_brand["logo_data_url"],
        trading_name=doc_brand["trading_name"],
        legal_name=doc_brand["legal_name"],
        has_logo=doc_brand["has_logo"],
        document_header=doc_brand["document_header"],
        document_footer=doc_brand["document_footer"],
    )
    await db.commit()
    if fmt == "pdf":
        pdf = sales_svc.render_invoice_pdf(data, **brand)
        filename = f"invoice_{(data.get('invoice_number') or invoice_id)}.pdf".replace("/", "-")
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    if fmt == "html":
        return HTMLResponse(sales_svc.render_invoice_html(data, **brand))
    text = sales_svc.render_invoice_text(data, **brand)
    return env(
        {
            "invoice": data,
            "text": text,
            "template": tpl,
            "format": fmt,
            "customer_name": customer.name,
            "company_name": doc_brand["company_name"],
            "legal_name": doc_brand["legal_name"],
            "trading_name": doc_brand["trading_name"],
            "has_logo": doc_brand["has_logo"],
            "logo_data_url": doc_brand["logo_data_url"],
        }
    )


@api.post("/sales/invoices/{invoice_id}/send")
async def send_sales_invoice(
    invoice_id: str,
    payload: InvoiceSendRequest | None = None,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    invoice, delivery = await sales_svc.send_sales_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        invoice_id=invoice_id,
        to=payload.to if payload else None,
    )
    await db.commit()
    data = await sales_svc.serialize_invoice(db, invoice)
    data["delivery"] = delivery
    return env(data, f"Invoice emailed to {delivery['to']} ({delivery['mode']})")


@api.post("/sales/invoices/{invoice_id}/post")
async def post_sales_invoice(
    invoice_id: str,
    payload: CreditLimitOverrideRequest = CreditLimitOverrideRequest(),
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    perms = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    invoice = await sales_svc.post_sales_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        invoice_id=invoice_id,
        role=claims.get("role") or "",
        permissions=perms,
        credit_limit_override=bool(payload.credit_limit_override),
        credit_override_reason=payload.credit_override_reason,
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
    stmt = (
        select(m.SalesQuotation)
        .where(m.SalesQuotation.tenant_id == claims["tenant_id"])
        .order_by(m.SalesQuotation.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesQuotation, claims)
    rows = (await db.execute(stmt)).scalars().all()
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
    assert_record_access(claims, quote.created_by)
    return env(await sales_docs_svc.serialize_quotation(db, quote))


@api.get("/sales/quotations/{quotation_id}/print")
async def print_sales_quotation(
    quotation_id: str,
    template: str | None = None,
    format: str = "text",
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    quote = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, quote.created_by)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    customer = await sales_svc.get_customer(db, claims["tenant_id"], quote.customer_id)
    tpl = (template or getattr(tenant, "invoice_print_template", None) or "a4").strip().lower()
    if tpl not in sales_docs_svc.QUOTATION_PRINT_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"template must be one of: {sorted(sales_docs_svc.QUOTATION_PRINT_TEMPLATES)}",
        )
    fmt = (format or "text").strip().lower()
    if fmt not in sales_docs_svc.QUOTATION_PRINT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of: {sorted(sales_docs_svc.QUOTATION_PRINT_FORMATS)}",
        )
    data = await sales_docs_svc.serialize_quotation(db, quote)
    currency = tenant.currency or "GHS"
    product_ids = [
        str(i.get("product_id")) for i in (data.get("items") or []) if i.get("product_id")
    ]
    item_labels: dict[str, str] = {}
    if product_ids:
        products = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == claims["tenant_id"],
                    m.Product.id.in_(product_ids),
                )
            )
        ).scalars().all()
        item_labels = {p.id: p.name for p in products}
    from app.print_branding import tenant_document_brand

    doc_brand = tenant_document_brand(tenant)
    brand = dict(
        company_name=doc_brand["company_name"],
        customer_name=customer.name,
        template=tpl,
        currency=currency,
        company_address=doc_brand["company_address"],
        company_phone=doc_brand["company_phone"],
        company_email=doc_brand["company_email"],
        tax_registration_number=doc_brand["tax_registration_number"],
        customer_address=getattr(customer, "address", None),
        item_labels=item_labels,
        logo_data_url=doc_brand["logo_data_url"],
        trading_name=doc_brand["trading_name"],
        legal_name=doc_brand["legal_name"],
        has_logo=doc_brand["has_logo"],
        document_header=doc_brand["document_header"],
        document_footer=doc_brand["document_footer"],
    )
    await db.commit()
    if fmt == "pdf":
        pdf = sales_docs_svc.render_quotation_pdf(data, **brand)
        filename = f"quotation_{(data.get('quotation_number') or quotation_id)}.pdf".replace(
            "/", "-"
        )
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    if fmt == "html":
        return HTMLResponse(sales_docs_svc.render_quotation_html(data, **brand))
    text = sales_docs_svc.render_quotation_text(data, **brand)
    return env(
        {
            "quotation": data,
            "text": text,
            "template": tpl,
            "format": fmt,
            "customer_name": customer.name,
            "company_name": doc_brand["company_name"],
            "legal_name": doc_brand["legal_name"],
            "trading_name": doc_brand["trading_name"],
            "has_logo": doc_brand["has_logo"],
            "logo_data_url": doc_brand["logo_data_url"],
        }
    )


@api.post("/sales/quotations/{quotation_id}/send")
async def send_quotation(
    quotation_id: str,
    to: str | None = None,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
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
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
    quote = await sales_docs_svc.accept_quotation(db, claims["tenant_id"], quotation_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_quotation(db, quote), "Quotation accepted")


@api.post("/sales/quotations/{quotation_id}/reject")
async def reject_quotation(
    quotation_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
    quote = await sales_docs_svc.reject_quotation(db, claims["tenant_id"], quotation_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_quotation(db, quote), "Quotation rejected")


@api.post("/sales/quotations/{quotation_id}/convert-order")
async def convert_quotation_order(
    quotation_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
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
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
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
    stmt = (
        select(m.SalesOrder)
        .where(m.SalesOrder.tenant_id == claims["tenant_id"])
        .order_by(m.SalesOrder.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesOrder, claims)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await sales_docs_svc.serialize_order(db, o) for o in rows])


@api.post("/sales/orders")
async def create_sales_order(
    payload: SalesOrderCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    if payload.quotation_id:
        quote = await sales_docs_svc.get_quotation(db, claims["tenant_id"], payload.quotation_id)
        assert_record_access(claims, quote.created_by)
    order = await sales_docs_svc.create_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        customer_id=payload.customer_id,
        quotation_id=payload.quotation_id,
        store_id=payload.store_id,
        warehouse_id=payload.warehouse_id,
        discount_amount=payload.discount_amount,
        notes=payload.notes,
        delivery_date=payload.delivery_date,
        delivery_address=payload.delivery_address,
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
    assert_record_access(claims, order.created_by)
    return env(await sales_docs_svc.serialize_order(db, order))


@api.patch("/sales/orders/{order_id}")
async def patch_sales_order(
    order_id: str,
    payload: SalesOrderUpdate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    fields = payload.model_dump(exclude_unset=True)
    order = await sales_docs_svc.update_order(
        db,
        tenant_id=claims["tenant_id"],
        order_id=order_id,
        notes=fields.get("notes"),
        delivery_date=fields.get("delivery_date"),
        delivery_address=fields.get("delivery_address"),
        store_id=fields.get("store_id"),
        warehouse_id=fields.get("warehouse_id"),
        clear_delivery_date="delivery_date" in fields and fields.get("delivery_date") is None,
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Sales order updated")


@api.post("/sales/orders/{order_id}/confirm")
async def confirm_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.confirm_order(
        db, claims["tenant_id"], order_id, user_id=claims["sub"]
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order confirmed; inventory reserved")


@api.post("/sales/orders/{order_id}/process")
async def process_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.advance_order_status(
        db,
        tenant_id=claims["tenant_id"],
        order_id=order_id,
        target_status="processing",
        user_id=claims["sub"],
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order processing")


@api.post("/sales/orders/{order_id}/ship")
async def ship_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.advance_order_status(
        db,
        tenant_id=claims["tenant_id"],
        order_id=order_id,
        target_status="shipped",
        user_id=claims["sub"],
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order shipped")


@api.post("/sales/orders/{order_id}/deliver")
async def deliver_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.advance_order_status(
        db,
        tenant_id=claims["tenant_id"],
        order_id=order_id,
        target_status="delivered",
        user_id=claims["sub"],
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order delivered")


@api.post("/sales/orders/{order_id}/cancel")
async def cancel_sales_order(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.cancel_order(
        db, claims["tenant_id"], order_id, user_id=claims["sub"]
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order cancelled")


@api.post("/sales/orders/{order_id}/convert-invoice")
async def convert_order_invoice(
    order_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
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
    stmt = (
        select(m.SalesReturn)
        .where(m.SalesReturn.tenant_id == claims["tenant_id"])
        .order_by(m.SalesReturn.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesReturn, claims)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await sales_docs_svc.serialize_return(db, r) for r in rows])


@api.post("/sales/returns")
async def create_sales_return(
    payload: SalesReturnCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    invoice = await sales_svc.get_invoice(db, claims["tenant_id"], payload.sales_invoice_id)
    assert_record_access(claims, invoice.created_by)
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
    assert_record_access(claims, ret.created_by)
    return env(await sales_docs_svc.serialize_return(db, ret))


@api.get("/sales/returns/{return_id}/print")
async def print_sales_return_credit_note(
    return_id: str,
    template: str | None = None,
    format: str = "text",
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    ret = await sales_docs_svc.get_return(db, claims["tenant_id"], return_id)
    assert_record_access(claims, ret.created_by)
    if ret.status != "posted" or not ret.credit_note_number:
        raise HTTPException(
            status_code=409,
            detail="Credit note is available after the sales return is posted",
        )
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    customer = await sales_svc.get_customer(db, claims["tenant_id"], ret.customer_id)
    invoice = await sales_svc.get_invoice(db, claims["tenant_id"], ret.sales_invoice_id)
    tpl = (template or getattr(tenant, "invoice_print_template", None) or "a4").strip().lower()
    if tpl not in sales_docs_svc.CREDIT_NOTE_PRINT_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"template must be one of: {sorted(sales_docs_svc.CREDIT_NOTE_PRINT_TEMPLATES)}",
        )
    fmt = (format or "text").strip().lower()
    if fmt not in sales_docs_svc.CREDIT_NOTE_PRINT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of: {sorted(sales_docs_svc.CREDIT_NOTE_PRINT_FORMATS)}",
        )
    data = await sales_docs_svc.serialize_return(db, ret)
    currency = tenant.currency or "GHS"
    product_ids = [
        str(i.get("product_id")) for i in (data.get("items") or []) if i.get("product_id")
    ]
    item_labels: dict[str, str] = {}
    if product_ids:
        products = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == claims["tenant_id"],
                    m.Product.id.in_(product_ids),
                )
            )
        ).scalars().all()
        item_labels = {p.id: p.name for p in products}
    from app.print_branding import tenant_document_brand

    doc_brand = tenant_document_brand(tenant)
    brand = dict(
        company_name=doc_brand["company_name"],
        customer_name=customer.name,
        template=tpl,
        currency=currency,
        company_address=doc_brand["company_address"],
        company_phone=doc_brand["company_phone"],
        company_email=doc_brand["company_email"],
        tax_registration_number=doc_brand["tax_registration_number"],
        customer_address=getattr(customer, "address", None),
        invoice_number=invoice.invoice_number,
        item_labels=item_labels,
        logo_data_url=doc_brand["logo_data_url"],
        trading_name=doc_brand["trading_name"],
        legal_name=doc_brand["legal_name"],
        has_logo=doc_brand["has_logo"],
        document_header=doc_brand["document_header"],
        document_footer=doc_brand["document_footer"],
    )
    await db.commit()
    if fmt == "pdf":
        pdf = sales_docs_svc.render_credit_note_pdf(data, **brand)
        filename = f"credit-note_{(data.get('credit_note_number') or return_id)}.pdf".replace(
            "/", "-"
        )
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    if fmt == "html":
        return HTMLResponse(sales_docs_svc.render_credit_note_html(data, **brand))
    text = sales_docs_svc.render_credit_note_text(data, **brand)
    return env(
        {
            "return": data,
            "text": text,
            "template": tpl,
            "format": fmt,
            "customer_name": customer.name,
            "company_name": doc_brand["company_name"],
            "legal_name": doc_brand["legal_name"],
            "trading_name": doc_brand["trading_name"],
            "has_logo": doc_brand["has_logo"],
            "logo_data_url": doc_brand["logo_data_url"],
            "invoice_number": invoice.invoice_number,
        }
    )


@api.post("/sales/returns/{return_id}/post")
async def post_sales_return(
    return_id: str,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_return(db, claims["tenant_id"], return_id)
    assert_record_access(claims, existing.created_by)
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
    stmt = (
        select(m.PurchaseRequest)
        .where(m.PurchaseRequest.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseRequest.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseRequest, claims)
    rows = (await db.execute(stmt)).scalars().all()
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
    assert_record_access(claims, pr.created_by)
    return env(await purchasing_svc.serialize_pr(db, pr))


@api.post("/purchasing/requests/{request_id}/submit")
async def submit_purchase_request(
    request_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_purchase_request(db, claims["tenant_id"], request_id)
    assert_record_access(claims, existing.created_by)
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
    existing = await purchasing_svc.get_purchase_request(db, claims["tenant_id"], request_id)
    assert_record_access(claims, existing.created_by)
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
    existing = await purchasing_svc.get_purchase_request(db, claims["tenant_id"], request_id)
    assert_record_access(claims, existing.created_by)
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
    stmt = (
        select(m.PurchaseOrder)
        .where(m.PurchaseOrder.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseOrder.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseOrder, claims)
    rows = (await db.execute(stmt)).scalars().all()
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
        delivery_address=payload.delivery_address,
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
    assert_record_access(claims, po.created_by)
    return env(await purchasing_svc.serialize_po(db, po))


@api.patch("/purchasing/orders/{po_id}")
async def patch_purchase_order(
    po_id: str,
    payload: PurchaseOrderUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, existing.created_by)
    data = payload.model_dump(exclude_unset=True)
    po = await purchasing_svc.update_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        items=[i for i in (data.get("items") or [])] if "items" in data else None,
        warehouse_id=data.get("warehouse_id") if "warehouse_id" in data else None,
        delivery_address=(
            data.get("delivery_address")
            if "delivery_address" in data
            else purchasing_svc._UNSET
        ),
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
    existing = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, existing.created_by)
    data = payload.model_dump(exclude_unset=True)
    po = await purchasing_svc.amend_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        reason=payload.reason,
        items=data.get("items"),
        warehouse_id=data.get("warehouse_id") if "warehouse_id" in data else None,
        delivery_address=(
            data.get("delivery_address")
            if "delivery_address" in data
            else purchasing_svc._UNSET
        ),
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
    po = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, po.created_by)
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
    existing = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, existing.created_by)
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
    assert_record_access(claims, po.created_by)
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
    existing = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, existing.created_by)
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
    stmt = (
        select(m.GoodsReceipt)
        .where(m.GoodsReceipt.tenant_id == claims["tenant_id"])
        .order_by(m.GoodsReceipt.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.GoodsReceipt, claims)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await purchasing_svc.serialize_grn(db, g) for g in rows])


@api.post("/purchasing/grn")
async def create_grn(
    payload: GrnCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    # Receiving may be done by warehouse staff who did not create the PO; do not gate on PO creator.
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
    assert_record_access(claims, grn.created_by)
    return env(await purchasing_svc.serialize_grn(db, grn))


@api.get("/purchasing/returns")
async def list_purchase_returns(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(m.PurchaseReturn)
        .where(m.PurchaseReturn.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseReturn.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseReturn, claims)
    rows = (await db.execute(stmt)).scalars().all()
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
    assert_record_access(claims, ret.created_by)
    return env(await purchasing_svc.serialize_purchase_return(db, ret))


@api.get("/purchasing/returns/{return_id}/print")
async def print_purchase_return_debit_note(
    return_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    ret = await purchasing_svc.get_purchase_return(db, claims["tenant_id"], return_id)
    assert_record_access(claims, ret.created_by)
    if ret.status != "posted" or not ret.debit_note_number:
        raise HTTPException(
            status_code=409,
            detail="Debit note is available after the purchase return is posted",
        )
    supplier = await purchasing_svc.get_supplier(db, claims["tenant_id"], ret.supplier_id)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    po = await purchasing_svc.get_po(db, claims["tenant_id"], ret.purchase_order_id)
    grn = await purchasing_svc.get_grn(db, claims["tenant_id"], ret.goods_receipt_id)
    data = await purchasing_svc.serialize_purchase_return(db, ret)
    text = purchasing_svc.render_debit_note_text(
        data,
        supplier_name=supplier.name,
        company_name=tenant.company_name,
        po_number=po.po_number,
        grn_number=grn.grn_number,
    )
    return env(
        {
            "return": data,
            "text": text,
            "supplier_name": supplier.name,
            "company_name": tenant.company_name,
            "po_number": po.po_number,
            "grn_number": grn.grn_number,
        }
    )


@api.post("/purchasing/returns/{return_id}/post")
async def post_purchase_return(
    return_id: str,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_purchase_return(db, claims["tenant_id"], return_id)
    assert_record_access(claims, existing.created_by)
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
    stmt = (
        select(m.PurchaseInvoice)
        .where(m.PurchaseInvoice.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseInvoice.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseInvoice, claims)
    rows = (await db.execute(stmt)).scalars().all()
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
    assert_record_access(claims, inv.created_by)
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv))


@api.patch("/purchasing/invoices/{invoice_id}")
async def patch_purchase_invoice(
    invoice_id: str,
    payload: PurchaseInvoiceUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import purchase_ocr as purchase_ocr_svc

    existing = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
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

    existing = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
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
    existing = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
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
    existing = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
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
    assert_record_access(claims, inv.created_by)
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
    assert_record_access(claims, inv.created_by)
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
    assert_record_access(claims, inv.created_by)
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
    from app.tax import resolve_product_tax
    from app.catalog import resolve_sale_line

    group_discount = await customers_svc.customer_group_discount_percent(
        db, claims["tenant_id"], payload.party_id
    )
    subtotal = 0.0
    tax_total = 0.0
    line_discounts = 0.0
    priced_items = []
    for item in items:
        product, variant, unit_price = await resolve_sale_line(
            db,
            claims["tenant_id"],
            item,
            group_discount_percent=group_discount,
        )
        spec = await resolve_product_tax(db, claims["tenant_id"], product)
        line_discount = round(float(item.get("discount") or 0), 2)
        if line_discount < 0:
            raise HTTPException(status_code=400, detail="Line discount must be >= 0")
        gross_before_discount = round(float(item["quantity"]) * float(unit_price), 2)
        if line_discount > gross_before_discount:
            raise HTTPException(status_code=400, detail="Line discount exceeds line amount")
        taxable_base = round(gross_before_discount - line_discount, 2)
        line_sub, line_tax, line_gross = spec.compute_amounts(taxable_base)
        subtotal += line_sub
        line_discounts += line_discount
        if not spec.is_reverse_charge:
            tax_total += line_tax
        priced_items.append(
            {
                **item,
                "variant_id": variant.id if variant else item.get("variant_id"),
                "name": variant.name if variant else product.name,
                "sku": variant.sku if variant else product.sku,
                "unit_price": unit_price,
                "discount": line_discount,
                "tax_rate": spec.rate_pct,
                "supply_category": spec.supply_category,
                "line_subtotal": line_sub,
                "line_tax": 0.0 if spec.is_reverse_charge else line_tax,
                "line_total": line_gross,
                "is_reverse_charge": spec.is_reverse_charge,
            }
        )
    cart_discount = round(float(payload.discount_amount or 0), 2)
    if cart_discount < 0:
        raise HTTPException(status_code=400, detail="discount_amount must be >= 0")
    max_cart_discount = round(subtotal + tax_total, 2)
    if cart_discount > max_cart_discount:
        raise HTTPException(status_code=400, detail="Cart discount exceeds sale total")
    total = round(subtotal + tax_total - cart_discount, 2)

    payments = pos_svc.resolve_sale_payments(
        total=total,
        payment_method=payload.payment_method,
        payments=[p.model_dump() for p in payload.payments] if payload.payments else None,
    )
    payment_method = pos_svc.primary_payment_method(payments)
    credit_amount = pos_svc.credit_portion(payments)
    if credit_amount > 0 and not payload.party_id:
        raise HTTPException(status_code=400, detail="Credit sales require a registered customer")

    party = None
    credit_gate = None
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
        if party is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        if (party.status or "active") != "active":
            raise HTTPException(status_code=409, detail="Customer is not active")
        if credit_amount > 0:
            ctype = (party.party_type or "registered").strip().lower()
            if ctype == "walk-in":
                raise HTTPException(
                    status_code=400,
                    detail="Credit sales require a registered customer",
                )
            from app.credit import enforce_credit_limit

            perms = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
            credit_gate = await enforce_credit_limit(
                db,
                tenant_id=claims["tenant_id"],
                user_id=claims.get("sub"),
                role=claims.get("role") or "",
                permissions=perms,
                customer=party,
                additional_amount=credit_amount,
                override=bool(payload.credit_limit_override),
                override_reason=payload.credit_override_reason,
                entity="pos_sale",
                entity_id=None,
                module="pos",
                record_audit=False,
            )

    ref = f"POS_SALE-{datetime.utcnow():%Y%m%d%H%M%S%f}"
    body = payload.model_dump()
    body.pop("items", None)
    body.pop("session_id", None)
    body.pop("payment_method", None)
    body.pop("payments", None)
    body.pop("credit_limit_override", None)
    body.pop("credit_override_reason", None)
    body["payload"] = {
        **(body.get("payload") or {}),
        "items": priced_items,
        "payment_method": payment_method,
        "payments": payments,
        "session_id": session.id,
        "discount_amount": cart_discount,
        "line_discounts": round(line_discounts, 2),
        "party_id": payload.party_id,
        "customer_name": party.name if party else None,
        "credit_limit_overridden": bool(credit_gate and credit_gate.get("overridden")),
        "credit_override_reason": (credit_gate or {}).get("override_reason"),
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
    if credit_gate and credit_gate.get("overridden"):
        # Re-emit audit with sale id now that the transaction exists.
        from app import audit as audit_svc

        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims.get("sub"),
            action="credit_limit_override",
            entity="pos_sale",
            entity_id=tx.id,
            module="pos",
            details={
                "customer_id": party.id if party else None,
                "customer_name": party.name if party else None,
                "reason": credit_gate.get("override_reason"),
                "credit_limit": credit_gate.get("credit_limit"),
                "current_balance": credit_gate.get("current_balance"),
                "additional_amount": credit_gate.get("additional_amount"),
                "projected_balance": credit_gate.get("projected_balance"),
                "reference": ref,
            },
        )
    payment_rows = await pos_svc.record_pos_payments(
        db,
        tenant_id=claims["tenant_id"],
        sale_id=tx.id,
        payments=payments,
    )

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
    await pos_svc.apply_sale_to_session(
        session, total=total, payment_method=payment_method, payments=payments
    )

    if payload.party_id and credit_amount > 0:
        party = await db.get(m.Party, payload.party_id)
        if party and party.tenant_id == claims["tenant_id"]:
            party.balance = float(party.balance or 0) + float(credit_amount)

    from app.accounting import post_pos_sale_journal

    await post_pos_sale_journal(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        tx=tx,
        payment_method=payment_method,
        payments=payments,
    )

    from app import cash_drawer as cash_drawer_svc

    drawer = await cash_drawer_svc.maybe_open_on_cash_sale(
        db,
        tenant_id=claims["tenant_id"],
        store_id=session.store_id,
        payment_method="cash" if pos_svc.has_cash_tender(payments) else payment_method,
        sale_id=tx.id,
        user_id=claims.get("sub"),
    )
    await db.commit()
    payload_out = {
        "id": tx.id,
        "reference": ref,
        "session_id": session.id,
        "party_id": payload.party_id,
        "subtotal": float(tx.subtotal),
        "tax": float(tx.tax),
        "discount_amount": cart_discount,
        "total": float(tx.total),
        "payment_method": payment_method,
        "payments": [pos_svc.serialize_payment(p) for p in payment_rows],
        "credit_limit_overridden": bool(credit_gate and credit_gate.get("overridden")),
        "credit_override_reason": (credit_gate or {}).get("override_reason"),
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
    paper: str | None = None,
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
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    paper = receipts_svc.resolve_receipt_paper(tenant, paper)
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
    paper: str | None = None,
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
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    paper = receipts_svc.resolve_receipt_paper(tenant, paper)
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
    return env([expenses_svc.serialize_category(c) for c in rows])


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
    return env(expenses_svc.serialize_category(cat), "Expense category created")


@api.patch("/expenses/categories/{category_id}")
async def update_expense_category(
    category_id: str,
    payload: ExpenseCategoryUpdate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    cat = await expenses_svc.update_category(
        db,
        tenant_id=claims["tenant_id"],
        category_id=category_id,
        name=payload.name,
        budget_amount=payload.budget_amount,
        is_active=payload.is_active,
    )
    await db.commit()
    return env(expenses_svc.serialize_category(cat), "Expense category updated")


@api.get("/expenses/budgets")
async def expense_category_budgets(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import reports as reports_svc

    data = await expenses_svc.category_budget_variance(
        db,
        claims["tenant_id"],
        from_date=reports_svc.parse_date(from_date),
        to_date=reports_svc.parse_date(to_date, end_of_day=True),
    )
    await db.commit()
    return env(data)


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
    return env([expenses_svc.serialize_recurring(r) for r in rows])


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
    return env(expenses_svc.serialize_recurring(row), "Recurring expense created")


@api.patch("/expenses/recurring/{recurring_id}")
async def update_recurring_expense(
    recurring_id: str,
    payload: RecurringExpenseUpdate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await expenses_svc.update_recurring(
        db,
        tenant_id=claims["tenant_id"],
        recurring_id=recurring_id,
        skip_next=payload.skip_next,
        next_amount=payload.next_amount,
        next_description=payload.next_description,
        clear_next_override=payload.clear_next_override,
        is_active=payload.is_active,
        amount=payload.amount,
        description=payload.description,
        frequency=payload.frequency,
        payment_method=payload.payment_method,
        payee=payload.payee,
    )
    await db.commit()
    return env(expenses_svc.serialize_recurring(row), "Recurring expense updated")


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
async def accounts(
    tree: bool = False,
    active_only: bool = True,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    await accounting_svc.ensure_default_accounts(db, claims["tenant_id"])
    await db.commit()
    q = select(m.Account).where(m.Account.tenant_id == claims["tenant_id"])
    if active_only:
        q = q.where(m.Account.is_active.is_(True))
    rows = list((await db.execute(q.order_by(m.Account.code))).scalars().all())
    if tree:
        return env(accounting_svc.build_account_tree(rows))
    return env([accounting_svc.serialize_coa_account(r) for r in rows])


@api.get("/accounting/accounts/{account_id}")
async def get_account(
    account_id: str,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    row = await accounting_svc.get_tenant_account(db, claims["tenant_id"], account_id)
    return env(accounting_svc.serialize_coa_account(row))


@api.post("/accounting/accounts")
async def create_coa_account(
    payload: CoaAccountCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc
    from app import audit as audit_svc

    row = await accounting_svc.create_coa_account(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        account_type=payload.account_type,
        parent_id=payload.parent_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="coa_account_create",
        entity="account",
        entity_id=row.id,
        details={"code": row.code, "account_type": row.account_type, "parent_id": row.parent_id},
    )
    await db.commit()
    return env(accounting_svc.serialize_coa_account(row), "Account created")


@api.patch("/accounting/accounts/{account_id}")
async def patch_coa_account(
    account_id: str,
    payload: CoaAccountUpdate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    data = payload.model_dump(exclude_unset=True)
    clear_parent = "parent_id" in data and data["parent_id"] is None
    row = await accounting_svc.update_coa_account(
        db,
        tenant_id=claims["tenant_id"],
        account_id=account_id,
        code=data.get("code"),
        name=data.get("name"),
        account_type=data.get("account_type"),
        parent_id=data.get("parent_id"),
        is_active=data.get("is_active"),
        clear_parent=clear_parent,
    )
    await db.commit()
    return env(accounting_svc.serialize_coa_account(row), "Account updated")


@api.post("/accounting/accounts/{account_id}/opening-balance")
async def post_opening_balance(
    account_id: str,
    payload: OpeningBalanceCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.post_account_opening_balance(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        account_id=account_id,
        amount=payload.amount,
        description=payload.description,
    )
    await db.commit()
    return env(
        await accounting_svc.serialize_journal(db, entry),
        "Opening balance posted",
    )


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


@api.post("/accounting/liquid-accounts")
async def create_liquid_account(
    payload: LiquidAccountCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc
    from app import bank_recon as bank_recon_svc
    from app import audit as audit_svc

    row = await accounting_svc.create_liquid_account(
        db,
        tenant_id=claims["tenant_id"],
        kind=payload.kind,
        code=payload.code,
        name=payload.name,
        bank_name=payload.bank_name,
        account_number=payload.account_number,
        bank_branch=payload.bank_branch,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="liquid_account_create",
        entity="account",
        entity_id=row.id,
        details={
            "code": row.code,
            "kind": "cash" if row.is_cash_account else "bank",
            "name": row.name,
        },
    )
    await db.commit()
    return env(bank_recon_svc.serialize_account(row), "Liquid account created")


@api.patch("/accounting/liquid-accounts/{account_id}")
async def update_liquid_account(
    account_id: str,
    payload: LiquidAccountUpdate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc
    from app import bank_recon as bank_recon_svc

    row = await accounting_svc.update_liquid_account(
        db,
        tenant_id=claims["tenant_id"],
        account_id=account_id,
        name=payload.name,
        bank_name=payload.bank_name,
        account_number=payload.account_number,
        bank_branch=payload.bank_branch,
        clear_bank_details=payload.clear_bank_details,
    )
    await db.commit()
    return env(bank_recon_svc.serialize_account(row), "Liquid account updated")


@api.post("/accounting/liquid-transfers")
async def create_liquid_transfer(
    payload: LiquidTransferCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.transfer_liquid_funds(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        amount=payload.amount,
        description=payload.description,
        reference=payload.reference,
        kind=payload.kind,
    )
    await db.commit()
    return env(await accounting_svc.serialize_journal(db, entry), "Liquid transfer posted")


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
    lines_in = payload.get("lines") or []
    stmt = await bank_recon_svc.create_statement(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        account_id=payload.get("account_id") or "",
        statement_date=payload.get("statement_date"),
        opening_balance=float(payload.get("opening_balance") or 0),
        closing_balance=float(payload.get("closing_balance") or 0),
        notes=payload.get("notes"),
        lines=lines_in,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="bank_statement_create",
        entity="bank_statement",
        entity_id=stmt.id,
        details={
            "account_id": stmt.account_id,
            "line_count": len(lines_in),
        },
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
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="bank_statement_import",
        entity="bank_statement",
        entity_id=stmt.id,
        details={
            "account_id": account_id,
            "format": meta.get("format"),
            "line_count": meta.get("line_count"),
            "filename": file.filename,
        },
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


@api.get("/accounting/journal-entries/{entry_id}")
async def get_journal(
    entry_id: str,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = (
        await db.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.id == entry_id,
                m.JournalEntry.tenant_id == claims["tenant_id"],
            )
        )
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return env(await accounting_svc.serialize_journal(db, entry))


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


@api.post("/accounting/journal-entries/{entry_id}/unpost")
async def unpost_journal(
    entry_id: str,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.unpost_journal_entry(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        entry_id=entry_id,
    )
    await db.commit()
    return env(await accounting_svc.serialize_journal(db, entry), "Journal entry unposted")


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
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts, profit_and_loss

    await ensure_default_accounts(db, claims["tenant_id"])
    await db.commit()
    return env(
        await profit_and_loss(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/reports/profit-loss")
async def report_profit_loss(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return await get_profit_loss(from_date, to_date, claims, db)


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
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    supplier = await purchasing_svc.get_supplier(db, claims["tenant_id"], inv.supplier_id)
    ep = credit_svc.resolve_early_pay_settings(tenant, supplier)
    quote = credit_svc.purchase_invoice_early_discount(
        inv,
        pct=ep["early_pay_discount_pct"],
        days=ep["early_pay_discount_days"],
    )
    return env(
        {
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "source": ep["source"],
            **quote,
        }
    )


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
    customer = await customers_svc.update_customer(
        db,
        tenant_id=claims["tenant_id"],
        customer_id=customer_id,
        fields={"credit_limit": payload.credit_limit},
    )
    await db.commit()
    return env(
        {
            "id": customer.id,
            "name": customer.name,
            "credit_limit": float(customer.credit_limit),
            "balance": float(customer.balance or 0),
            "status": customer.status or "active",
            "party_type": customer.party_type or "registered",
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
    out = []
    for s in rows:
        detail = await stores_svc.serialize_store_detail(db, s)
        detail.update(
            {
                k: v
                for k, v in cash_drawer_svc.serialize_drawer_settings(s).items()
                if k != "source"
            }
        )
        out.append(detail)
    return env(out)


@api.post("/stores")
async def add_store(
    payload: StoreCreate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    branch_id = None
    if payload.branch_id:
        branch_id, _ = await org_units_svc.assert_user_org_assignment(
            db,
            claims["tenant_id"],
            branch_id=payload.branch_id,
            department_id=None,
        )
    store = await stores_svc.create_store(
        db,
        tenant_id=claims["tenant_id"],
        name=payload.name,
        code=payload.code,
        address=payload.address,
        phone=payload.phone,
        manager_id=payload.manager_id,
        branch_id=branch_id,
        operating_hours=payload.operating_hours,
    )
    await db.commit()
    return env(
        await stores_svc.serialize_store_detail(db, store),
        "Store created with warehouse",
    )


@api.patch("/stores/{store_id}")
async def update_store(
    store_id: str,
    payload: StoreUpdate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    branch_id = payload.branch_id
    if payload.branch_id:
        branch_id, _ = await org_units_svc.assert_user_org_assignment(
            db,
            claims["tenant_id"],
            branch_id=payload.branch_id,
            department_id=None,
        )
    store = await stores_svc.update_store(
        db,
        tenant_id=claims["tenant_id"],
        store_id=store_id,
        name=payload.name,
        address=payload.address,
        phone=payload.phone,
        manager_id=payload.manager_id,
        clear_manager=payload.clear_manager,
        branch_id=branch_id,
        clear_branch=payload.clear_branch,
        operating_hours=payload.operating_hours,
        is_active=payload.is_active,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="stores",
        action="store_updated",
        entity="store",
        entity_id=store.id,
        details={"code": store.code},
    )
    await db.commit()
    return env(await stores_svc.serialize_store_detail(db, store), "Store updated")


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
        minimum_stock=payload.minimum_stock,
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
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        role=claims.get("role") or "",
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
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        role=claims.get("role") or "",
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
    return env([stores_svc.serialize_warehouse(r) for r in rows])


@api.post("/warehouses")
async def add_warehouse(
    payload: WarehouseCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    data = payload.model_dump()
    if data.get("store_id"):
        await stores_svc.get_store(db, claims["tenant_id"], data["store_id"])
    if data.get("manager_id"):
        manager = (
            await db.execute(
                select(m.User).where(
                    m.User.id == data["manager_id"],
                    m.User.tenant_id == claims["tenant_id"],
                )
            )
        ).scalar_one_or_none()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager user not found")
    wtype = (data.get("warehouse_type") or "retail").strip().lower()
    if wtype not in {"retail", "main", "cold", "bulk", "transit"}:
        raise HTTPException(
            status_code=400,
            detail="warehouse_type must be one of: retail, main, cold, bulk, transit",
        )
    data["warehouse_type"] = wtype
    data["code"] = str(data["code"]).strip().upper()
    exists = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == claims["tenant_id"],
                m.Warehouse.code == data["code"],
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Warehouse code already exists")
    warehouse = m.Warehouse(tenant_id=claims["tenant_id"], is_active=True, **data)
    db.add(warehouse)
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="warehouse_created",
        entity="warehouse",
        entity_id=warehouse.id,
        details={"code": warehouse.code},
    )
    await db.commit()
    return env(stores_svc.serialize_warehouse(warehouse), "Warehouse created")


@api.patch("/warehouses/{warehouse_id}")
async def update_warehouse(
    warehouse_id: str,
    payload: WarehouseUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    warehouse = await stores_svc.update_warehouse(
        db,
        tenant_id=claims["tenant_id"],
        warehouse_id=warehouse_id,
        name=payload.name,
        store_id=payload.store_id,
        clear_store=payload.clear_store,
        warehouse_type=payload.warehouse_type,
        manager_id=payload.manager_id,
        clear_manager=payload.clear_manager,
        address=payload.address,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="warehouse_updated",
        entity="warehouse",
        entity_id=warehouse.id,
        details={"code": warehouse.code, "is_active": bool(warehouse.is_active)},
    )
    await db.commit()
    return env(stores_svc.serialize_warehouse(warehouse), "Warehouse updated")


@api.get("/inventory/stock-transfers")
async def list_inventory_stock_transfers(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.StockTransfer)
            .where(m.StockTransfer.tenant_id == claims["tenant_id"])
            .order_by(m.StockTransfer.created_at.desc())
        )
    ).scalars().all()
    return env([await stores_svc.serialize_transfer(db, row) for row in rows])


@api.post("/inventory/stock-transfers")
async def create_inventory_stock_transfer(
    payload: WarehouseStockTransferCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.create_warehouse_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        from_warehouse_id=payload.from_warehouse_id,
        to_warehouse_id=payload.to_warehouse_id,
        items=[i.model_dump() for i in payload.items],
        notes=payload.notes,
        submit=payload.submit,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="warehouse_transfer_created",
        entity="stock_transfer",
        entity_id=transfer.id,
        details={
            "transfer_number": transfer.transfer_number,
            "from_warehouse_id": transfer.from_warehouse_id,
            "to_warehouse_id": transfer.to_warehouse_id,
            "status": transfer.status,
        },
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Warehouse transfer created")


@api.post("/inventory/stock-transfers/{transfer_id}/submit")
async def submit_inventory_stock_transfer(
    transfer_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.submit_transfer(
        db, tenant_id=claims["tenant_id"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer submitted")


@api.post("/inventory/stock-transfers/{transfer_id}/ship")
async def ship_inventory_stock_transfer(
    transfer_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.ship_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        role=claims.get("role") or "",
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer shipped")


@api.post("/inventory/stock-transfers/{transfer_id}/receive")
async def receive_inventory_stock_transfer(
    transfer_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.receive_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        role=claims.get("role") or "",
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer received")


@api.post("/inventory/stock-transfers/{transfer_id}/cancel")
async def cancel_inventory_stock_transfer(
    transfer_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.cancel_transfer(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer cancelled")


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
    group: str | None = None,
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await notifications_svc.list_notifications(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        status=status,
        category=category,
        group=group,
    )
    # Array payload preserved for existing clients; history window is HISTORY_DAYS (BR-4.4).
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


@api.patch("/notifications/{nid}/unread")
async def notification_unread(
    nid: str,
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    note = await notifications_svc.mark_unread(
        db, tenant_id=claims["tenant_id"], notification_id=nid, user_id=claims["sub"]
    )
    await db.commit()
    return env(notifications_svc.serialize_notification(note), "Marked unread")


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
    payment_created = await notifications_svc.scan_payment_due(db, claims["tenant_id"])
    quote_scan = await notifications_svc.scan_quotation_expiry(db, claims["tenant_id"])
    recurring_scan = await notifications_svc.scan_recurring_expense_upcoming(
        db, claims["tenant_id"]
    )
    await db.commit()
    total = (
        int(payment_created)
        + int(quote_scan.get("reminded") or 0)
        + int(recurring_scan.get("reminded") or 0)
    )
    return env(
        {
            "created": total,
            "payment_due": payment_created,
            "quotation_expiry": quote_scan,
            "recurring_expense": recurring_scan,
        },
        f"Created {total} due notification(s)",
    )


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
                "scan_quotation_expiry_minutes": app_settings.CELERY_QUOTATION_EXPIRY_INTERVAL_MINUTES,
                "generate_recurring_expenses_minutes": app_settings.CELERY_RECURRING_INTERVAL_MINUTES,
                "run_due_backups_minutes": app_settings.CELERY_BACKUP_INTERVAL_MINUTES,
                "run_due_report_emails_minutes": app_settings.CELERY_REPORT_EMAIL_INTERVAL_MINUTES,
                "generate_ai_low_stock_predictions_minutes": app_settings.CELERY_AI_PREDICTION_INTERVAL_MINUTES,
                "generate_ai_insights_minutes": app_settings.CELERY_AI_INSIGHTS_INTERVAL_MINUTES,
                "archive_cold_audit_logs_minutes": app_settings.CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES,
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
    format: str = "csv",
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
    chronological = list(reversed(rows))
    fmt = (format or "csv").strip().lower()
    if fmt == "pdf":
        pdf_bytes = audit_svc.to_pdf(chronological)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=audit-logs.pdf"},
        )
    if fmt != "csv":
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    csv_text = audit_svc.to_csv(chronological)
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


@api.get("/audit-logs/retention")
async def audit_logs_retention(
    claims=Depends(require_permission("audit", "read")),
):
    """BR-17.2 / Stage 1 G20 — retention policy (7-year minimum, no purge)."""
    return env(audit_svc.retention_policy())


@api.get("/audit-logs/archives")
async def audit_logs_archives(
    claims=Depends(require_permission("audit", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await audit_svc.list_cold_archives(db, tenant_id=claims["tenant_id"])
    return env([audit_svc.serialize_cold_archive(r) for r in rows])


@api.post("/audit-logs/archive-cold")
async def audit_logs_archive_cold(
    older_than_days: int | None = None,
    limit: int = 5000,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Copy aged audit rows to cold object storage; mark archived_at (never delete)."""
    tenants_svc.assert_writable(claims)
    result = await audit_svc.archive_cold_logs(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        older_than_days=older_than_days,
        limit=limit,
    )
    await db.commit()
    return env(result, "Cold archive completed" if result.get("archived") else "Nothing to archive")


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
async def ai_chat(
    payload: dict,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.1 — rule-based NL chat with history (no external LLM required)."""
    message = str((payload or {}).get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > 2000:
        raise HTTPException(status_code=400, detail="message must be at most 2000 characters")
    result = await ai_chat_svc.handle_chat(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        claims=claims,
        message=message,
    )
    await db.commit()
    return env(result)


@api.get("/ai/chat/history")
async def ai_chat_history(
    limit: int = 50,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    items = await ai_chat_svc.list_history(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        limit=limit,
    )
    return env({"items": items})


@api.get("/ai/insights")
async def insights(claims=Depends(require_permission("ai", "read")), db: AsyncSession = Depends(get_db)):
    from app import ai_insights as ai_insights_svc

    data = await ai_insights_svc.generate_insights(db, claims["tenant_id"])
    return env(
        {
            "insights": data["summaries"],
            "cards": data["insights"],
            "generated_at": data["generated_at"],
            "method": data["method"],
            "count": data["count"],
            "low_stock_predictions": data["low_stock_predictions"],
        }
    )


@api.get("/ai/inventory/low-stock-prediction")
async def ai_low_stock_prediction(
    lookback_days: int = 30,
    horizon_days: int = 14,
    lead_time_days: int = 7,
    at_risk_only: bool = False,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import ai_inventory as ai_inventory_svc

    data = await ai_inventory_svc.predict_low_stock(
        db,
        claims["tenant_id"],
        lookback_days=lookback_days,
        horizon_days=horizon_days,
        lead_time_days=lead_time_days,
        at_risk_only=at_risk_only,
    )
    return env(data)


@api.get("/ai/inventory/demand-forecast")
async def ai_demand_forecast(
    lookback_days: int = 30,
    lead_time_days: int = 7,
    product_id: str | None = None,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.3 — 7/30/90-day demand forecast, seasonality, optimal reorder qty."""
    from app import ai_inventory as ai_inventory_svc

    data = await ai_inventory_svc.forecast_demand(
        db,
        claims["tenant_id"],
        lookback_days=lookback_days,
        lead_time_days=lead_time_days,
        product_id=product_id,
    )
    return env(data)


@api.get("/ai/inventory/dead-stock")
async def ai_dead_stock(
    lookback_days: int = 90,
    min_stock: float = 0,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.3 — identify products with stock and no sales in the lookback window."""
    from app import ai_inventory as ai_inventory_svc

    data = await ai_inventory_svc.identify_dead_stock(
        db,
        claims["tenant_id"],
        lookback_days=lookback_days,
        min_stock=min_stock,
    )
    return env(data)


@api.get("/ai/inventory/predictions")
async def ai_inventory_predictions(
    lookback_days: int = 30,
    horizon_days: int = 14,
    lead_time_days: int = 7,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Inventory intelligence: demand forecasts plus low-stock predictions."""
    from app import ai_inventory as ai_inventory_svc

    forecast = await ai_inventory_svc.forecast_demand(
        db,
        claims["tenant_id"],
        lookback_days=lookback_days,
        lead_time_days=lead_time_days,
    )
    low = await ai_inventory_svc.predict_low_stock(
        db,
        claims["tenant_id"],
        lookback_days=lookback_days,
        horizon_days=horizon_days,
        lead_time_days=lead_time_days,
        at_risk_only=False,
    )
    return env(
        {
            "generated_at": forecast["generated_at"],
            "method": forecast["method"],
            "lookback_days": lookback_days,
            "horizon_days": horizon_days,
            "lead_time_days": lead_time_days,
            "horizons_days": forecast["horizons_days"],
            "forecasts": forecast["forecasts"],
            "predictions": low["predictions"],
            "at_risk_count": low["at_risk_count"],
            "forecast_count": forecast["count"],
        }
    )


@api.get("/ai/sales/analysis")
async def ai_sales_analysis(
    from_date: str | None = None,
    to_date: str | None = None,
    lookback_days: int = 90,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.5 — sales trends, RFM segments, product affinity, peak hour/day."""
    from app import ai_sales as ai_sales_svc

    data = await ai_sales_svc.analyze_sales(
        db,
        claims["tenant_id"],
        from_date=from_date,
        to_date=to_date,
        lookback_days=lookback_days,
    )
    return env(data)


@api.get("/ai/expenses/analysis")
async def ai_expenses_analysis(
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.6 — budget variance, anomalies, optimization, OCR category hints."""
    from app import ai_expenses as ai_expenses_svc

    data = await ai_expenses_svc.analyze_expenses(
        db,
        claims["tenant_id"],
        from_date=from_date,
        to_date=to_date,
    )
    return env(data)


@api.get("/ai/security/alerts")
async def ai_security_alerts(
    lookback_hours: int = 72,
    notify: bool = False,
    claims=Depends(require_permission("security", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.10 — behavioral security alerts from audit logs."""
    from app import ai_security as ai_security_svc

    data = await ai_security_svc.scan_security_alerts(
        db,
        claims["tenant_id"],
        lookback_hours=lookback_hours,
        notify=notify,
    )
    if notify and data.get("notifications_created"):
        await db.commit()
    return env(data)


@api.post("/ai/reports/generate")
async def ai_reports_generate(
    payload: dict,
    export: bool = False,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.7 — generate (or export) a report from a natural-language prompt."""
    from app import ai_reports as ai_reports_svc

    prompt = str((payload or {}).get("prompt") or (payload or {}).get("message") or "").strip()
    # API-doc shape also accepts report_type + period without free text
    if not prompt and (payload or {}).get("report_type"):
        period = str((payload or {}).get("period") or "").strip()
        report_type = str(payload.get("report_type") or "").strip()
        prompt = f"Show me {report_type.replace('_', ' ')} {period}".strip()
    fmt = (payload or {}).get("format")
    template_id = (payload or {}).get("template_id")
    if export or str((payload or {}).get("export") or "").lower() in {"1", "true", "yes"}:
        # Export also needs reports:read semantics — AI read is the gate; data is tenant-scoped.
        content, media, filename = await ai_reports_svc.export_from_prompt(
            db,
            claims["tenant_id"],
            prompt=prompt,
            format=fmt,
            template_id=template_id,
        )
        return Response(
            content=content,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    data = await ai_reports_svc.generate_from_prompt(
        db,
        claims["tenant_id"],
        prompt=prompt,
        format=fmt,
        template_id=template_id,
    )
    return env(data)


@api.get("/ai/reports/templates")
async def ai_report_templates_list(
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import ai_reports as ai_reports_svc

    rows = await ai_reports_svc.list_templates(
        db, claims["tenant_id"], user_id=claims.get("sub")
    )
    return env([ai_reports_svc.serialize_template(r) for r in rows])


@api.post("/ai/reports/templates")
async def ai_report_templates_create(
    payload: dict,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import ai_reports as ai_reports_svc

    row = await ai_reports_svc.save_template(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        name=str((payload or {}).get("name") or ""),
        prompt=str((payload or {}).get("prompt") or ""),
        format=(payload or {}).get("format"),
    )
    await db.commit()
    return env(ai_reports_svc.serialize_template(row), "Report template saved")


@api.delete("/ai/reports/templates/{template_id}")
async def ai_report_templates_delete(
    template_id: str,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import ai_reports as ai_reports_svc

    await ai_reports_svc.delete_template(db, claims["tenant_id"], template_id)
    await db.commit()
    return env({"id": template_id}, "Report template deleted")


@api.post("/ai/customer/assist")
async def ai_customer_assist(
    payload: dict | None = None,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.9 — customer intelligence / assist from sales history."""
    from app import ai_customers as ai_customers_svc

    body = payload or {}
    data = await ai_customers_svc.assist_customer(
        db,
        claims["tenant_id"],
        customer_id=body.get("customer_id"),
        query=body.get("query") or body.get("message"),
    )
    return env(data)


@api.get("/ai/customers/insights")
async def ai_customers_insights(
    lookback_days: int = 180,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.9 — churn risks, best customers, promotion suggestions."""
    from app import ai_customers as ai_customers_svc

    data = await ai_customers_svc.customer_intelligence(
        db, claims["tenant_id"], lookback_days=lookback_days
    )
    return env(data)


@api.post("/ai/documents/analyze")
async def ai_documents_analyze(
    document_type: str = "receipt",
    file: UploadFile = File(...),
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.8 — OCR extract, match to parties/products, flag discrepancies."""
    from app import ai_documents as ai_documents_svc

    data = await ai_documents_svc.analyze_document(
        db,
        claims["tenant_id"],
        upload=file,
        document_type=document_type,
    )
    return env(data)
