from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path as FsPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import EmailStr, TypeAdapter, ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
import logging

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
from app import custom_roles as custom_roles_svc
from app import org_units as org_units_svc
from app import api_keys as api_keys_svc
from app import webhooks as webhooks_svc
from app import onboarding as onboarding_svc
from app import ai as ai_svc
from app import ai_digest as ai_digest_svc
from app import ai_security as ai_security_svc
from app import ai_inventory as ai_inventory_svc
from app import ai_sales as ai_sales_svc
from app import ai_expenses as ai_expenses_svc
from app import ai_reports as ai_reports_svc
from app import ai_customer as ai_customer_svc
from app import ai_documents as ai_documents_svc
from app import purchasing as purchasing_svc
from app import purchase_requests as purchase_requests_svc
from app import purchase_suggestions as purchase_suggestions_svc
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
from app import packages as packages_svc
from app import storage as storage_svc
from app.honesty import money_json, require_honest_narrative
from app.schemas import validate_e164_phone_value
from app import cheques as cheques_svc
from app import stock_counts as stock_counts_svc
from app import catalog_meta as catalog_meta_svc
from app import product_images as product_images_svc
from app import party_contacts as party_contacts_svc
from app import barcodes as barcodes_svc
from app.config import settings
from app.schemas import (
    BarcodeLabelPrintRequest,
    BrandCreate,
    BrandUpdate,
    BackupSettingsUpdate,
    BackupCreateBody,
    BackupVerifyBody,
    BackupRestoreBody,
    BackupJobStatusFilterValue,
    ReportScheduleCreate,
    ReportScheduleUpdate,
    ReportTypeValue,
    ReportExportFormatValue,
    ScheduleFrequencyValue,
    JobNameValue,
    OnboardingStepIdValue,
    UuidIdValue,
    BalanceSheetCompareValue,
    CreditAgingKindValue,
    InventoryValuationMethodValue,
    ChequeDirectionValue,
    ChequeStatusValue,
    PartyStatusValue,
    StockCountReportStatusValue,
    TransferReportStatusValue,
    PendingPoReportStatusValue,
    PurchaseOrderStatusValue,
    PurchaseInvoiceStatusValue,
    SalesInvoiceStatusValue,
    PurchaseRequestStatusValue,
    SalesQuotationStatusValue,
    SalesOrderStatusValue,
    ReturnReportStatusValue,
    TenantStatusFilterValue,
    ApiKeyStatusFilterValue,
    ApiKeyCreate,
    ExpenseStatusFilterValue,
    JournalStatusFilterValue,
    CashTransferKindFilterValue,
    PosSessionStatusFilterValue,
    TaxFilingJurisdictionValue,
    BankStatementStatusFilterValue,
    WebhookDeliveryStatusFilterValue,
    AuditModuleValue,
    AuditActionValue,
    TenantRefValue,
    RoleKeyValue,
    BankStatementNotesValue,
    AuditEntityValue,
    ProductBarcodeValue,
    ReceiptOverrideToValue,
    FiniteMoneyValue,
    ProductSearchQueryValue,
    IsoDateQueryValue,
    SalesReturnReportReasonValue,
    PurchaseReturnReportReasonValue,
    MovementTypeValue,
    StockAdjustReasonValue,
    WebhookCreate,
    WebhookUpdate,
    BarcodeSymbologyValue,
    AiDocumentTypeValue,
    NotificationCategoryValue,
    NotificationStatusValue,
    CreditLimitUpdate,
    CreditLimitOverrideRequest,
    CustomerPaymentCreate,
    EarlyPaySettingsUpdate,
    SalesInvoiceNumberingUpdate,
    SalesSettingsUpdate,
    PurchasingNumberingUpdate,
    AccountingSettingsUpdate,
    PosSettingsUpdate,
    DocumentNumberingFields,
    PrintBrandingUpdate,
    InvoiceTemplateValue,
    ReceiptPaperValue,
    InvoicePrintFormatValue,
    ReceiptPrintFormatValue,
    ReceiptChannelValue,
    E164PhoneValue,
    EmailVerifyConfirm,
    ResendVerificationRequest,
    ExchangeRateRefresh,
    ExchangeRateUpsert,
    CurrencyCodeValue,
    FxAutoRefreshUpdate,
    BankConnectionCreate,
    BankConnectionUpdate,
    BankAutoClearBody,
    BankStatementCreateBody,
    BankStatementMatchBody,
    BankClearGroupBody,
    ExpenseCategoryCreate,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    AiDocumentExpenseCreate,
    AiChatBody,
    AiCustomerAssistBody,
    AiReportsGenerateBody,
    AiReportsExportBody,
    AiReportTemplateCreateBody,
    AiLowStockPredictionRequestsBody,
    AiDocumentPurchaseInvoiceCreate,
    ExpenseDecision,
    ExpenseReject,
    ExpenseThresholdUpdate,
    ExpenseOcrApply,
    ExpenseUpdate,
    GrnCreate,
    FmcgRouteCreate,
    FmcgRouteStopCreate,
    FmcgCustomerAssignmentUpsert,
    FmcgDispatchCreate,
    FmcgRouteStopDeliveryUpdate,
    FmcgSchemePreview,
    FmcgTradeSchemeActiveUpdate,
    FmcgTradeSchemeCreate,
    HotelCheckoutBody,
    HotelGroupReservationCreate,
    HotelSettingsUpdate,
    HotelExtendStay,
    HotelFolioChargeCreate,
    HotelFolioChargeVoid,
    HotelFolioPaymentCreate,
    HotelGuestCreate,
    HotelGuestUpdate,
    HotelHousekeepingComplete,
    HotelHousekeepingCreate,
    HotelListKindValue,
    HotelMaintenanceCreate,
    HotelMoveRoom,
    HotelReservationCreate,
    HotelRoomCreate,
    HotelRoomUpdate,
    HotelReservationStatusValue,
    HotelRoomStatusValue,
    HotelHousekeepingStatusValue,
    JournalCreate,
    JournalUnpost,
    ChequeLifecycleReason,
    PeriodCloseBody,
    PeriodReopenBody,
    CreditLimitOverrideBody,
    Login,
    NotificationPreferencesUpdate,
    PartyCreate,
    PartyUpdate,
    PartyContactCreate,
    PartyContactUpdate,
    CustomerGroupCreate,
    CustomerGroupUpdate,
    PlatformGrantAccess,
    PlatformStaffCreate,
    PlatformStaffUpdate,
    PlatformRevokeAccess,
    AccountCreate,
    CashTransferCreate,
    PasswordResetConfirm,
    ChangePasswordRequest,
    PasswordResetRequest,
    PosSaleCreate,
    PosDeviceHeartbeat,
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
    PurchaseOrderAmend,
    PurchaseOrderCancel,
    PurchaseInvoiceCancel,
    PurchaseRequestCreate,
    PurchaseRequestConvert,
    PurchaseRequestReject,
    PurchaseApprovalSettingsUpdate,
    LowStockSuggestionsCreate,
    UnitOfMeasureCreate,
    UnitOfMeasureUpdate,
    UnitConvertPreview,
    PurchaseInvoiceCreate,
    PurchaseInvoiceOcrApply,
    PurchaseInvoiceUpdate,
    PurchaseReturnCreate,
    PurchaseReturnCancel,
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
    RecurringSkipNext,
    RefreshRequest,
    SalesInvoiceCreate,
    SalesOrderCreate,
    SalesOrderCancel,
    SalesInvoiceCancel,
    SalesOrderConfirm,
    SalesQuotationCreate,
    SalesQuotationReject,
    SalesReturnCreate,
    SalesReturnCancel,
    SalesReturnPost,
    SmsTestRequest,
    OpeningStockRequest,
    StockAdjust,
    StockMove,
    StockOut,
    OpeningStockCreate,
    OpeningBalanceCreate,
    AccountUpdate,
    StockTransferCreate,
    StockTransferReject,
    StoreCreate,
    StoreUpdate,
    StoreDrawerSettingsUpdate,
    StoreReorderPolicyUpdate,
    WarehouseReorderPolicyUpdate,
    InventoryFefoSettingsUpdate,
    SupplierPaymentCreate,
    TaxCalculateRequest,
    TaxCreate,
    TaxUpdate,
    TenantCreate,
    TenantProfileUpdate,
    TenantSuspendRequest,
    TenantDeleteConfirm,
    TenantSubscriptionAssign,
    TenantModulesUpdate,
    TenantIndustryChange,
    TenantStoreLimitUpdate,
    TenantMaxStoresOverrideUpdate,
    TransactionCreate,
    EmailTestRequest,
    EmailSettingsUpdate,
    SmsSettingsUpdate,
    TwoFactorConfirm,
    TwoFactorDisable,
    TwoFactorVerify,
    WebAuthnLoginOptions,
    WebAuthnLoginVerify,
    WebAuthnRegisterVerify,
    UserCreate,
    UserUpdate,
    UserStoreMembershipsReplace,
    CustomRoleCreate,
    CustomRoleUpdate,
    BranchCreate,
    BranchUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    ProductUpdate,
    StockCountCreate,
    StockCountCancel,
    StockCountItemsUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)

from app.http_errors import TenantSeedError, http_exception_for_tenant_create_failure
from app import schema_compat
from app.security import (
    create_access_token,
    current_claims,
    hash_password,
    hash_token,
    issue_one_time_token,
    issue_refresh_token,
    require_permission,
    require_platform_permission,
    require_roles,
    resolve_user_permissions,
    validate_password_strength,
    verify_password,
)
from app import totp as totp_svc
from app import platform_staff as platform_staff_svc
from app import platform_reports as platform_reports_svc
from app import user_accounts as user_accounts_svc
from app import hotel as hotel_svc
from app import fmcg as fmcg_svc
from app.rbac import PLATFORM_ROLES, is_platform_owner_role, is_platform_role

api = APIRouter(prefix="/api/v1")
logger = logging.getLogger("ribdigi.api")


def _optional_user_phone(value: str | None) -> str | None:
    """OpenAPI E164PhoneValue → 422; service defense-in-depth → 400."""
    if value is None:
        return None
    try:
        return validate_e164_phone_value(str(value).strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

from app.bi_api import router as business_insights_router

api.include_router(business_insights_router)


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


async def _issue_email_verification(db: AsyncSession, user: m.User, tenant: m.Tenant | None) -> dict:
    """Issue a one-time link and send it. The user row must already be flushed."""
    now = datetime.utcnow()
    prior = (
        await db.execute(
            select(m.AuthToken).where(
                m.AuthToken.user_id == user.id,
                m.AuthToken.purpose == "email_verify",
                m.AuthToken.used_at.is_(None),
            )
        )
    ).scalars().all()
    for row in prior:
        row.used_at = now
    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            purpose="email_verify",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    await db.commit()
    from app import emailer

    try:
        result = await emailer.send_verification_email(
            to=user.email,
            token=raw,
            company_name=getattr(tenant, "company_name", None) if tenant else None,
            tenant=tenant,
        )
    except Exception:
        logger.exception("verification email send failed user_id=%s", user.id)
        result = emailer.EmailResult(sent=False, mode="error", error="send_failed")
    data = {"sent": bool(result.sent), "mode": result.mode}
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["error"] = result.error
        data["email_verification_token"] = raw
    return data


async def tenant_pk(db: AsyncSession, tenant_ref: str) -> str:
    tenant = (
        await db.execute(
            select(m.Tenant).where((m.Tenant.id == tenant_ref) | (m.Tenant.slug == tenant_ref))
        )
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant.id


async def _seed_step(step: str, factory, db: AsyncSession) -> None:
    try:
        async with db.begin_nested():
            await factory()
    except TenantSeedError:
        raise
    except Exception as exc:
        logger.exception("tenant seed failed step=%s", step)
        raise TenantSeedError(step) from exc


async def _seed_optional(step: str, factory, db: AsyncSession) -> None:
    try:
        async with db.begin_nested():
            await factory()
    except Exception:
        logger.exception("tenant seed skipped step=%s", step)


async def seed_tenant_defaults(db: AsyncSession, tenant_id: str) -> None:
    from app.accounting import ensure_default_accounts
    from app import catalog_meta as catalog_meta_svc
    from app import stores as stores_svc
    from app import store_entitlements as store_ent_svc
    from app import customer_groups as customer_groups_svc
    from app.notifications import create_notification

    tenant = await db.get(m.Tenant, tenant_id)
    await _seed_optional(
        "company",
        lambda: schema_compat.ensure_tenant_company(
            db,
            tenant_id,
            name=getattr(tenant, "company_name", None),
            industry=getattr(tenant, "industry", None),
            currency=getattr(tenant, "currency", None),
        ),
        db,
    )
    await _seed_step("chart of accounts", lambda: ensure_default_accounts(db, tenant_id), db)
    await _seed_step("expense categories", lambda: expenses_svc.ensure_default_categories(db, tenant_id), db)
    await _seed_step("product catalog", lambda: catalog_meta_svc.ensure_default_catalog(db, tenant_id), db)
    await _seed_optional(
        "customer groups",
        lambda: customer_groups_svc.ensure_default_groups(db, tenant_id),
        db,
    )
    await _seed_optional(
        "welcome notification",
        lambda: create_notification(
            db,
            tenant_id=tenant_id,
            category="system",
            title="Welcome to RIBDIGI ERP",
            message="Your tenant was provisioned. Complete company setup and add products to begin.",
        ),
        db,
    )

    async def _default_tax() -> None:
        existing = await schema_compat.existing_names(db, "tax_rates", tenant_id)
        if "VAT" in existing:
            return
        await schema_compat.insert_matching_row(
            db,
            "tax_rates",
            {
                "tenant_id": tenant_id,
                "name": "VAT",
                "code": "VAT",
                "rate": 15,
                "tax_type": "vat",
                "pricing_mode": "exclusive",
                "is_reverse_charge": False,
                "is_default": True,
                "is_active": True,
                "company_id": None,
            },
        )

    await _seed_step("default tax rate", _default_tax, db)

    async def _default_store() -> None:
        existing_store = None
        try:
            existing_store = (
                await db.execute(select(m.Store).where(m.Store.tenant_id == tenant_id).limit(1))
            ).scalar_one_or_none()
        except Exception:
            existing_store = None
        if existing_store is not None:
            return
        if tenant is None:
            return
        await store_ent_svc.assert_can_create_store(db, tenant)
        await stores_svc.create_store(
            db,
            tenant_id=tenant_id,
            name="Main Store",
            code="MAIN",
        )

    await _seed_optional("default store", _default_store, db)

    async def _default_departments() -> None:
        await org_units_svc.ensure_default_departments(db, tenant_id)

    await _seed_optional("default departments", _default_departments, db)



async def create_session(
    db: AsyncSession,
    *,
    user: m.User,
    request: Request | None = None,
    login_method: str | None = None,
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
    # Interactive login only — refresh must not fan out user.login.
    if login_method:
        await webhooks_svc.emit_event(
            db,
            tenant_id=user.tenant_id,
            event="user.login",
            data={
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "method": login_method,
                "session_id": session.id,
                "ip": session.ip_address,
            },
        )
    return access, refresh_raw


def _auth_user_payload(user: m.User, *, extra: dict | None = None) -> dict:
    from app.platform_const import home_path_for_principal, principal_for

    principal = principal_for(tenant_id=user.tenant_id, role=user.role)
    payload = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "email_verified": user.email_verified,
        "totp_enabled": bool(user.totp_enabled),
        "principal": principal,
        "redirect_path": home_path_for_principal(principal),
    }
    if extra:
        payload.update(extra)
    return payload


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
async def health(request: Request, deep: bool = False):
    """Liveness by default; pass deep=true for dependency checks (DB/Redis/broker)."""
    from fastapi.responses import JSONResponse

    from app import health as health_svc

    factory = getattr(request.app.state, "session_factory", None)
    body, status_code = await health_svc.assemble_health(deep=deep, session_factory=factory)
    if status_code != 200:
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "data": body,
                "message": "Service unhealthy",
            },
        )
    return env(body)


@api.get("/health/ready")
async def health_ready(request: Request):
    """Readiness probe — always runs deep dependency checks."""
    from fastapi.responses import JSONResponse

    from app import health as health_svc

    factory = getattr(request.app.state, "session_factory", None)
    body, status_code = await health_svc.assemble_health(deep=True, session_factory=factory)
    if status_code != 200:
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "data": body,
                "message": "Service not ready",
            },
        )
    return env(body, "Ready")


@api.get("/metrics")
async def metrics_endpoint():
    """Prometheus text exposition (optional; disable with METRICS_ENABLED=false)."""
    from fastapi.responses import PlainTextResponse

    from app import metrics as metrics_svc

    if not metrics_svc.metrics_enabled():
        raise HTTPException(status_code=404, detail="Metrics disabled")
    return PlainTextResponse(
        metrics_svc.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@api.post("/tenants")
async def create_tenant(
    payload: TenantCreate,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    validate_password_strength(payload.admin_password)
    try:
        password_hash = hash_password(payload.admin_password)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Password is too long. Use 72 characters or fewer.",
        ) from None
    # OpenAPI TenantSlugValue / CompanyNameValue → 422; service defense-in-depth → 400.
    slug = tenants_svc.require_tenant_slug(payload.slug)
    company_name = tenants_svc.require_company_name(payload.company_name)
    admin_email = str(payload.admin_email).strip().lower()
    existing = (
        await db.execute(select(m.Tenant).where(m.Tenant.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug exists")

    industry = tenants_svc.normalize_industry(payload.industry)
    trial_end = tenants_svc.default_trial_ends_at()
    now = datetime.utcnow()
    try:
        tenant = m.Tenant(
            slug=slug,
            company_name=company_name,
            industry=industry,
            currency=payload.currency,
            status="trial",
            trial_ends_at=trial_end,
            trial_notices={},
            package_code="trial",
            subscription_term_unit="months",
            subscription_term_value=max(1, int(settings.TRIAL_DAYS) // 30 or 1),
            subscription_starts_at=now,
            subscription_ends_at=trial_end,
            package_assigned_at=now,
        )
        db.add(tenant)
        await db.flush()

        admin = m.User(
            tenant_id=tenant.id,
            email=admin_email,
            full_name="Company Administrator",
            password_hash=password_hash,
            role="company_admin",
            email_verified=False,
            permissions=permissions_for_role("company_admin"),
        )
        db.add(admin)
        await db.flush()
        await seed_tenant_defaults(db, tenant.id)

        await audit_svc.record_event(
            db,
            tenant_id=tenant.id,
            user_id=claims.get("sub"),
            module="tenants",
            action="tenant_created",
            entity="tenant",
            entity_id=tenant.id,
            details={
                "slug": tenant.slug,
                "admin_email": admin_email,
                "admin_email_verified": False,
                "admin_user_id": admin.id,
                "admin_role": "company_admin",
                "industry": tenant.industry,
                "source": "platform_console",
            },
        )
        await db.flush()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("tenant create failed slug=%s", slug)
        raise http_exception_for_tenant_create_failure(exc) from None

    try:
        email_info = await _issue_email_verification(db, admin, tenant)
        await db.refresh(tenant)
    except Exception as exc:
        logger.exception("tenant create persist/email failed slug=%s", slug)
        raise http_exception_for_tenant_create_failure(exc) from None
    return env(
        {
            "tenant_id": tenant.id,
            "id": tenant.id,
            "slug": tenant.slug,
            "status": tenant.status,
            "admin_email_verified": False,
            "email": email_info,
        },
        "Tenant created. The company admin must verify their email before signing in.",
    )


@api.get("/tenants/me")
async def tenant_me(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    tenant = await tenants_svc.ensure_trial_state(db, tenant)
    if tenant.status == "suspended":
        raise HTTPException(status_code=403, detail="Tenant is suspended")
    company = None
    if claims.get("company_id"):
        company = await db.get(m.Company, claims["company_id"])
        if not company or company.tenant_id != claims["tenant_id"]:
            company = None
    await db.commit()
    return env(await tenants_svc.serialize_tenant_with_store_usage(db, tenant))


@api.patch("/tenants/me")
async def tenant_me_update(
    payload: TenantProfileUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if payload.industry is not None:
        current = (getattr(tenant, "industry", None) or "").strip().lower()
        if payload.industry != current:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Business type is set when the Platform Owner creates the tenant "
                    "and cannot be changed by company users."
                ),
            )
    tenant = await tenants_svc.update_profile(
        db,
        tenant,
        company_name=payload.company_name,
        currency=payload.currency,
        phone=payload.phone,
        email=str(payload.email) if payload.email is not None else None,
        website=payload.website,
        address=payload.address,
        legal_name=payload.legal_name,
        registration_number=payload.registration_number,
        contact_person=payload.contact_person,
        billing_address=payload.billing_address,
        shipping_address=payload.shipping_address,
        timezone=payload.timezone,
        fiscal_year_start=payload.fiscal_year_start,
        tax_jurisdiction=payload.tax_jurisdiction,
        tax_registration_number=payload.tax_registration_number,
        tax_filing_period=payload.tax_filing_period,
        date_format=payload.date_format,
        decimal_separator=payload.decimal_separator,
        thousand_separator=payload.thousand_separator,
        time_format=payload.time_format,
        inactivity_timeout_minutes=payload.inactivity_timeout_minutes,
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
    company = numbering_company or print_templates_company
    if company is None and claims.get("company_id"):
        company = await db.get(m.Company, claims["company_id"])
        if not company or company.tenant_id != claims["tenant_id"]:
            company = None
    data = tenants_svc.serialize_tenant(tenant, company=company)
    msg = "Company profile updated"
    if payload.plan_code is not None and new_plan != previous_plan:
        msg = "Plan metadata updated (billing deferred; no payment processed)"
    return env(data, msg)


@api.post("/tenants/me/suspend")
async def tenant_me_suspend(
    payload: TenantSuspendRequest,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    reason_s = require_honest_narrative(payload.reason, label="suspension reason")
    tenant = await tenants_svc.suspend_tenant(
        db, tenant, reason=reason_s, suspended_by=claims["sub"]
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="suspend",
        entity="tenant",
        entity_id=tenant.id,
        details={"reason": reason_s},
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Tenant suspended; sessions revoked")


@api.post("/tenants/me/activate")
async def tenant_me_activate(
    claims=Depends(require_roles("company_admin", "super_admin", "platform_owner")),
    db: AsyncSession = Depends(get_db),
):
    """Activate own tenant when already authenticated (trial/grace → active).

    Platform owner may also reactivate the protected platform workspace if it
    was mistakenly suspended (recovery path).
    """
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if tenant.status == "suspended":
        slug = (tenant.slug or "").strip().lower()
        tid = (tenant.id or "").strip().lower()
        is_platform_ws = (
            slug in tenants_svc.PROTECTED_TENANT_SLUGS
            or tid in tenants_svc.PROTECTED_TENANT_SLUGS
        )
        if not (is_platform_ws and is_platform_owner_role(claims.get("role"))):
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
    status: Annotated[TenantStatusFilterValue | None, Query()] = None,
    claims=Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
):
    """ADR-137: cross-tenant listing moved to /api/v1/platform/tenants."""
    raise HTTPException(
        status_code=410,
        detail={
            "code": "PLATFORM_API_REQUIRED",
            "message": "Cross-tenant tenant listing moved to /api/v1/platform/tenants (ADR-137).",
            "migrate_to": "/api/v1/platform/tenants",
        },
    )


@api.post("/tenants/{tenant_ref}/suspend")
async def tenant_suspend_by_ref(
    tenant_ref: TenantRefValue,
    payload: TenantSuspendRequest,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    reason_s = require_honest_narrative(payload.reason, label="suspension reason")
    tenant = await tenants_svc.suspend_tenant(
        db, tenant, reason=reason_s, suspended_by=claims["sub"]
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="suspend",
        entity="tenant",
        entity_id=tenant.id,
        details={"reason": reason_s, "target_tenant": tenant.id},
    )


@api.post("/tenants/{tenant_ref}/activate")
async def tenant_activate_by_ref(
    tenant_ref: TenantRefValue,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """ADR-137: cross-tenant activate moved to /api/v1/platform/tenants/{id}/activate."""
    raise HTTPException(
        status_code=410,
        detail={
            "code": "PLATFORM_API_REQUIRED",
            "message": (
                f"Cross-tenant activate moved to /api/v1/platform/tenants/{tenant_ref}/activate "
                "(ADR-137)."
            ),
            "migrate_to": f"/api/v1/platform/tenants/{tenant_ref}/activate",
        },
    )


@api.post("/tenants/{tenant_ref}/delete")
async def tenant_delete_by_ref(
    tenant_ref: TenantRefValue,
    payload: TenantDeleteConfirm,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a company tenant (platform owner only)."""
    if not is_platform_owner_role(claims.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Only the platform owner can delete a tenant",
        )
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    snapshot = await tenants_svc.delete_tenant(
        db,
        tenant,
        actor_role=claims.get("role") or "",
        actor_tenant_id=claims["tenant_id"],
        confirm_slug=payload.confirm_slug,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="delete",
        entity="tenant",
        entity_id=snapshot["id"],
        details={
            "target_tenant": snapshot["id"],
            "slug": snapshot["slug"],
            "company_name": snapshot["company_name"],
        },
    )
    await db.commit()
    return env(snapshot, "Tenant deleted")


@api.post("/tenants/{tenant_ref}/verify-admin")
async def tenant_verify_admin(
    tenant_ref: TenantRefValue,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Platform owner override: mark the company admin verified without the email link."""
    if not is_platform_owner_role(claims.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Only the platform owner can verify an account without the email link",
        )
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    users = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant.id,
                m.User.role == "company_admin",
                m.User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    if not users:
        raise HTTPException(status_code=404, detail="No active company admin on this tenant")
    changed = 0
    for user in users:
        if not user.email_verified:
            user.email_verified = True
            changed += 1
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="admin_email_verified",
        entity="tenant",
        entity_id=tenant.id,
        details={"target_tenant": tenant.id, "admins": len(users), "newly_verified": changed},
    )
    await db.commit()
    return env(
        {
            "tenant_id": tenant.id,
            "slug": tenant.slug,
            "admins": len(users),
            "newly_verified": changed,
        },
        "Company admin verified by the platform owner. They can sign in with this workspace slug.",
    )


@api.post("/tenants/{tenant_ref}/resend-admin-verification")
async def tenant_resend_admin_verification(
    tenant_ref: TenantRefValue,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Send a fresh verification email to each unverified company admin."""
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    users = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant.id,
                m.User.role == "company_admin",
                m.User.is_active == True,  # noqa: E712
                m.User.email_verified == False,  # noqa: E712
            )
        )
    ).scalars().all()
    if not users:
        raise HTTPException(status_code=404, detail="No unverified company admin on this tenant")
    sent = 0
    last: dict = {}
    for user in users:
        last = await _issue_email_verification(db, user, tenant)
        if last.get("sent"):
            sent += 1
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="admin_verification_resent",
        entity="tenant",
        entity_id=tenant.id,
        details={"target_tenant": tenant.id, "admins": len(users), "sent": sent},
    )
    await db.commit()
    return env(
        {"tenant_id": tenant.id, "slug": tenant.slug, "admins": len(users), "sent": sent, "email": last},
        "Verification email sent." if sent else "Verification email was not delivered. Check SMTP, or verify the account yourself.",
    )


@api.get("/packages")
async def packages_catalog(
    claims=Depends(require_platform_permission("platform_packages", "read")),
):
    """List commercial packages and default module sets for the platform owner."""
    return env(
        {
            "packages": packages_svc.list_packages(),
            "packageable_modules": list(packages_svc.PACKAGEABLE_MODULES),
            "always_on_modules": sorted(packages_svc.ALWAYS_ON_MODULES),
        }
    )


@api.post("/tenants/{tenant_ref}/subscription")
async def tenant_assign_subscription(
    tenant_ref: TenantRefValue,
    payload: TenantSubscriptionAssign,
    claims=Depends(require_platform_permission("platform_packages", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Assign package + term (months/years); calculates usage and renewal window."""
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    data = payload.model_dump(exclude_unset=True)
    prev_override = getattr(tenant, "max_stores_override", None)
    tenant = await tenants_svc.assign_subscription(
        db,
        tenant,
        package_code=payload.package_code,
        term_value=payload.term_value,
        term_unit=payload.term_unit,
        start_at=reports_svc.parse_date(payload.start_at),
        activate=payload.activate,
        enabled_modules=payload.enabled_modules,
        max_stores_override=data.get("max_stores_override"),
        apply_max_stores_override="max_stores_override" in data,
        clear_max_stores_override=bool(data.get("clear_max_stores_override")),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="assign_subscription",
        entity="tenant",
        entity_id=tenant.id,
        details={
            "target_tenant": tenant.id,
            "package_code": payload.package_code,
            "term_value": payload.term_value,
            "term_unit": payload.term_unit,
            "max_stores_override": getattr(tenant, "max_stores_override", None),
            "max_stores_override_prev": prev_override,
        },
    )
    await db.commit()
    return env(
        await tenants_svc.serialize_tenant_with_store_usage(db, tenant),
        "Subscription assigned",
    )


@api.patch("/tenants/{tenant_ref}/industry")
async def tenant_update_industry(
    tenant_ref: TenantRefValue,
    payload: TenantIndustryChange,
    claims=Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Platform Owner only — exceptional audited business-type change."""
    if not is_platform_owner_role(claims.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Only the Platform Owner can change a tenant business type",
        )
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    previous = getattr(tenant, "industry", None)
    reason = require_honest_narrative(payload.reason, label="business type change reason")
    tenant = await tenants_svc.update_profile(
        db, tenant, industry=payload.industry
    )
    await schema_compat.sync_company_industry(db, tenant.id, tenant.industry)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="industry_changed",
        entity="tenant",
        entity_id=tenant.id,
        details={
            "target_tenant": tenant.id,
            "previous_industry": previous,
            "industry": tenant.industry,
            "reason": reason,
        },
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Business type updated")


@api.patch("/tenants/{tenant_ref}/modules")
async def tenant_update_modules(
    tenant_ref: TenantRefValue,
    payload: TenantModulesUpdate,
    claims=Depends(require_platform_permission("platform_packages", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Override which modules a tenant may use (package feature control)."""
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    if payload.reset_to_package:
        tenant = await tenants_svc.clear_module_override(db, tenant)
    elif payload.enabled_modules is not None:
        tenant = await tenants_svc.set_enabled_modules(
            db, tenant, payload.enabled_modules, commit=False
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide enabled_modules or set reset_to_package=true",
        )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="update_modules",
        entity="tenant",
        entity_id=tenant.id,
        details={
            "target_tenant": tenant.id,
            "reset_to_package": payload.reset_to_package,
            "enabled_modules": tenant.enabled_modules,
        },
    )
    await db.commit()
    return env(tenants_svc.serialize_tenant(tenant), "Tenant modules updated")


@api.get("/tenants/{tenant_ref}/usage")
async def tenant_usage(
    tenant_ref: TenantRefValue,
    claims=Depends(require_platform_permission("platform_packages", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    return env(await tenants_svc.serialize_tenant_with_store_usage(db, tenant))


@api.patch("/tenants/{tenant_ref}/store-entitlement")
async def tenant_store_entitlement_override(
    tenant_ref: TenantRefValue,
    payload: TenantMaxStoresOverrideUpdate,
    claims=Depends(require_platform_permission("platform_packages", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Platform override for max stores (null/clear → package catalog default / unlimited)."""
    tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    prev = getattr(tenant, "max_stores_override", None)
    new_val = None if payload.clear else payload.max_stores_override
    if payload.clear:
        new_val = None
    elif payload.max_stores_override is None and not payload.clear:
        # explicit null without clear flag also clears
        new_val = None
    tenant = await tenants_svc.set_max_stores_override(db, tenant, new_val)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="tenants",
        action="set_max_stores_override",
        entity="tenant",
        entity_id=tenant.id,
        details={
            "target_tenant": tenant.id,
            "old": prev,
            "new": getattr(tenant, "max_stores_override", None),
        },
    )
    await db.commit()
    return env(
        await tenants_svc.serialize_tenant_with_store_usage(db, tenant),
        "Store entitlement override updated",
    )


@api.patch("/tenants/me/store-limit")
async def tenant_me_store_limit(
    payload: TenantStoreLimitUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Company (== Tenant) store allocation cap within subscription entitlement."""
    tenants_svc.assert_writable(claims)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    prev = getattr(tenant, "store_limit", None)
    tenant = await tenants_svc.set_store_limit(db, tenant, payload.store_limit)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="stores",
        action="set_store_limit",
        entity="tenant",
        entity_id=tenant.id,
        details={"old": prev, "new": getattr(tenant, "store_limit", None)},
    )
    await db.commit()
    return env(
        await tenants_svc.serialize_tenant_with_store_usage(db, tenant),
        "Store allocation updated",
    )


@api.get("/platform/staff")
async def platform_staff_list(
    claims=Depends(require_platform_permission("platform_staff", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await platform_staff_svc.list_platform_staff(db, tenant_id=claims["tenant_id"])
    return env([platform_staff_svc.serialize_staff(u) for u in rows])


@api.get("/platform/app-users")
async def platform_app_users_list(
    claims=Depends(require_platform_permission("platform_staff", "read")),
    db: AsyncSession = Depends(get_db),
):
    """App users on the platform workspace who do not yet have software-owner dashboard access."""
    rows = await platform_staff_svc.list_app_users(db, tenant_id=claims["tenant_id"])
    return env([platform_staff_svc.serialize_staff(u) for u in rows])


@api.get("/platform/roles")
async def platform_roles_catalog(
    claims=Depends(require_platform_permission("platform_staff", "read")),
):
    from app.rbac import ROLE_LABELS, ROLE_PERMISSIONS

    return env(
        [
            {
                "key": r,
                "label": ROLE_LABELS.get(r, r),
                "permissions": ROLE_PERMISSIONS.get(r, {}),
            }
            for r in sorted(PLATFORM_ROLES)
        ]
    )


@api.post("/platform/staff")
async def platform_staff_create(
    payload: PlatformStaffCreate,
    claims=Depends(require_platform_permission("platform_staff", "write")),
    db: AsyncSession = Depends(get_db),
):
    user = await platform_staff_svc.create_platform_staff(
        db,
        tenant_id=claims["tenant_id"],
        actor_role=claims.get("role") or "",
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
        phone=payload.phone,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="platform_staff",
        action="create",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "role": user.role, "email_verified": False},
    )
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    email_info = await _issue_email_verification(db, user, tenant)
    data = platform_staff_svc.serialize_staff(user)
    data["verification_email"] = email_info
    return env(data, "Platform staff created. They must verify their email before signing in.")


@api.post("/platform/staff/{user_id}/verify-email")
async def platform_staff_verify_email(
    user_id: UuidIdValue,
    claims=Depends(require_platform_permission("platform_staff", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Platform owner override: activate a staff account without the email link."""
    if not is_platform_owner_role(claims.get("role")):
        raise HTTPException(status_code=403, detail="Only the platform owner can verify a staff account")
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == claims["tenant_id"])
        )
    ).scalar_one_or_none()
    if not user or not is_platform_role(user.role):
        raise HTTPException(status_code=404, detail="Platform staff user not found")
    user.email_verified = True
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="platform_staff",
        action="email_verified",
        entity="user",
        entity_id=user.id,
        details={"email": user.email},
    )
    await db.commit()
    return env(platform_staff_svc.serialize_staff(user), "Staff account verified. They can sign in.")


@api.post("/platform/staff/{user_id}/resend-verification")
async def platform_staff_resend_verification(
    user_id: UuidIdValue,
    claims=Depends(require_platform_permission("platform_staff", "write")),
    db: AsyncSession = Depends(get_db),
):
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == claims["tenant_id"])
        )
    ).scalar_one_or_none()
    if not user or not is_platform_role(user.role):
        raise HTTPException(status_code=404, detail="Platform staff user not found")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="This staff account is already verified")
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    email_info = await _issue_email_verification(db, user, tenant)
    return env(
        {"id": user.id, "email": email_info},
        "Verification email sent."
        if email_info.get("sent")
        else "Verification email was not delivered. Check SMTP, or verify the account yourself.",
    )


@api.post("/platform/staff/grant")
async def platform_staff_grant(
    payload: PlatformGrantAccess,
    claims=Depends(require_platform_permission("platform_staff", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Grant an existing app user permission to open the software-owner dashboard."""
    prev = (
        await db.execute(
            select(m.User).where(
                m.User.id == payload.user_id,
                m.User.tenant_id == claims["tenant_id"],
            )
        )
    ).scalar_one_or_none()
    prev_role = prev.role if prev else None
    user = await platform_staff_svc.grant_dashboard_access(
        db,
        tenant_id=claims["tenant_id"],
        actor_id=claims["sub"],
        actor_role=claims.get("role") or "",
        user_id=payload.user_id,
        role=payload.role,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="platform_staff",
        action="grant_dashboard",
        entity="user",
        entity_id=user.id,
        details={"from_role": prev_role, "to_role": user.role, "email": user.email},
    )
    await db.commit()
    return env(
        platform_staff_svc.serialize_staff(user),
        "Software owner dashboard access granted",
    )


@api.post("/platform/staff/{user_id}/revoke")
async def platform_staff_revoke(
    user_id: UuidIdValue,
    payload: PlatformRevokeAccess,
    claims=Depends(require_platform_permission("platform_staff", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Revoke software-owner dashboard access; account stays as an app user."""
    user = await platform_staff_svc.revoke_dashboard_access(
        db,
        tenant_id=claims["tenant_id"],
        actor_id=claims["sub"],
        actor_role=claims.get("role") or "",
        user_id=user_id,
        fallback_role=payload.fallback_role,
    )
    rows = (
        await db.execute(
            select(m.AuthSession).where(
                m.AuthSession.user_id == user.id,
                m.AuthSession.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    now = datetime.utcnow()
    for s in rows:
        s.revoked_at = now
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="platform_staff",
        action="revoke_dashboard",
        entity="user",
        entity_id=user.id,
        details={"role": user.role, "email": user.email},
    )
    await db.commit()
    return env(
        platform_staff_svc.serialize_staff(user),
        "Software owner dashboard access revoked",
    )


@api.patch("/platform/staff/{user_id}")
async def platform_staff_update(
    user_id: UuidIdValue,
    payload: PlatformStaffUpdate,
    claims=Depends(require_platform_permission("platform_staff", "write")),
    db: AsyncSession = Depends(get_db),
):
    user = await platform_staff_svc.update_platform_staff(
        db,
        tenant_id=claims["tenant_id"],
        actor_id=claims["sub"],
        actor_role=claims.get("role") or "",
        user_id=user_id,
        full_name=payload.full_name,
        email=str(payload.email) if payload.email is not None else None,
        role=payload.role,
        phone=payload.phone,
        is_active=payload.is_active,
        password=payload.password,
    )
    if payload.is_active is False or payload.password is not None:
        rows = (
            await db.execute(
                select(m.AuthSession).where(
                    m.AuthSession.user_id == user.id,
                    m.AuthSession.revoked_at.is_(None),
                )
            )
        ).scalars().all()
        now = datetime.utcnow()
        for s in rows:
            s.revoked_at = now
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="platform_staff",
        action="update",
        entity="user",
        entity_id=user.id,
        details={
            "role": user.role,
            "is_active": user.is_active,
            "email_changed": payload.email is not None,
            "password_changed": payload.password is not None,
        },
    )
    await db.commit()
    return env(platform_staff_svc.serialize_staff(user), "Platform staff updated")


@api.delete("/platform/staff/{user_id}")
async def platform_staff_delete(
    user_id: UuidIdValue,
    claims=Depends(require_platform_permission("platform_staff", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a platform staff account (platform owner / super_admin only)."""
    snapshot = await platform_staff_svc.delete_platform_staff(
        db,
        tenant_id=claims["tenant_id"],
        actor_id=claims["sub"],
        actor_role=claims.get("role") or "",
        user_id=user_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="platform_staff",
        action="delete",
        entity="user",
        entity_id=snapshot["id"],
        details={"email": snapshot["email"], "role": snapshot["role"], "full_name": snapshot["full_name"]},
    )
    await db.commit()
    return env(snapshot, "Platform staff account deleted")


@api.get("/platform/reports")
async def platform_reports_all(
    claims=Depends(require_platform_permission("platform_reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_reports_svc.build_all_platform_reports(db))


@api.get("/platform/reports/summary")
async def platform_reports_summary(
    claims=Depends(require_platform_permission("platform_reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_reports_svc.build_platform_summary(db))


@api.get("/platform/reports/subscriptions")
async def platform_reports_subscriptions(
    claims=Depends(require_platform_permission("platform_reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_reports_svc.build_subscription_usage_report(db))


@api.get("/platform/reports/packages")
async def platform_reports_packages(
    claims=Depends(require_platform_permission("platform_reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await platform_reports_svc.build_package_distribution_report(db))


@api.get("/platform/reports/trials")
async def platform_reports_trials(
    # omit → 45; 0/negative/>365 → **422** (was free int; service silently clamped 1–365)
    within_days: Annotated[int, Query(ge=1, le=365)] = 45,
    claims=Depends(require_platform_permission("platform_reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await platform_reports_svc.build_trial_expirations_report(
            db, within_days=max(1, min(within_days, 365))
        )
    )


@api.get("/settings/email")
async def settings_email_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import emailer

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(emailer.email_status(tenant))


@api.patch("/settings/email")
async def settings_email_patch(
    payload: EmailSettingsUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.email_settings import apply_email_settings_update

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    data = apply_email_settings_update(tenant, payload.model_dump(exclude_unset=True))
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="settings",
        action="email_settings_update",
        entity="email",
        details={
            "host": data.get("host"),
            "from_email": data.get("from_email"),
            "tenant_override": data.get("tenant_override"),
            "has_password": data.get("has_password"),
        },
    )
    await db.commit()
    return env(data, "Email settings updated")


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
    db: AsyncSession = Depends(get_db),
):
    from app import sms as sms_svc

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(sms_svc.sms_status(tenant))


@api.patch("/settings/sms")
async def settings_sms_patch(
    payload: SmsSettingsUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.sms_settings import apply_sms_settings_update

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    data = apply_sms_settings_update(tenant, payload.model_dump(exclude_unset=True))
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="settings",
        action="sms_settings_update",
        entity="sms",
        details={
            "from_number": data.get("from_number"),
            "account_sid_set": data.get("account_sid_set"),
            "tenant_override": data.get("tenant_override"),
            "has_auth_token": data.get("has_auth_token"),
        },
    )
    await db.commit()
    return env(data, "SMS settings updated")


@api.get("/settings/sms/export")
async def settings_sms_export(
    claims=Depends(require_roles("company_admin", "super_admin")),
):
    """Stage 135 S1 — SMS/Twilio settings CSV (auth token / raw SID never included)."""
    text = finance_ops_export_svc.export_sms_settings_csv()
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="sms_settings_export.csv"'
        },
    )


@api.get("/settings/storage")
async def settings_storage_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
):
    return env(storage_svc.storage_status())


@api.get("/settings/print")
async def settings_print_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.print_branding import print_branding_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(print_branding_settings(tenant))


@api.patch("/settings/print")
async def settings_print_patch(
    payload: PrintBrandingUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.print_branding import apply_print_branding_update

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    data = apply_print_branding_update(
        tenant,
        payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return env(data, "Print branding updated")


@api.post("/settings/sms/test")
async def settings_sms_test(
    payload: SmsTestRequest | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import sms as sms_svc

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    user = await db.get(m.User, claims["sub"])
    to = (payload.to if payload and payload.to else None) or (user.phone if user else None)
    if not to:
        raise HTTPException(
            status_code=400,
            detail="No recipient phone — set your profile phone or pass `to`",
        )
    result = await sms_svc.send_test_sms(to=to, tenant=tenant)
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

    if not user.email_verified:
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
        raise HTTPException(
            status_code=403,
            detail={
                "code": "EMAIL_NOT_VERIFIED",
                "message": "Verify your email before signing in",
            },
        )

    from app import webauthn_svc as webauthn

    has_webauthn = await webauthn.user_has_webauthn(db, user.id)
    needs_2fa = totp_svc.login_2fa_enabled() and (bool(user.totp_enabled) or has_webauthn)
    methods: list[str] = []
    if user.totp_enabled:
        methods.append("totp")
    if has_webauthn:
        methods.append("webauthn")

    # 2FA challenge when login MFA is enabled and TOTP and/or passkeys are enrolled
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

    access, refresh = await create_session(
        db,
        user=user,
        request=request,
        login_method="totp" if (needs_2fa and payload.totp_code) else "password",
    )
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
    from app.platform_const import home_path_for_principal, principal_for

    principal = principal_for(tenant_id=user.tenant_id, role=user.role)
    return env(
        {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_enroll_2fa": totp_svc.must_enroll_2fa(user.role, has_mfa=has_mfa),
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

    access, refresh = await create_session(
        db, user=user, request=request, login_method="totp"
    )
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
    from app.platform_const import home_path_for_principal, principal_for

    principal = principal_for(tenant_id=user.tenant_id, role=user.role)
    return env(
        {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_enroll_2fa": False,
            "principal": principal,
            "redirect_path": home_path_for_principal(principal),
            "user": _auth_user_payload(user, extra={"totp_enabled": True}),
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
            "must_enroll_2fa": totp_svc.must_enroll_2fa(user.role, has_mfa=has_mfa),
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
        db, user, credential=payload.credential.model_dump(mode="json"), name=payload.name
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


@api.get("/auth/webauthn/credentials/export")
async def webauthn_credentials_export(
    claims=Depends(current_claims), db: AsyncSession = Depends(get_db)
):
    """Stage 128 P1 — passkey inventory CSV (public_key / credential_id excluded)."""
    text = await session_passkey_doc_export_svc.export_passkeys_csv(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"]
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="passkeys_export.csv"'},
    )


@api.delete("/auth/webauthn/credentials/{credential_id}")
async def webauthn_delete_credential(
    credential_id: UuidIdValue,
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
    await webauthn.verify_authentication(
        db, user, credential=payload.credential.model_dump(mode="json")
    )
    access, refresh = await create_session(
        db, user=user, request=request, login_method="webauthn"
    )
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
    from app.platform_const import home_path_for_principal, principal_for

    principal = principal_for(tenant_id=user.tenant_id, role=user.role)
    return env(
        {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_enroll_2fa": False,
            "principal": principal,
            "redirect_path": home_path_for_principal(principal),
            "user": _auth_user_payload(
                user, extra={"totp_enabled": bool(user.totp_enabled), "webauthn_enabled": True}
            ),
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
    if totp_svc.login_2fa_enabled() and totp_svc.role_requires_2fa(user.role):
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
async def list_sessions(
    status: str | None = None,
    active_only: bool = False,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Stage 128 S1 — status / active_only for honest session lists (caller only)."""
    status_n = (status or "").strip().lower() or None
    if status_n and status_n not in {"active", "revoked", "all"}:
        raise HTTPException(status_code=400, detail="status must be active, revoked, or all")
    rows = await session_passkey_doc_export_svc.list_user_sessions(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        status=status_n,
        active_only=active_only,
    )
    return env(
        [
            session_passkey_doc_export_svc.serialize_session(s, current_jti=claims.get("jti"))
            for s in rows
        ]
    )


@api.get("/auth/sessions/export")
async def sessions_export(
    status: str | None = None,
    active_only: bool = False,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Stage 128 S1 — sessions CSV export (refresh-token secrets never included)."""
    status_n = (status or "").strip().lower() or None
    if status_n and status_n not in {"active", "revoked", "all"}:
        raise HTTPException(status_code=400, detail="status must be active, revoked, or all")
    text = await session_passkey_doc_export_svc.export_sessions_csv(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        current_jti=claims.get("jti"),
        status=status_n,
        active_only=active_only,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sessions_export.csv"'},
    )


@api.get("/auth/tenant-sessions")
async def list_tenant_sessions(
    status: str | None = None,
    active_only: bool = False,
    user_id: str | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 129 A1 — tenant-wide session inventory (no refresh-token secrets)."""
    status_n = (status or "").strip().lower() or None
    if status_n and status_n not in {"active", "revoked", "all"}:
        raise HTTPException(status_code=400, detail="status must be active, revoked, or all")
    rows = await admin_ops_export_svc.list_tenant_sessions(
        db,
        tenant_id=claims["tenant_id"],
        status=status_n,
        active_only=active_only,
        user_id=user_id,
    )
    users = await admin_ops_export_svc.user_map(
        db, claims["tenant_id"], {r.user_id for r in rows}
    )
    return env(
        [
            admin_ops_export_svc.serialize_tenant_session(s, users.get(s.user_id))
            for s in rows
        ]
    )


@api.get("/auth/tenant-sessions/export")
async def tenant_sessions_export(
    status: str | None = None,
    active_only: bool = False,
    user_id: str | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 129 A1 — tenant session inventory CSV (refresh-token secrets never included)."""
    status_n = (status or "").strip().lower() or None
    if status_n and status_n not in {"active", "revoked", "all"}:
        raise HTTPException(status_code=400, detail="status must be active, revoked, or all")
    text = await admin_ops_export_svc.export_tenant_sessions_csv(
        db,
        tenant_id=claims["tenant_id"],
        status=status_n,
        active_only=active_only,
        user_id=user_id,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="tenant_sessions_export.csv"'
        },
    )


@api.delete("/auth/sessions/{session_id}")
async def revoke_session(
    session_id: UuidIdValue,
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

        tenant = await db.get(m.Tenant, tenant_id)
        email_result = await emailer.send_password_reset_email(
            to=user.email, token=raw, tenant=tenant
        )
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
    return env({"verified": True, "email": user.email}, "Email verified")


@api.post("/auth/resend-verification")
async def resend_verification(
    payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)
):
    """Neutral resend — does not reveal whether the account exists or is verified."""
    tenant_id = await tenant_pk(db, payload.tenant_id)
    user = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == tenant_id, m.User.email == payload.email)
        )
    ).scalar_one_or_none()
    data: dict = {"requested": True}
    if user and user.is_active and not user.email_verified:
        # Invalidate unused prior verify tokens for this user
        prior = (
            await db.execute(
                select(m.AuthToken).where(
                    m.AuthToken.user_id == user.id,
                    m.AuthToken.purpose == "email_verify",
                    m.AuthToken.used_at.is_(None),
                )
            )
        ).scalars().all()
        now = datetime.utcnow()
        for row in prior:
            row.used_at = now
        raw, token_hash, expires = issue_one_time_token()
        db.add(
            m.AuthToken(
                tenant_id=tenant_id,
                user_id=user.id,
                purpose="email_verify",
                token_hash=token_hash,
                expires_at=expires,
            )
        )
        await db.commit()
        from app import emailer

        tenant = await db.get(m.Tenant, tenant_id)
        email_result = await emailer.send_verification_email(
            to=user.email,
            token=raw,
            company_name=tenant.company_name if tenant else None,
            tenant=tenant,
        )
        data["email"] = {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        }
        if settings.DEBUG or settings.APP_ENV.lower() != "production":
            data["verification_token"] = raw
    return env(data, "If the account exists and needs verification, a link was sent")


STAFF_GUIDE_NAME = "RIBDIGI-ERP-Customer-User-Guide.pdf"
STAFF_GUIDE_PATHS = (
    FsPath("/app/guides") / STAFF_GUIDE_NAME,
    FsPath(__file__).resolve().parents[1] / "guides" / STAFF_GUIDE_NAME,
)


@api.get("/staff-guide")
async def download_staff_guide(
    claims=Depends(require_permission("staff_guide", "download")),
):
    """Authenticated tenant download of the staff user guide (not Company Admin only)."""
    for path in STAFF_GUIDE_PATHS:
        if path.is_file():
            return FileResponse(
                path,
                media_type="application/pdf",
                filename=STAFF_GUIDE_NAME,
                headers={"Cache-Control": "private, no-store"},
            )
    raise HTTPException(status_code=404, detail="Guide file is not available")


@api.get("/me")
async def me(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    from app.platform_const import home_path_for_principal, principal_for

    user = await db.get(m.User, claims["sub"])
    perms = user.permissions or permissions_for_role(user.role)
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    usage = packages_svc.usage_snapshot(tenant) if tenant else None
    return env(
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant.company_name if tenant else None,
            "tenant_has_logo": bool(getattr(tenant, "logo_url", None)) if tenant else False,
            "email_verified": user.email_verified,
            "permissions": perms,
            "record_scope": record_scope_from_permissions(user.role, perms if isinstance(perms, dict) else None),
            "package_code": claims.get("package_code") or (getattr(tenant, "package_code", None) if tenant else "trial"),
            "enabled_modules": claims.get("enabled_modules")
            or (packages_svc.resolve_enabled_modules(tenant) if tenant else []),
            "industry": claims.get("industry")
            or (getattr(tenant, "industry", None) if tenant else "retail")
            or "retail",
            "subscription": usage,
            "inactivity_timeout_minutes": int(
                getattr(tenant, "inactivity_timeout_minutes", None) or 30
            )
            if tenant
            else 30,
            "company_name": getattr(tenant, "company_name", None) if tenant else None,
            "has_logo": bool(getattr(tenant, "logo_url", None)) if tenant else False,
            **totp_svc.status_payload(user),
        }
    )


@api.get("/workspace")
async def get_workspace(claims=Depends(current_claims), db: AsyncSession = Depends(get_db)):
    """Current workspace + switchable companies (ADR-490)."""
    user = await db.get(m.User, claims["sub"])
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    companies = await companies_svc.list_companies_for_user(
        db,
        tenant_id=claims["tenant_id"],
        user=user,
        tenant_admin=workspace_svc.is_tenant_admin_role(user.role),
    )
    return env(
        {
            "workspace_kind": claims.get("workspace_kind"),
            "company_id": claims.get("company_id"),
            "tenant_id": claims["tenant_id"],
            "tenant_name": tenant.company_name if tenant else None,
            "tenant_has_logo": bool(getattr(tenant, "logo_url", None)) if tenant else False,
            "tenant_admin": workspace_svc.is_tenant_admin_role(user.role),
            "companies": [
                await companies_svc.serialize_company_async(db, c)
                for c in companies
                if c.is_active
            ],
        }
    )


@api.get("/business-types")
async def list_business_types(
    claims=Depends(current_claims), db: AsyncSession = Depends(get_db)
):
    return env(await companies_svc.list_business_types(db))


@api.get("/companies")
async def list_companies(
    claims=Depends(require_permission("companies", "read")),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(m.User, claims["sub"])
    rows = await companies_svc.list_companies_for_user(
        db,
        tenant_id=claims["tenant_id"],
        user=user,
        tenant_admin=workspace_svc.is_tenant_admin_role(user.role),
    )
    return env([await companies_svc.serialize_company_async(db, c) for c in rows])


@api.post("/companies")
async def create_company(
    payload: dict,
    claims=Depends(require_permission("companies", "write")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("workspace_kind") != "tenant":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_WORKSPACE_REQUIRED",
                "message": "Create companies from the tenant workspace.",
            },
        )
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    user = await db.get(m.User, claims["sub"])
    if not workspace_svc.is_tenant_admin_role(user.role):
        raise HTTPException(status_code=403, detail="Tenant administrator required")
    co = await companies_svc.create_company(db, tenant=tenant, actor=user, payload=payload or {})
    await seed_tenant_defaults(db, tenant.id, company_id=co.id)
    await audit_svc.record_event(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        module="companies",
        action="create",
        entity="company",
        entity_id=co.id,
        details={"name": co.name, "code": co.code, "company_id": co.id},
    )
    await db.commit()
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=201,
        content=env(await companies_svc.serialize_company_async(db, co), "Company created"),
    )


@api.get("/companies/{company_id}")
async def get_company(
    company_id: str,
    claims=Depends(require_permission("companies", "read")),
    db: AsyncSession = Depends(get_db),
):
    co = await companies_svc.get_company(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    user = await db.get(m.User, claims["sub"])
    if not workspace_svc.is_tenant_admin_role(user.role):
        mems = await workspace_svc.list_user_memberships(
            db, tenant_id=claims["tenant_id"], user_id=user.id
        )
        if not any(mrow.company_id == company_id for mrow in mems):
            raise HTTPException(status_code=404, detail="Company not found")
    return env(await companies_svc.serialize_company_async(db, co))


@api.patch("/companies/{company_id}")
async def patch_company(
    company_id: str,
    payload: dict,
    claims=Depends(require_permission("companies", "write")),
    db: AsyncSession = Depends(get_db),
):
    companies_svc.assert_can_manage_company_branding(claims, company_id)
    tenants_svc.assert_writable(claims)
    co = await companies_svc.get_company(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    co = await companies_svc.update_company(db, company=co, payload=payload or {})
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="companies",
        action="update",
        entity="company",
        entity_id=co.id,
        details={"name": co.name},
        company_id=co.id,
    )
    await db.commit()
    return env(await companies_svc.serialize_company_async(db, co), "Company updated")


@api.get("/tenant/store-entitlement")
async def tenant_store_entitlement(
    claims=Depends(require_permission("companies", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Tenant Admin view of subscription store allowance + per-company allocations."""
    from app import store_entitlements as store_ent_svc

    if claims.get("workspace_kind") not in {None, "tenant"} and not claims.get("tenant_admin"):
        # Allow tenant admins even if header omitted; company workspace still OK for read of own tenant.
        pass
    user = await db.get(m.User, claims["sub"])
    if not workspace_svc.is_tenant_admin_role(user.role if user else None):
        raise HTTPException(status_code=403, detail="Tenant administrator required")
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    entitlement = await store_ent_svc.get_tenant_store_entitlement(db, tenant)
    allocations = await store_ent_svc.store_usage_by_company(db, tenant_id=tenant.id)
    return env(
        {"entitlement": entitlement, "companies": allocations},
        "Store entitlement",
    )


@api.get("/companies/{company_id}/store-entitlement")
async def company_store_entitlement(
    company_id: str,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import store_entitlements as store_ent_svc

    tenant = await db.get(m.Tenant, claims["tenant_id"])
    co = await companies_svc.get_company(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    user = await db.get(m.User, claims["sub"])
    if not workspace_svc.is_tenant_admin_role(user.role if user else None):
        if claims.get("company_id") and claims.get("company_id") != company_id:
            raise HTTPException(status_code=404, detail="Company not found")
        mems = await workspace_svc.list_user_memberships(
            db, tenant_id=claims["tenant_id"], user_id=user.id
        )
        if not any(mrow.company_id == company_id for mrow in mems):
            raise HTTPException(status_code=404, detail="Company not found")
    data = await store_ent_svc.get_company_store_entitlement(
        db, tenant=tenant, company=co
    )
    return env(data, "Company store entitlement")


@api.patch("/companies/{company_id}/store-limit")
async def patch_company_store_limit(
    company_id: str,
    payload: CompanyStoreLimitUpdate,
    claims=Depends(require_permission("companies", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Tenant Admin allocates Store capacity to a Company (never exceeds tenant entitlement)."""
    from app import store_entitlements as store_ent_svc

    if claims.get("workspace_kind") != "tenant":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_WORKSPACE_REQUIRED",
                "message": "Manage store allocations from the tenant workspace.",
            },
        )
    user = await db.get(m.User, claims["sub"])
    if not workspace_svc.is_tenant_admin_role(user.role if user else None):
        raise HTTPException(status_code=403, detail="Tenant administrator required")
    tenants_svc.assert_writable(claims)
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    co = await companies_svc.get_company(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    prev = getattr(co, "store_limit", None)
    co = await store_ent_svc.set_company_store_limit(
        db, tenant=tenant, company=co, store_limit=payload.store_limit
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="companies",
        action="store_allocation_updated",
        entity="company",
        entity_id=co.id,
        details={
            "company_id": co.id,
            "from": prev,
            "to": co.store_limit,
        },
        company_id=co.id,
    )
    await db.commit()
    entitlement = await store_ent_svc.get_company_store_entitlement(
        db, tenant=tenant, company=co
    )
    return env(entitlement, "Company store allocation updated")


@api.post("/companies/{company_id}/logo")
async def company_logo_upload(
    company_id: str,
    file: UploadFile = File(...),
    claims=Depends(require_permission("companies", "write")),
    db: AsyncSession = Depends(get_db),
):
    companies_svc.assert_can_manage_company_branding(claims, company_id)
    tenants_svc.assert_writable(claims)
    co = await companies_svc.get_company(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="logos",
        upload=file,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    if co.logo_url:
        storage_svc.delete_key(co.logo_url, tenant_id=claims["tenant_id"])
    co.logo_url = stored.key
    co.updated_at = datetime.utcnow()
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="companies",
        action="logo_upload",
        entity="company",
        entity_id=co.id,
        details={"key": stored.key, "size": stored.size, "content_type": stored.content_type},
        company_id=co.id,
    )
    await db.commit()
    return env(
        {
            **(await companies_svc.serialize_company_async(db, co)),
            "uploaded": {
                "key": stored.key,
                "size": stored.size,
                "content_type": stored.content_type,
                "filename": stored.original_filename,
            },
        },
        "Company logo uploaded",
    )


@api.get("/companies/{company_id}/logo")
async def company_logo_get(
    company_id: str,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    co = await companies_svc.get_company(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    # Members or tenant admins may view; block cross-tenant via get_company.
    if claims.get("workspace_kind") == "company" and claims.get("company_id") != company_id:
        user = await db.get(m.User, claims["sub"])
        if not workspace_svc.is_tenant_admin_role(user.role):
            mems = await workspace_svc.list_user_memberships(
                db, tenant_id=claims["tenant_id"], user_id=user.id
            )
            if not any(mrow.company_id == company_id for mrow in mems):
                raise HTTPException(status_code=404, detail="Company not found")
    if not co.logo_url:
        raise HTTPException(status_code=404, detail="No logo uploaded")
    return storage_svc.media_response(co.logo_url, tenant_id=claims["tenant_id"])


@api.delete("/companies/{company_id}/logo")
async def company_logo_delete(
    company_id: str,
    claims=Depends(require_permission("companies", "write")),
    db: AsyncSession = Depends(get_db),
):
    companies_svc.assert_can_manage_company_branding(claims, company_id)
    tenants_svc.assert_writable(claims)
    co = await companies_svc.get_company(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    if not co.logo_url:
        raise HTTPException(status_code=404, detail="No logo uploaded")
    storage_svc.delete_key(co.logo_url, tenant_id=claims["tenant_id"])
    co.logo_url = None
    co.updated_at = datetime.utcnow()
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="companies",
        action="logo_delete",
        entity="company",
        entity_id=co.id,
        company_id=co.id,
    )
    await db.commit()
    return env(await companies_svc.serialize_company_async(db, co), "Company logo removed")


@api.get("/companies/{company_id}/memberships")
async def list_company_memberships(
    company_id: str,
    claims=Depends(require_permission("companies", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List user↔company memberships (tenant account admin)."""
    rows = await companies_svc.list_company_memberships(
        db, tenant_id=claims["tenant_id"], company_id=company_id
    )
    return env(rows)


@api.post("/companies/{company_id}/memberships")
async def assign_company_membership(
    company_id: str,
    payload: dict,
    claims=Depends(require_permission("companies", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Assign or reactivate a user on a company (does not grant tenant-wide ops)."""
    user_id = (payload or {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    role = (payload or {}).get("role") or "cashier"
    row = await companies_svc.assign_company_membership(
        db,
        tenant_id=claims["tenant_id"],
        company_id=company_id,
        user_id=user_id,
        role=role,
    )
    user = await db.get(m.User, user_id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="companies",
        action="membership_assign",
        entity="user_company_membership",
        entity_id=row.id,
        details={"company_id": company_id, "member_user_id": user_id, "role": row.role},
    )
    await db.commit()
    return env(companies_svc.serialize_membership(row, user=user), "Membership assigned")


@api.delete("/companies/{company_id}/memberships/{user_id}")
async def revoke_company_membership(
    company_id: str,
    user_id: str,
    claims=Depends(require_permission("companies", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user's company membership (ops access revoked)."""
    row = await companies_svc.revoke_company_membership(
        db,
        tenant_id=claims["tenant_id"],
        company_id=company_id,
        user_id=user_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="companies",
        action="membership_revoke",
        entity="user_company_membership",
        entity_id=row.id,
        details={"company_id": company_id, "member_user_id": user_id},
    )
    await db.commit()
    return env(companies_svc.serialize_membership(row), "Membership revoked")


@api.get("/tenant/dashboard")
async def tenant_dashboard(
    claims=Depends(require_permission("tenant_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("workspace_kind") != "tenant":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_WORKSPACE_REQUIRED",
                "message": "Tenant dashboard requires the tenant workspace.",
            },
        )
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    user = await db.get(m.User, claims["sub"])
    if not workspace_svc.is_tenant_admin_role(user.role):
        raise HTTPException(status_code=403, detail="Tenant administrator required")
    payload = await companies_svc.tenant_dashboard_payload(db, tenant=tenant, user=user)
    return env(payload)


@api.patch("/me")
async def update_me(
    payload: ProfileUpdate,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(m.User, claims["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.full_name is not None:
        from app.honesty import require_honest_narrative

        user.full_name = require_honest_narrative(
            payload.full_name, label="full name", max_length=150
        )
    if payload.phone is not None:
        # ProfileUpdate.phone ∈ E164PhoneValue — defense-in-depth → 400.
        from app.schemas import validate_e164_phone_value

        try:
            user.phone = validate_e164_phone_value(str(payload.phone).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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


async def _get_tenant_user(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    *,
    actor_role: str | None = None,
) -> m.User:
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if actor_role is not None and not is_platform_role(actor_role) and is_platform_role(user.role):
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
    include_inactive: bool = False,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    """System + custom roles. Default hides inactive custom roles; set include_inactive for manage UI."""
    return env(
        await custom_roles_svc.catalog_for_tenant(
            db, claims["tenant_id"], include_inactive=bool(include_inactive)
        )
    )


@api.get("/roles/{role}")
async def role_detail(
    role: RoleKeyValue,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    if role in VALID_ROLES:
        catalog = {row["role"]: row for row in list_role_catalog()}
        return env(catalog[role])
    custom = await custom_roles_svc.get_custom_role(
        db, claims["tenant_id"], role, active_only=False
    )
    if not custom:
        raise HTTPException(status_code=404, detail="Role not found")
    return env(custom_roles_svc.serialize_custom_role(custom))


@api.post("/roles")
async def create_custom_role(
    payload: CustomRoleCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("role") not in {"company_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only company admins can create custom roles")
    row = await custom_roles_svc.create_custom_role(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        key=payload.key,
        label=payload.label,
        permissions=payload.permissions,
        base_role=payload.base_role,
        record_scope=payload.record_scope,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="custom_role_created",
        entity="custom_role",
        entity_id=row.id,
        details={"key": row.key, "label": row.label},
    )
    await db.commit()
    return env(custom_roles_svc.serialize_custom_role(row), "Custom role created")


@api.patch("/roles/{role}")
async def update_custom_role(
    role: RoleKeyValue,
    payload: CustomRoleUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("role") not in {"company_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only company admins can update custom roles")
    if role in VALID_ROLES:
        raise HTTPException(status_code=400, detail="System roles are immutable")
    row = await custom_roles_svc.update_custom_role(
        db,
        tenant_id=claims["tenant_id"],
        key=role,
        label=payload.label,
        permissions=payload.permissions,
        record_scope=payload.record_scope,
        is_active=payload.is_active,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="custom_role_updated",
        entity="custom_role",
        entity_id=row.id,
        details={"key": row.key},
    )
    await db.commit()
    return env(custom_roles_svc.serialize_custom_role(row), "Custom role updated")


@api.delete("/roles/{role}")
async def delete_custom_role(
    role: RoleKeyValue,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    if claims.get("role") not in {"company_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only company admins can delete custom roles")
    if role in VALID_ROLES:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")
    existing = await custom_roles_svc.get_custom_role(
        db, claims["tenant_id"], role, active_only=False
    )
    entity_id = existing.id if existing else role
    await custom_roles_svc.delete_custom_role(db, tenant_id=claims["tenant_id"], key=role)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="custom_role_deleted",
        entity="custom_role",
        entity_id=entity_id,
        details={"key": role},
    )
    await db.commit()
    return env({"role": role}, "Custom role deleted")


@api.get("/branches")
async def list_branches(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await org_units_svc.list_branches(
        db, claims["tenant_id"], active_only=active_only, is_active=is_active
    )
    return env([org_units_svc.serialize_branch(r) for r in rows])


@api.post("/branches")
async def create_branch(
    payload: BranchCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

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
    branch_id: UuidIdValue,
    payload: BranchUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

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
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    active_only: bool = False,
    is_active: bool | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await org_units_svc.list_departments(
        db,
        claims["tenant_id"],
        branch_id=branch_id,
        active_only=active_only,
        is_active=is_active,
        q=q,
    )
    return env([org_units_svc.serialize_department(r) for r in rows])


@api.post("/departments")
async def create_department(
    payload: DepartmentCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

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
    department_id: UuidIdValue,
    payload: DepartmentUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

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
async def users(
    is_active: bool | None = None,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List tenant users. Optional is_active filters soft-deactivated rows (Users manage UI)."""
    stmt = (
        select(m.User)
        .where(m.User.tenant_id == claims["tenant_id"])
        .order_by(m.User.full_name.asc())
    )
    if is_active is not None:
        stmt = stmt.where(m.User.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt)).scalars().all()
    actor_role = claims.get("role") or ""
    if not is_platform_role(actor_role):
        rows = [u for u in rows if not is_platform_role(u.role)]
    return env([serialize_user(u) for u in rows])


@api.get("/users/import/template")
async def users_import_template(
    claims=Depends(require_permission("users", "read")),
):
    from app import user_import as user_import_svc

    csv_text = user_import_svc.template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=users-import-template.csv"},
    )


@api.post("/users/import")
async def users_import(
    file: UploadFile = File(...),
    dry_run: bool = True,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Validate (default) or commit a user CSV import. Commit is all-or-nothing."""
    from app import user_import as user_import_svc

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")

    rows = user_import_svc.parse_csv_rows(content)
    report = await user_import_svc.validate_import_rows(
        db,
        tenant_id=claims["tenant_id"],
        rows=rows,
        actor_role=claims.get("role"),
    )
    prepared = report.pop("_prepared", [])
    if dry_run:
        return env(report, "Validation complete — no users created")

    if not report["can_commit"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "IMPORT_VALIDATION_FAILED",
                "message": "Fix CSV errors before importing",
                "report": report,
            },
        )

    created = await user_import_svc.commit_import(
        db,
        tenant_id=claims["tenant_id"],
        actor_user_id=claims["sub"],
        prepared=prepared,
    )
    await db.commit()
    report["created"] = [{"id": c["id"], "email": c["user"]["email"], "role": c["user"]["role"]} for c in created]
    report["imported"] = len(created)
    return env(report, f"Imported {len(created)} users")


@api.get("/users/{user_id}")
async def get_user(
    user_id: UuidIdValue,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_tenant_user(
        db, claims["tenant_id"], user_id, actor_role=claims.get("role")
    )
    return env(serialize_user(user))


@api.get("/users/{user_id}/stores")
async def get_user_stores(
    user_id: UuidIdValue,
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List store memberships for a user (empty = all stores / grandfather)."""
    from app import store_access as store_access_svc

    await _get_tenant_user(db, claims["tenant_id"], user_id, actor_role=claims.get("role"))
    rows = await store_access_svc.list_memberships(
        db, tenant_id=claims["tenant_id"], user_id=user_id, active_only=True
    )
    allowed = await store_access_svc.assigned_store_ids(
        db, tenant_id=claims["tenant_id"], user_id=user_id
    )
    return env(
        {
            "memberships": [store_access_svc.serialize_membership(r) for r in rows],
            "store_ids": [r.store_id for r in rows],
            "all_stores": allowed is None,
        }
    )


@api.put("/users/{user_id}/stores")
async def put_user_stores(
    user_id: UuidIdValue,
    payload: UserStoreMembershipsReplace,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Replace store memberships. Empty store_ids clears assignments (all stores)."""
    from app import store_access as store_access_svc
    from app import audit as audit_svc

    await _get_tenant_user(db, claims["tenant_id"], user_id, actor_role=claims.get("role"))
    rows = await store_access_svc.replace_memberships(
        db,
        tenant_id=claims["tenant_id"],
        user_id=user_id,
        store_ids=list(payload.store_ids or []),
        actor_user_id=claims.get("sub"),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="users",
        action="user.stores.replace",
        entity="user",
        entity_id=user_id,
        details={"store_ids": [r.store_id for r in rows]},
    )
    await db.commit()
    allowed = await store_access_svc.assigned_store_ids(
        db, tenant_id=claims["tenant_id"], user_id=user_id
    )
    return env(
        {
            "memberships": [store_access_svc.serialize_membership(r) for r in rows],
            "store_ids": [r.store_id for r in rows],
            "all_stores": allowed is None,
        },
        "Store assignments updated",
    )


@api.post("/users")
async def add_user(
    payload: UserCreate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    role_key, role_perms = await custom_roles_svc.resolve_role_assignment(
        db, claims["tenant_id"], payload.role
    )
    if is_platform_role(role_key):
        raise HTTPException(
            status_code=400,
            detail="Create platform staff via POST /platform/staff (not tenant /users)",
        )
    if role_key == "super_admin":
        raise HTTPException(
            status_code=400,
            detail="Create platform owners via POST /platform/staff",
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
    branch_id, department_id = await org_units_svc.assert_user_org_assignment(
        db,
        claims["tenant_id"],
        branch_id=payload.branch_id,
        department_id=payload.department_id,
    )
    if payload.record_scope is not None:
        try:
            scope = normalize_record_scope(payload.record_scope)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        role_perms = dict(role_perms)
        role_perms[RECORD_SCOPE_KEY] = scope
    user = m.User(
        tenant_id=claims["tenant_id"],
        email=payload.email,
        full_name=require_honest_narrative(
            payload.full_name, label="full name", max_length=150
        ),
        phone=_optional_user_phone(payload.phone),
        password_hash=hash_password(payload.password),
        role=role_key,
        permissions=role_perms,
        branch_id=branch_id,
        department_id=department_id,
        # The signed-in admin chose this password and will hand it to the user.
        email_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="user_created",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "role": user.role, "email_verified": True},
    )
    await db.commit()
    return env(
        {"id": user.id, "user": serialize_user(user)},
        "User created. They can sign in with this workspace.",
    )


@api.post("/users/{user_id}/confirm-email")
async def confirm_user_email(
    user_id: UuidIdValue,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Clear the email gate for a user an admin already provisioned."""
    user = await _get_tenant_user(
        db, claims["tenant_id"], user_id, actor_role=claims.get("role")
    )
    user.email_verified = True
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="email_confirmed",
        entity="user",
        entity_id=user.id,
        details={"email": user.email},
    )
    await db.commit()
    return env(serialize_user(user), "User can sign in. Email verification is not required.")


@api.patch("/users/{user_id}")
async def update_user(
    user_id: UuidIdValue,
    payload: UserUpdate,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_tenant_user(
        db, claims["tenant_id"], user_id, actor_role=claims.get("role")
    )
    changes: dict = {}

    if payload.full_name is not None:
        name = require_honest_narrative(
            payload.full_name, label="full name", max_length=150
        )
        user.full_name = name
        changes["full_name"] = name

    if payload.phone is not None:
        # UserUpdate.phone ∈ E164PhoneValue — defense-in-depth → 400.
        user.phone = _optional_user_phone(payload.phone)
        changes["phone"] = user.phone

    if payload.role is not None:
        role_key, role_perms = await custom_roles_svc.resolve_role_assignment(
            db, claims["tenant_id"], payload.role
        )
        if role_key == "super_admin" and claims.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Only super_admin can assign super_admin")
        if user.id == claims["sub"] and role_key != user.role:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        if user.role != role_key:
            changes["role"] = {"from": user.role, "to": role_key}
            prev_scope = None
            if isinstance(user.permissions, dict):
                prev_scope = user.permissions.get(RECORD_SCOPE_KEY)
            user.role = role_key
            perms = dict(role_perms)
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

    if (
        payload.clear_branch
        or payload.clear_department
        or payload.branch_id is not None
        or payload.department_id is not None
    ):
        desired_branch = None if payload.clear_branch else (
            payload.branch_id if payload.branch_id is not None else user.branch_id
        )
        desired_dept = None if payload.clear_department else (
            payload.department_id if payload.department_id is not None else user.department_id
        )
        branch_id, department_id = await org_units_svc.assert_user_org_assignment(
            db,
            claims["tenant_id"],
            branch_id=desired_branch,
            department_id=desired_dept,
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
    user_id: UuidIdValue,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete: deactivate the user and revoke sessions (no hard delete)."""
    user = await _get_tenant_user(
        db, claims["tenant_id"], user_id, actor_role=claims.get("role")
    )
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


@api.delete("/users/{user_id}/account")
async def delete_user_account(
    user_id: UuidIdValue,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a tenant staff account (company admin / users write)."""
    snapshot = await user_accounts_svc.delete_tenant_user(
        db,
        tenant_id=claims["tenant_id"],
        actor_id=claims["sub"],
        user_id=user_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="user_deleted",
        entity="user",
        entity_id=snapshot["id"],
        details={"email": snapshot["email"], "role": snapshot["role"], "full_name": snapshot["full_name"]},
    )
    await db.commit()
    return env(snapshot, "User account deleted")


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
    if "role" in changes or "record_scope" in changes:
        await cache_svc.app_cache.invalidate_user_permissions(claims["tenant_id"], user.id)
    return env(serialize_user(user), "User updated")


@api.post("/users/{user_id}/password-reset-email")
async def admin_password_reset_email(
    user_id: str,
    request: Request,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 85 E1 — Tenant Admin initiates email password reset (not prompt/PATCH password)."""
    user = await _get_tenant_user(db, claims["tenant_id"], user_id)
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Cannot email reset for inactive user")
    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=claims["tenant_id"],
            user_id=user.id,
            purpose="password_reset",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="users",
        action="admin_password_reset_email",
        entity="user",
        entity_id=user.id,
        details={"email": user.email, "initiated_by": claims["sub"]},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    from app import emailer

    email_result = await emailer.send_password_reset_email(to=user.email, token=raw)
    data: dict = {
        "user_id": user.id,
        "email": user.email,
        "email_delivery": {
            "sent": email_result.sent,
            "mode": email_result.mode,
            "error": email_result.error,
        },
    }
    if settings.DEBUG or settings.APP_ENV.lower() != "production":
        data["reset_token"] = raw
    return env(data, "Password reset email issued")


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
async def dashboard(
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import build_dashboard

    return env(await build_dashboard(db, claims["tenant_id"], store_id=store_id))

    # Tenant user management KPIs (Tenant Admin / users:read only after filter)
    user_total = await scalar(select(func.count(m.User.id)).where(m.User.tenant_id == tid))
    user_active = await scalar(
        select(func.count(m.User.id)).where(m.User.tenant_id == tid, m.User.is_active == True)  # noqa: E712
    )
    role_count = await scalar(
        select(func.count(m.CustomRole.id)).where(m.CustomRole.tenant_id == tid)
    )
    # System roles + custom roles for catalog size
    from app.rbac import list_system_role_catalog

    system_role_count = len(list_system_role_catalog())
    recent_logins = await scalar(
        select(func.count(func.distinct(m.AuthSession.user_id))).where(
            m.AuthSession.tenant_id == tid,
            m.AuthSession.revoked_at.is_(None),
            m.AuthSession.created_at >= day_start - timedelta(days=7),
        )
    )

    expenses_by_category = await dashboard_slices_svc.expenses_by_category(
        db, tid, company_id=cid
    )
    ar_aging = await credit_svc.ar_aging(db, tid, company_id=cid)
    ar_total_due = float(ar_aging.get("total_due") or 0)
    # Stage 96 B1 — AP Payables + MTD Profit Summary (real aggregates; no fabricated KPIs)
    ap_aging = await credit_svc.ap_aging(db, tid, company_id=cid)
    ap_total_due = float(ap_aging.get("total_due") or 0)
    from app import accounting as accounting_svc

    pnl_mtd = await accounting_svc.profit_and_loss(
        db, tid, from_date=month_start, to_date=now, company_id=cid
    )
    profit_summary = float(pnl_mtd.get("net_profit") or 0)
    income_mtd = float(pnl_mtd.get("income") or 0)

    payload = {
        "total_sales": float(sales) + float(
            await scalar(
                select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                    *_co(m.SalesInvoice),
                    m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
                )
            )
        ),
        "total_purchases": float(purchases),
        "total_expenses": float(expenses),
        "pending_expenses": int(pending_expenses or 0),
        "expenses_by_category": expenses_by_category,
        "credit_outstanding": ar_total_due,
        "ar_total_due": ar_total_due,
        "ap_total_due": ap_total_due,
        "ap_outstanding": ap_total_due,
        "profit_summary": profit_summary,
        "income_mtd": income_mtd,
        "products": products,
        "low_stock": low,
        "out_of_stock": out_of_stock,
        "expiring_batches": expiring_batches,
        "customers": customers,
        "suppliers": suppliers,
        "daily_revenue": daily_revenue,
        "yesterday_revenue": yesterday_revenue,
        "dod_change_pct": dod_change_pct,
        "monthly_revenue": monthly_revenue,
        "prior_month_revenue": prior_month_revenue,
        "mom_change_pct": mom_change_pct,
        "recent_sales": recent,
        "top_products": top_products,
        "daily_revenue_series": chart_series["daily_revenue_series"],
        "monthly_revenue_series": chart_series["monthly_revenue_series"],
        "user_stats": {
            "total_users": int(user_total),
            "active_users": int(user_active),
            "inactive_users": int(user_total) - int(user_active),
            "custom_roles": int(role_count),
            "system_roles": int(system_role_count),
            "recent_logins_7d": int(recent_logins),
        },
        "role_label": ROLE_LABELS.get(role, role),
        "store_scope": dashboard_scope_svc.store_scope_payload(managed_ids),
        # BR-4.1 click-through targets (Stage 1 F17 / Stage 21 V1 / Stage 96 B1)
        "kpi_links": {
            "total_sales": "/sales?tab=invoices",
            "total_purchases": "/purchasing?tab=invoices",
            "total_expenses": "/expenses",
            "pending_expenses": "/expenses?status=pending",
            "credit_outstanding": "/credit?kind=receivable",
            "ar_total_due": "/credit?kind=receivable",
            "ap_total_due": "/credit?kind=payable",
            "ap_outstanding": "/credit?kind=payable",
            "profit_summary": "/accounting?tab=ledger#profit-loss",
            "income_mtd": "/accounting?tab=ledger#profit-loss",
            "customers": "/sales?tab=customers",
            "suppliers": "/purchasing?tab=suppliers",
            "products": "/inventory?tab=products",
            "low_stock": "/inventory?tab=lowstock",
            "out_of_stock": "/inventory?tab=lowstock",
            "expiring_batches": "/inventory?tab=expiry",
            "daily_revenue": "/reports?tab=sales",
            "yesterday_revenue": "/reports?tab=sales",
            "dod_change_pct": "/reports?tab=sales",
            "monthly_revenue": "/reports?tab=sales",
            "prior_month_revenue": "/reports?tab=sales",
            "mom_change_pct": "/reports?tab=sales",
            "user_stats": "/users",
            # Stage 104 R1 — Custom Roles KPI → Roles admin (not Users list)
            "custom_roles": "/admin/roles#custom",
        },
    }
    # Stage 81 S1 — Store Manager aggregates limited to stores.manager_id
    if managed_ids is not None:
        scoped = await dashboard_scope_svc.scoped_financial_kpis(
            db,
            tenant_id=tid,
            store_ids=managed_ids,
            day_start=day_start,
            yesterday_start=yesterday_start,
            month_start=month_start,
            prior_month_start=prior_month_start,
        )
        payload.update(scoped)
    # Stage 80 T1 — permission + role scoped view (cashier omits accounting/users/etc.)
    _ = has_permission  # imported for clarity; filtering uses dashboard_views
    payload = dashboard_views_svc.filter_dashboard_payload(payload, claims)
    await cache_svc.app_cache.set_json(
        dash_key, payload, ttl_seconds=int(settings.CACHE_DASHBOARD_TTL_SECONDS)
    )
    return env(payload)


@api.get("/dashboard/export")
async def dashboard_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 153 B1 — tenant dashboard aggregates CSV (real KPIs; no fabricated MRR)."""
    wrapped = await dashboard(claims=claims, db=db)
    payload = wrapped.get("data") if isinstance(wrapped, dict) else wrapped
    if not isinstance(payload, dict):
        payload = {}
    text = tenant_ops_export_svc.export_tenant_dashboard_csv(dashboard=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="tenant_dashboard_export.csv"'
        },
    )


@api.get("/dashboard/summary")
async def dashboard_summary(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import dashboard_slices as slices_svc

    return env(
        await slices_svc.summary_slice(db, claims, company_id=claims.get("company_id"))
    )


@api.get("/dashboard/sales-trend")
async def dashboard_sales_trend(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import dashboard_slices as slices_svc

    return env(
        await slices_svc.sales_trend(db, claims, company_id=claims.get("company_id"))
    )


@api.get("/dashboard/sales-trend/export")
async def dashboard_sales_trend_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 157 S1 — dashboard sales-trend series CSV (distinct from Stage 153 aggregates)."""
    from app import dashboard_slices as slices_svc

    payload = await slices_svc.sales_trend(
        db, claims, company_id=claims.get("company_id")
    )
    text = tenant_ops_export_svc.export_dashboard_sales_trend_csv(payload=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_sales_trend_export.csv"'
        },
    )


@api.get("/dashboard/top-products")
async def dashboard_top_products(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import dashboard_slices as slices_svc

    return env(
        await slices_svc.top_products(db, claims, company_id=claims.get("company_id"))
    )


@api.get("/dashboard/top-products/export")
async def dashboard_top_products_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 157 T1 — dashboard top-products ranking CSV (distinct from Stage 153 aggregates)."""
    from app import dashboard_slices as slices_svc

    payload = await slices_svc.top_products(
        db, claims, company_id=claims.get("company_id")
    )
    text = tenant_ops_export_svc.export_dashboard_top_products_csv(payload=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_top_products_export.csv"'
        },
    )

@api.get("/dashboard/expenses")
async def dashboard_expenses(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import dashboard_slices as slices_svc

    return env(
        await slices_svc.expenses_slice(db, claims, company_id=claims.get("company_id"))
    )


@api.get("/dashboard/expenses/export")
async def dashboard_expenses_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 158 E1 — dashboard expenses-by-category CSV (distinct from Stage 153 aggregates)."""
    from app import dashboard_slices as slices_svc

    payload = await slices_svc.expenses_slice(
        db, claims, company_id=claims.get("company_id")
    )
    text = tenant_ops_export_svc.export_dashboard_expenses_csv(payload=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_expenses_export.csv"'
        },
    )


@api.get("/dashboard/credit")
async def dashboard_credit(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import dashboard_slices as slices_svc

    return env(await slices_svc.credit_slice(db, claims))


@api.get("/dashboard/credit/export")
async def dashboard_credit_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 158 C1 — dashboard AR outstanding CSV (distinct from Stage 153 aggregates)."""
    from app import dashboard_slices as slices_svc

    payload = await slices_svc.credit_slice(db, claims)
    text = tenant_ops_export_svc.export_dashboard_credit_csv(payload=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_credit_export.csv"'
        },
    )


@api.get("/dashboard/stock-alerts")
async def dashboard_stock_alerts(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import dashboard_slices as slices_svc

    return env(
        await slices_svc.stock_alerts(db, claims, company_id=claims.get("company_id"))
    )


@api.get("/dashboard/stock-alerts/export")
async def dashboard_stock_alerts_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 158 A1 — dashboard stock-alerts KPI CSV (distinct from Stage 153 aggregates)."""
    from app import dashboard_slices as slices_svc

    payload = await slices_svc.stock_alerts(
        db, claims, company_id=claims.get("company_id")
    )
    text = tenant_ops_export_svc.export_dashboard_stock_alerts_csv(payload=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_stock_alerts_export.csv"'
        },
    )


@api.get("/dashboard/user-stats")
async def dashboard_user_stats(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import dashboard_slices as slices_svc

    return env(await slices_svc.user_stats_slice(db, claims))


@api.get("/dashboard/user-stats/export")
async def dashboard_user_stats_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 159 U1 — dashboard user-stats KPI CSV (distinct from Stage 153/158 slices)."""
    from app import dashboard_slices as slices_svc

    payload = await slices_svc.user_stats_slice(db, claims)
    text = tenant_ops_export_svc.export_dashboard_user_stats_csv(payload=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_user_stats_export.csv"'
        },
    )


@api.get("/dashboard/summary/export")
async def dashboard_summary_export(
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 159 M1 — dashboard compact summary KPI CSV (distinct from Stage 153 aggregates)."""
    from app import dashboard_slices as slices_svc

    payload = await slices_svc.summary_slice(
        db, claims, company_id=claims.get("company_id")
    )
    text = tenant_ops_export_svc.export_dashboard_summary_csv(payload=payload)
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_summary_export.csv"'
        },
    )


@api.get("/search")
async def global_search(
    q: str = "",
    claims=Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 96 G1 — RBAC-gated topbar search (products + customers). No fabricated hits."""
    from app.rbac import has_permission

    query = (q or "").strip()
    role = claims.get("role") or ""
    overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    results: list[dict] = []
    if not query:
        return env({"q": query, "results": results, "total": 0})

    if has_permission(role, "inventory", "read", overrides=overrides):
        products = await product_lookup_svc.lookup_products(
            db,
            tenant_id=claims["tenant_id"],
            q=query,
            limit=12,
            company_id=claims.get("company_id"),
        )
        for p in products[:8]:
            results.append(
                {
                    "kind": "product",
                    "id": p.get("id") or p.get("product_id"),
                    "label": p.get("name") or p.get("sku") or "Product",
                    "meta": p.get("sku") or p.get("barcode") or "",
                    "href": "/inventory?tab=products",
                }
            )

    if has_permission(role, "sales", "read", overrides=overrides) or has_permission(
        role, "customers", "read", overrides=overrides
    ):
        like = f"%{query}%"
        stmt = (
            select(m.Party)
            .where(
                *workspace_svc.company_scope_filter(m.Party, claims),
                m.Party.kind == "customer",
                (m.Party.name.ilike(like))
                | (m.Party.email.ilike(like))
                | (m.Party.phone.ilike(like)),
            )
            .order_by(m.Party.name.asc())
            .limit(8)
        )
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            results.append(
                {
                    "kind": "customer",
                    "id": row.id,
                    "label": row.name,
                    "meta": row.email or row.phone or "",
                    "href": "/sales?tab=customers",
                }
            )

    return env({"q": query, "results": results, "total": len(results)})


@api.get("/products")
async def products(
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List products. Optional is_active filters soft-deactivated rows (Inventory manage UI)."""
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    extra = ""
    params: dict = {}
    if is_active is not None:
        extra = "is_active = :ia"
        params["ia"] = bool(is_active)
    from app import schema_compat

    rows = await schema_compat.list_mapped(
        db, m.Product, tenant_id=claims["tenant_id"], extra=extra, extra_params=params, order_by="name"
    )
    return env([catalog_meta_svc.serialize_product(p) for p in rows])


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
        company_id=claims.get("company_id"),
    )
    data["category"] = category_label
    data["category_id"] = category_id
    data["brand_id"] = brand_id
    data["unit_id"] = unit_id
    if data.get("barcode") is not None:
        data["barcode"] = barcodes_svc.normalize_barcode(data.get("barcode"))
        if data["barcode"]:
            await barcodes_svc.assert_barcode_unique(
                db,
                tenant_id=claims["tenant_id"],
                barcode_value=data["barcode"],
            )
    from app.tax import normalize_supply_class, sync_product_tax_flags

    supply = normalize_supply_class(
        data.get("tax_supply_class"),
        tax_exempt=bool(data.get("tax_exempt")),
        strict=True,
    )
    data["tax_supply_class"] = supply
    data["tax_exempt"] = supply == "exempt"
    from app.honesty import optional_honest_narrative, require_honest_narrative

    data["name"] = require_honest_narrative(
        data.get("name"), label="product name", max_length=200
    )
    if data.get("description") is not None:
        data["description"] = optional_honest_narrative(
            data["description"], label="product description"
        )
    for dim in ("weight", "length", "width", "height"):
        if data.get(dim) is not None:
            data[dim] = money_json(data[dim])
    sku_norm = catalog_svc.normalize_sku(data.get("sku"))
    if not sku_norm:
        sku_norm = await catalog_svc.allocate_sku(db, claims["tenant_id"], prefix="SKU")
    else:
        await catalog_svc.assert_sku_available(db, claims["tenant_id"], sku_norm)
    data["sku"] = sku_norm
    from app import schema_compat
    from app.models import uid

    product = await schema_compat.insert_and_get(
        db,
        m.Product,
        {
            **data,
            "id": uid(),
            "tenant_id": claims["tenant_id"],
            "reserved_qty": 0,
            "minimum_stock": data.get("reorder_level") or 0,
        },
    )
    if product is None:
        raise HTTPException(status_code=500, detail="The server could not complete this request.")
    await db.flush()
    if money_json(product.stock_qty or 0) > 0:
        opening = money_json(product.stock_qty)
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
            company_id=claims.get("company_id"),
        )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="product_create",
        entity="product",
        entity_id=product.id,
        details={
            "sku": product.sku,
            "after": catalog_meta_svc.product_audit_snapshot(product),
        },
    )
    await db.commit()
    fresh = await schema_compat.get_mapped(db, m.Product, product.id)
    return env(catalog_meta_svc.serialize_product(fresh or product), "Product created")


@api.get("/products/import/template")
async def products_import_template(
    claims=Depends(require_permission("inventory", "read")),
):
    from app import product_import as product_import_svc

    csv_text = product_import_svc.template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=products-import-template.csv"},
    )


@api.get("/products/export")
async def products_export(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-18.2 — catalog CSV export using the same columns as the import template."""
    from app import product_import as product_import_svc

    csv_text = await product_import_svc.export_tenant_products_csv(db, claims["tenant_id"])
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=products-export.csv"},
    )


@api.post("/products/import")
async def products_import(
    file: UploadFile = File(...),
    dry_run: bool = True,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Validate (default) or commit a product CSV import. Commit is all-or-nothing."""
    from app import product_import as product_import_svc

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")

    rows = product_import_svc.parse_csv_rows(content)
    report = await product_import_svc.validate_import_rows(
        db, tenant_id=claims["tenant_id"], rows=rows
    )
    prepared = report.pop("_prepared", [])
    if dry_run:
        return env(report, "Validation complete — no products created")

    if not report["can_commit"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "IMPORT_VALIDATION_FAILED",
                "message": "Fix CSV errors before importing",
                "report": report,
            },
        )

    created = await product_import_svc.commit_import(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        prepared=prepared,
    )
    await db.commit()
    report["created"] = created
    report["imported"] = len(created)
    return env(report, f"Imported {len(created)} products")


@api.get("/products/{product_id}")
async def get_product(
    product_id: UuidIdValue,
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
    product_id: UuidIdValue,
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

    tracked = (
        "name",
        "sku",
        "barcode",
        "cost_price",
        "selling_price",
        "reorder_level",
        "description",
        "category",
        "category_id",
        "brand_id",
        "unit_id",
        "tax_rate_id",
        "tax_supply_class",
        "tax_exempt",
        "tracks_batches",
        "is_active",
        "weight",
        "length",
        "width",
        "height",
    )
    before = {key: getattr(product, key, None) for key in tracked}

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
            from app.honesty import require_honest_narrative

            product.name = require_honest_narrative(
                value, label="product name", max_length=200
            )
        elif key == "barcode":
            code = barcodes_svc.normalize_barcode(str(value) if value is not None else None)
            if code:
                await barcodes_svc.assert_barcode_unique(
                    db,
                    tenant_id=claims["tenant_id"],
                    barcode_value=code,
                    exclude_product_id=product.id,
                )
            product.barcode = code
        elif key in {"cost_price", "selling_price", "reorder_level"} and value is not None:
            setattr(product, key, money_json(value))
        elif key == "description":
            from app.honesty import optional_honest_narrative

            if value is None:
                product.description = None
            else:
                product.description = optional_honest_narrative(
                    value, label="product description"
                )
        elif key in {"weight", "length", "width", "height"}:
            setattr(product, key, money_json(value) if value is not None else None)
        elif key == "tax_rate_id":
            product.tax_rate_id = value
        elif key == "tax_supply_class" and value is not None:
            from app.tax import sync_product_tax_flags

            sync_product_tax_flags(product, supply_class=str(value))
        elif key == "tax_exempt" and value is not None:
            from app.tax import sync_product_tax_flags

            sync_product_tax_flags(product, tax_exempt=bool(value))
        elif key == "tracks_batches" and value is not None:
            product.tracks_batches = bool(value)
        elif key == "is_active" and value is not None:
            product.is_active = bool(value)

    after = {key: getattr(product, key, None) for key in tracked}

    def _jsonable(value):
        from decimal import Decimal

        if isinstance(value, Decimal):
            return money_json(value)
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        if isinstance(value, float):
            return money_json(round(value, 4))
        return value

    changes = {
        key: {"before": _jsonable(before[key]), "after": _jsonable(after[key])}
        for key in tracked
        if before.get(key) != after.get(key)
    }

    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="product_update",
        entity="product",
        entity_id=product.id,
        details={
            "sku": product.sku,
            "fields": sorted(payload.model_dump(exclude_unset=True).keys()),
            "changes": changes,
        },
    )
    await db.commit()
    await db.refresh(product)
    return env(catalog_meta_svc.serialize_product(product), "Product updated")


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
                *workspace_svc.company_scope_filter(m.Product, claims),
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    workspace_svc.assert_record_company(claims, product)
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
                *workspace_svc.company_scope_filter(m.Product, claims),
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    workspace_svc.assert_record_company(claims, product)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return env(catalog_meta_svc.serialize_product(product), "No changes")

    before_snap = catalog_meta_svc.product_audit_snapshot(product)
    was_active = bool(product.is_active)

    if any(k in data for k in ("category_id", "brand_id", "unit_id", "category")):
        category_id, brand_id, unit_id, category_label = await catalog_meta_svc.resolve_product_refs(
            db,
            claims["tenant_id"],
            category_id=data.get("category_id", product.category_id),
            brand_id=data.get("brand_id", product.brand_id),
            unit_id=data.get("unit_id", product.unit_id),
            category_name=data.get("category", product.category),
            company_id=claims.get("company_id"),
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
        clash_stmt = select(m.Product).where(
            m.Product.tenant_id == claims["tenant_id"],
            m.Product.sku == sku,
            m.Product.id != product.id,
        )
        if claims.get("company_id"):
            clash_stmt = clash_stmt.where(m.Product.company_id == claims["company_id"])
        clash = (await db.execute(clash_stmt)).scalar_one_or_none()
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
                company_id=claims.get("company_id") or getattr(product, "company_id", None),
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
            if value is not None:
                from app import tax as tax_svc

                await tax_svc.get_tax_rate(
                    db,
                    claims["tenant_id"],
                    value,
                    company_id=claims.get("company_id")
                    or getattr(product, "company_id", None),
                )
            product.tax_rate_id = value
        elif key == "tax_exempt" and value is not None:
            product.tax_exempt = bool(value)
        elif key == "tracks_batches" and value is not None:
            product.tracks_batches = bool(value)
        elif key == "is_active" and value is not None:
            product.is_active = bool(value)

    after_snap = catalog_meta_svc.product_audit_snapshot(product)
    before_diff, after_diff = catalog_meta_svc.product_audit_diff(before_snap, after_snap)
    deactivated = was_active and not bool(product.is_active)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="product_deactivate" if deactivated else "product_update",
        entity="product",
        entity_id=product.id,
        details={
            "sku": product.sku,
            "fields": sorted(payload.model_dump(exclude_unset=True).keys()),
            "before": before_diff,
            "after": after_diff,
        },
    )
    await db.commit()
    await db.refresh(product)
    await cache_svc.app_cache.invalidate_tenant(claims["tenant_id"])
    return env(catalog_meta_svc.serialize_product(product), "Product updated")


@api.get("/catalog/categories")
async def catalog_categories(
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List product categories. Optional is_active filters soft-deactivated rows (Catalog manage UI)."""
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    rows = await catalog_meta_svc.list_categories(
        db, claims["tenant_id"], is_active=is_active
    )
    return env(catalog_meta_svc.serialize_categories_tree(rows))


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
        tax_rate_id=payload.tax_rate_id,
    )
    await db.commit()
    rows = await catalog_meta_svc.list_categories(db, claims["tenant_id"])
    tree = catalog_meta_svc.serialize_categories_tree(rows)
    hit = next((c for c in tree if c["id"] == row.id), catalog_meta_svc.serialize_category(row))
    return env(hit, "Category created")


@api.patch("/catalog/categories/{category_id}")
async def catalog_patch_category(
    category_id: UuidIdValue,
    payload: ProductCategoryUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    clear_parent = "parent_id" in data and data["parent_id"] is None
    clear_tax_rate = "tax_rate_id" in data and data["tax_rate_id"] is None
    row = await catalog_meta_svc.update_category(
        db,
        tenant_id=claims["tenant_id"],
        category_id=category_id,
        code=data.get("code"),
        name=data.get("name"),
        parent_id=data.get("parent_id"),
        tax_rate_id=data.get("tax_rate_id"),
        is_active=data.get("is_active"),
        clear_parent=clear_parent,
        clear_tax_rate=clear_tax_rate,
    )
    await db.commit()
    # Return enriched tree fields for the updated row
    rows = await catalog_meta_svc.list_categories(db, claims["tenant_id"])
    tree = catalog_meta_svc.serialize_categories_tree(rows)
    hit = next((c for c in tree if c["id"] == row.id), catalog_meta_svc.serialize_category(row))
    return env(hit, "Category updated")


@api.delete("/catalog/categories/{category_id}")
async def catalog_delete_category(
    category_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.deactivate_category(
        db, tenant_id=claims["tenant_id"], category_id=category_id
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_category(row), "Category deactivated")


@api.patch("/catalog/categories/{category_id}")
async def catalog_patch_category(
    category_id: str,
    payload: ProductCategoryUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    clear_parent = "parent_id" in data and data["parent_id"] is None
    clear_tax_rate = "tax_rate_id" in data and data["tax_rate_id"] is None
    row = await catalog_meta_svc.update_category(
        db,
        tenant_id=claims["tenant_id"],
        category_id=category_id,
        code=data.get("code"),
        name=data.get("name"),
        parent_id=data.get("parent_id"),
        is_active=data.get("is_active"),
        tax_rate_id=data.get("tax_rate_id"),
        clear_parent=clear_parent,
        clear_tax_rate=clear_tax_rate,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    await cache_svc.app_cache.invalidate_catalog(
        claims["tenant_id"], company_id=claims.get("company_id")
    )
    return env(catalog_meta_svc.serialize_category(row), "Category updated")


@api.delete("/catalog/categories/{category_id}")
async def catalog_delete_category(
    category_id: str,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.deactivate_category(
        db,
        tenant_id=claims["tenant_id"],
        category_id=category_id,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    await cache_svc.app_cache.invalidate_catalog(
        claims["tenant_id"], company_id=claims.get("company_id")
    )
    return env(catalog_meta_svc.serialize_category(row), "Category deactivated")


@api.get("/catalog/brands")
async def catalog_brands(
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List brands. Optional is_active filters soft-deactivated rows (Catalog manage UI)."""
    rows = await catalog_meta_svc.list_brands(
        db, claims["tenant_id"], is_active=is_active
    )
    return env([catalog_meta_svc.serialize_brand(r) for r in rows])


@api.get("/catalog/brands/export")
async def catalog_brands_export(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 122 X1 — brands CSV export."""
    text = await org_catalog_export_svc.export_brands_csv(
        db,
        tenant_id=claims["tenant_id"],
        is_active=is_active,
        active_only=active_only,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="brands_export.csv"'},
    )


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
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_brand(row), "Brand created")


@api.patch("/catalog/brands/{brand_id}")
async def catalog_patch_brand(
    brand_id: UuidIdValue,
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
    brand_id: UuidIdValue,
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
    brand_id: UuidIdValue,
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
    await db.refresh(brand)
    return env(
        {
            **catalog_meta_svc.serialize_brand(brand),
            "uploaded": {
                "key": stored.key,
                "size": stored.size,
                "content_type": stored.content_type,
                "filename": stored.original_filename,
            },
        },
        "Brand logo uploaded",
    )


@api.get("/catalog/brands/{brand_id}/logo")
async def catalog_brand_logo_get(
    brand_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    brand = await catalog_meta_svc.get_brand(db, claims["tenant_id"], brand_id)
    if not brand.logo_url:
        raise HTTPException(status_code=404, detail="Brand logo not found")
    return storage_svc.media_response(brand.logo_url, tenant_id=claims["tenant_id"])


@api.delete("/catalog/brands/{brand_id}/logo")
async def catalog_brand_logo_delete(
    brand_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    brand = await catalog_meta_svc.get_brand(db, claims["tenant_id"], brand_id)
    if not brand.logo_url:
        raise HTTPException(status_code=404, detail="Brand logo not found")
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
    await db.refresh(brand)
    return env(catalog_meta_svc.serialize_brand(brand), "Brand logo removed")


@api.get("/catalog/units")
async def catalog_units(
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List units of measure. Optional is_active filters soft-deactivated rows (Catalog manage UI)."""
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    await db.commit()
    rows = await catalog_meta_svc.list_units(
        db, claims["tenant_id"], is_active=is_active
    )
    return env(await catalog_meta_svc.serialize_units(db, claims["tenant_id"], rows))


@api.get("/catalog/units/export")
async def catalog_units_export(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 122 X1 — units CSV export."""
    text = await org_catalog_export_svc.export_units_csv(
        db,
        tenant_id=claims["tenant_id"],
        is_active=is_active,
        active_only=active_only,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="units_export.csv"'},
    )


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
        company_id=claims.get("company_id"),
    )
    return env(result)


@api.post("/catalog/units")
async def catalog_create_unit(
    payload: UnitOfMeasureCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    await catalog_meta_svc.ensure_default_catalog(db, claims["tenant_id"])
    row = await catalog_meta_svc.create_unit(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        base_unit_id=payload.base_unit_id,
        conversion_ratio=payload.conversion_ratio,
    )
    await db.commit()
    from app import schema_compat

    row = await schema_compat.get_mapped(db, m.UnitOfMeasure, row.id) or row
    base = None
    if row.base_unit_id:
        base = await schema_compat.get_mapped(db, m.UnitOfMeasure, row.base_unit_id)
    return env(catalog_meta_svc.serialize_unit(row, base=base), "Unit created")


@api.post("/catalog/units/convert")
async def catalog_convert_unit(
    payload: UnitConvertPreview,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.catalog import get_product
    from app.uom import to_stock_qty

    product = await get_product(db, claims["tenant_id"], payload.product_id)
    quantity_base, entered_unit_id, entered_qty = await to_stock_qty(
        db,
        tenant_id=claims["tenant_id"],
        quantity=payload.quantity,
        from_unit_id=payload.from_unit_id,
        product=product,
    )
    return env(
        {
            "product_id": product.id,
            "stock_unit_id": product.unit_id,
            "from_unit_id": entered_unit_id,
            "quantity_entered": entered_qty,
            "quantity_base": quantity_base,
        }
    )


@api.patch("/catalog/units/{unit_id}")
async def catalog_patch_unit(
    unit_id: UuidIdValue,
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
        base_unit_id=data.get("base_unit_id"),
        conversion_ratio=data.get("conversion_ratio"),
        clear_base=bool(data.get("clear_base")),
    )
    await db.commit()
    from app import schema_compat

    row = await schema_compat.get_mapped(db, m.UnitOfMeasure, row.id) or row
    base = None
    if row.base_unit_id:
        base = await schema_compat.get_mapped(db, m.UnitOfMeasure, row.base_unit_id)
    return env(catalog_meta_svc.serialize_unit(row, base=base), "Unit updated")

@api.delete("/catalog/units/{unit_id}")
async def catalog_delete_unit(
    unit_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await catalog_meta_svc.deactivate_unit(
        db, tenant_id=claims["tenant_id"], unit_id=unit_id
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_unit(row), "Unit deactivated")


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
        company_id=claims.get("company_id"),
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
        db,
        tenant_id=claims["tenant_id"],
        unit_id=unit_id,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(catalog_meta_svc.serialize_unit(row), "Unit deactivated")


@api.post("/products/{product_id}/image")
async def product_image_upload(
    product_id: UuidIdValue,
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
    product_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id,
                *workspace_svc.company_scope_filter(m.Product, claims),
            )
        )
    ).scalar_one_or_none()
    if not product or not product.image_url:
        raise HTTPException(status_code=404, detail="Product image not found")
    workspace_svc.assert_record_company(claims, product)
    return storage_svc.media_response(product.image_url, tenant_id=claims["tenant_id"])


@api.delete("/products/{product_id}/image")
async def product_image_delete(
    product_id: UuidIdValue,
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
    product_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await product_images_svc.list_product_images(
        db, tenant_id=claims["tenant_id"], product_id=product_id
    )
    return env([product_images_svc.serialize_image(r) for r in rows])


@api.post("/products/{product_id}/images")
async def product_images_upload(
    product_id: UuidIdValue,
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
    product_id: UuidIdValue,
    image_id: UuidIdValue,
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
    product_id: UuidIdValue,
    image_id: UuidIdValue,
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


@api.post("/products/{product_id}/barcode/generate")
async def product_barcode_generate(
    product_id: UuidIdValue,
    force: bool = False,
    # omit → code128; blank/invalid → 422 (was free str; "" coerced to code128)
    symbology: Annotated[BarcodeSymbologyValue, Query()] = "code128",
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Assign a barcode (Code128 from SKU, or EAN-13 / UPC-A GTIN)."""
    sym = barcodes_svc.normalize_symbology(symbology)
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
    if product.barcode and not force:
        return env(catalog_meta_svc.serialize_product(product), "Barcode already set")

    candidate = await barcodes_svc.allocate_unique_barcode(
        db,
        tenant_id=claims["tenant_id"],
        sku=product.sku,
        symbology=sym,
        seed=f"{product.id}:{product.sku}",
        exclude_product_id=product.id,
    )

    product.barcode = candidate
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="barcode_generate",
        entity="product",
        entity_id=product.id,
        details={"barcode": product.barcode, "sku": product.sku, "symbology": sym},
    )
    await db.commit()
    await db.refresh(product)
    out = catalog_meta_svc.serialize_product(product)
    out["symbology"] = sym
    return env(out, "Barcode generated")


@api.get("/products/{product_id}/barcode.png")
async def product_barcode_png(
    product_id: UuidIdValue,
    symbology: Annotated[BarcodeSymbologyValue | None, Query()] = None,
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
    code = product.barcode or product.sku
    if not code:
        raise HTTPException(status_code=404, detail="No barcode or SKU available")
    sym = (
        barcodes_svc.normalize_symbology(symbology)
        if symbology
        else barcodes_svc.detect_symbology(str(code))
    )
    png = barcodes_svc.render_barcode_png(str(code), symbology=sym)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="barcode-{product.sku}.png"'},
    )


@api.get("/products/{product_id}/barcode/label")
async def product_barcode_label(
    product_id: UuidIdValue,
    # omit → 1; 0/negative/>40 → **422** (was free int; service silently clamped 1–40)
    copies: Annotated[int, Query(ge=1, le=40)] = 1,
    symbology: Annotated[BarcodeSymbologyValue | None, Query()] = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Printable HTML label sheet (Code128 / EAN-13 / UPC-A) for shelf / price tags."""
    import base64

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
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    code = product.barcode or product.sku
    if not code:
        raise HTTPException(status_code=404, detail="No barcode or SKU available")
    sym = (
        barcodes_svc.normalize_symbology(symbology)
        if symbology
        else barcodes_svc.detect_symbology(str(code))
    )
    png = barcodes_svc.render_barcode_png(str(code), symbology=sym)
    data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    page = barcodes_svc.label_html(
        company_name=(tenant.company_name if tenant else "RIBDIGI ERP"),
        product_name=product.name,
        sku=product.sku,
        barcode_value=str(code),
        price=money_json(product.selling_price or 0),
        currency=(tenant.currency if tenant else "GHS"),
        png_data_uri=data_uri,
        copies=copies,
        symbology=sym,
    )
    return Response(content=page, media_type="text/html; charset=utf-8")


@api.get("/products/{product_id}/images")
async def product_images_list(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await product_images_svc.list_product_images(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        company_id=claims.get("company_id"),
    )
    return env([product_images_svc.serialize_image(r) for r in rows])


@api.get("/products/{product_id}/images/export")
async def product_images_export(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 156 G1 — per-product image metadata CSV (no binary payloads)."""
    text = await product_images_svc.export_product_images_csv(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="product_{product_id}_images_export.csv"'
            )
        },
    )


@api.post("/products/{product_id}/images")
async def product_images_upload(
    product_id: str,
    file: UploadFile = File(...),
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    workspace_svc.assert_record_company(claims, product)
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
        company_id=claims.get("company_id"),
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
        company_id=claims.get("company_id"),
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
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(None, "Product image removed")


@api.get("/inventory/low-stock")
async def lowstock(
    stock_status: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 137 L1 — optional stock_status=red|yellow filter."""
    out = await inventory_ops_export_svc.list_low_stock_alerts(
        db,
        tenant_id=claims["tenant_id"],
        stock_status=stock_status,
        company_id=claims.get("company_id"),
    )
    return env(out)


@api.get("/inventory/low-stock/export")
async def export_low_stock_csv(
    stock_status: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 137 L1 — low-stock alert CSV."""
    text = await inventory_ops_export_svc.export_low_stock_csv(
        db,
        tenant_id=claims["tenant_id"],
        stock_status=stock_status,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="low_stock_export.csv"'},
    )


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
    workspace_svc.assert_record_company(claims, product)
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
    workspace_svc.assert_record_company(claims, supplier)
    if payload.warehouse_id:
        from app.inventory import get_warehouse

        await get_warehouse(
            db, claims["tenant_id"], payload.warehouse_id, company_id=claims.get("company_id")
        )

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
        company_id=claims.get("company_id"),
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
    # Optional filters ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach product/warehouse/store lookup).
    product_id: Annotated[UuidIdValue | None, Query()] = None,
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    movement_type: Annotated[MovementTypeValue | None, Query()] = None,
    created_by: Annotated[UuidIdValue | None, Query()] = None,
    reason: Annotated[StockAdjustReasonValue | None, Query()] = None,
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Immutable stock movement history (BR-5.3). No DELETE endpoint."""
    return env(
        await reports_svc.inventory_movements(
            db,
            claims["tenant_id"],
            product_id=product_id or None,
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
            movement_type=movement_type or None,
            created_by=created_by or None,
            reason=reason or None,
        )
    )


@api.get("/inventory/stock-counts")
async def list_stock_counts(
    status: Annotated[StockCountReportStatusValue | None, Query()] = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await stock_counts_svc.list_counts(
        db, claims["tenant_id"], status=status
    )
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
    count_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.get_count(db, claims["tenant_id"], count_id)
    return env(await stock_counts_svc.serialize_count(db, count))


@api.patch("/inventory/stock-counts/{count_id}/items")
async def patch_stock_count_items(
    count_id: UuidIdValue,
    payload: StockCountItemsUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.update_count_items(
        db,
        tenant_id=claims["tenant_id"],
        count_id=count_id,
        # exclude_unset: omit notes → no change; explicit null → clear (BR-5.2).
        items=[i.model_dump(exclude_unset=True) for i in payload.items],
    )
    await db.commit()
    return env(await stock_counts_svc.serialize_count(db, count), "Count lines updated")


@api.post("/inventory/stock-counts/{count_id}/complete")
async def complete_stock_count(
    count_id: UuidIdValue,
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
    count_id: UuidIdValue,
    payload: StockCountCancel,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    count = await stock_counts_svc.cancel_count(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        count_id=count_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await stock_counts_svc.serialize_count(db, count), "Stock count cancelled")


@api.get("/inventory/movements/export")
async def export_movements_csv(
    product_id: str | None = None,
    warehouse_id: str | None = None,
    movement_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 137 M1 — stock movement CSV honoring list filters."""
    text = await inventory_ops_export_svc.export_movements_csv(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        from_date=from_date,
        to_date=to_date,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="stock_movements_export.csv"'},
    )


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
                *workspace_svc.company_scope_filter(m.Product, claims),
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    workspace_svc.assert_record_company(claims, product)
    stock_q = (
        select(m.WarehouseStock, m.Warehouse)
        .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
        .where(
            m.WarehouseStock.tenant_id == claims["tenant_id"],
            m.WarehouseStock.product_id == product_id,
        )
    )
    if claims.get("company_id"):
        stock_q = stock_q.where(
            (m.WarehouseStock.company_id == claims["company_id"])
            | (m.WarehouseStock.company_id.is_(None))
        )
    rows = (await db.execute(stock_q.order_by(m.Warehouse.code))).all()
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
                "id": stock.id,
                "company_id": getattr(stock, "company_id", None) or getattr(wh, "company_id", None),
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


@api.get("/products/{product_id}/warehouse-stock/export")
async def export_product_warehouse_stock(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 155 W1 — per-product warehouse-stock CSV (distinct from Stage 137 movements)."""
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    workspace_svc.assert_record_company(claims, product)
    text = await inventory_ops_export_svc.export_product_warehouse_stock_csv(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="product_{product_id}_warehouse_stock_export.csv"'
            )
        },
    )


@api.get("/inventory/stock-counts")
async def list_stock_counts(
    status: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 130 S1 — optional status filter for stock-count list honesty."""
    status_n = (status or "").strip().lower() or None
    rows = await ops_lifecycle_export_svc.list_stock_counts(
        db,
        tenant_id=claims["tenant_id"],
        status=status_n,
        company_id=claims.get("company_id"),
    )
    out = []
    for row in rows:
        data = await stock_counts_svc.serialize_count(db, row)
        data.pop("items", None)
        out.append(data)
    return env(out)


@api.get("/inventory/stock-counts/export")
async def stock_counts_export(
    status: str | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 130 S1 — stock-count list CSV (header metadata; not variance lines)."""
    status_n = (status or "").strip().lower() or None
    text = await ops_lifecycle_export_svc.export_stock_counts_csv(
        db,
        tenant_id=claims["tenant_id"],
        status=status_n,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="stock_counts_export.csv"'
        },
    )


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
        company_id=claims.get("company_id"),
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
    count = await stock_counts_svc.get_count(db, claims["tenant_id"], count_id, company_id=claims.get("company_id"))
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
        db, tenant_id=claims["tenant_id"], count_id=count_id,
        company_id=claims.get("company_id"),
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
        company_id=claims.get("company_id"),
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
        company_id=claims.get("company_id"),
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
        db, tenant_id=claims["tenant_id"], count_id=count_id,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await stock_counts_svc.serialize_count(db, count), "Stock count cancelled")


@api.post("/inventory/adjust/{product_id}")
async def adjust(
    product_id: UuidIdValue,
    payload: StockAdjust,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Coded stock adjustment (BR-5.2): damage | theft | expiry | found | lost."""
    from app.inventory import STOCK_ADJUSTMENT_REASONS

    reason = (payload.reason or "").strip().lower()
    if reason not in STOCK_ADJUSTMENT_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"reason must be one of {sorted(STOCK_ADJUSTMENT_REASONS)}",
        )
    product = await apply_stock_change(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        quantity_delta=money_json(payload.quantity),
        movement_type="adjustment",
        user_id=claims["sub"],
        notes=payload.notes,
        reason=reason,
        warehouse_id=payload.warehouse_id or None,
        allow_negative=True,
        reference_type="stock_adjustment",
    )
    await db.commit()
    return env(
        {
            "product_id": product.id,
            "stock_qty": money_json(product.stock_qty),
            "reason": reason,
            "warehouse_id": payload.warehouse_id or None,
        },
        "Stock adjusted",
    )


@api.post("/inventory/stock-in")
async def stock_in(
    payload: StockMove,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = await catalog_svc.get_product(db, claims["tenant_id"], payload.product_id)
    workspace_svc.assert_record_company(claims, product)
    result = await catalog_svc.stock_in_with_batch(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        product_id=payload.product_id,
        quantity=money_json(payload.quantity),
        unit_id=payload.unit_id,
        notes=payload.notes,
        warehouse_id=payload.warehouse_id,
        variant_id=payload.variant_id,
        batch_number=payload.batch_number,
        manufacturing_date=reports_svc.parse_date(payload.manufacturing_date),
        expiry_date=reports_svc.parse_date(payload.expiry_date),
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )
    await db.commit()
    return env(result, "Stock in recorded")


@api.post("/inventory/opening-stock")
async def opening_stock_post(
    payload: OpeningStockCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-5.2 — initialize on-hand stock (go-live / fiscal year) with optional equity journal."""
    from app import opening_stock as opening_stock_svc

    result = await opening_stock_svc.post_opening_stock(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        lines=[
            {
                **line.model_dump(),
                "manufacturing_date": reports_svc.parse_date(line.manufacturing_date),
                "expiry_date": reports_svc.parse_date(line.expiry_date),
            }
            for line in payload.lines
        ],
        post_journal=payload.post_journal,
        reference=payload.reference,
        notes=payload.notes,
    )
    await db.commit()
    return env(result, "Opening stock recorded")


@api.get("/inventory/opening-stock")
async def opening_stock_list(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
    # omit → 100; 0/negative/>500 → **422** (was free int; service silently clamped 1–500)
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    from app import opening_stock as opening_stock_svc

    rows = await opening_stock_svc.list_opening_stock_movements(
        db, claims["tenant_id"], limit=min(max(limit, 1), 500)
    )
    return env(rows)


@api.post("/inventory/stock-out")
async def stock_out(
    payload: StockOut,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.inventory import STOCK_OUT_REFERENCE_TYPES

    # Defense in depth — schema Literal already rejects omit/blank/invalid
    ref = (payload.reference_type or "").strip().lower()
    if ref not in STOCK_OUT_REFERENCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"reference_type must be one of {sorted(STOCK_OUT_REFERENCE_TYPES)}",
        )
    # OpenAPI StockMovementReferenceIdValue → 422; catalog also defends → 400.
    from app.honesty import optional_honest_narrative

    ref_id = optional_honest_narrative(
        payload.reference_id, label="stock movement reference id", max_length=36
    )
    result = await catalog_svc.stock_out_with_batch(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        product_id=payload.product_id,
        quantity=money_json(payload.quantity),
        unit_id=payload.unit_id,
        notes=payload.notes,
        warehouse_id=payload.warehouse_id,
        variant_id=payload.variant_id,
        batch_id=payload.batch_id,
        reference_type=ref,
        reference_id=ref_id,
    )
    result["reference_type"] = ref
    result["reference_id"] = ref_id
    await db.commit()
    return env(result, "Stock out recorded")


@api.get("/inventory/warehouse-stock")
async def inventory_warehouse_stock(
    warehouse_id: UuidIdValue,
    include_zero: bool = False,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-5.4 — view on-hand + reorder policy for one warehouse."""
    from app import inventory as inventory_svc

    if not (warehouse_id or "").strip():
        raise HTTPException(status_code=400, detail="warehouse_id is required")
    return env(
        await inventory_svc.list_warehouse_stock(
            db,
            claims["tenant_id"],
            warehouse_id.strip(),
            include_zero=include_zero,
        )
    )


@api.put("/inventory/warehouse-stock/reorder")
async def inventory_warehouse_stock_reorder(
    payload: WarehouseReorderPolicyUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-5.4 — set per-warehouse reorder level/qty."""
    from app import inventory as inventory_svc

    row = await inventory_svc.set_warehouse_reorder_policy(
        db,
        tenant_id=claims["tenant_id"],
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        reorder_level=payload.reorder_level,
        reorder_qty=payload.reorder_qty,
    )
    await db.commit()
    return env(row, "Warehouse reorder policy saved")


@api.get("/inventory/products/lookup")
async def inventory_products_lookup(
    q: Annotated[ProductSearchQueryValue, Query()] = "",
    barcode: Annotated[ProductBarcodeValue | None, Query()] = None,
    # omit → 48; 0/negative/>100 → **422** (was free int; service silently clamped 1–100)
    limit: Annotated[int, Query(ge=1, le=100)] = 48,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-18.2 — barcode / SKU / name product lookup (inventory:read; API-key friendly)."""
    from app import inventory as inventory_svc

    return env(
        await inventory_svc.lookup_products(
            db,
            claims["tenant_id"],
            q=q,
            barcode=barcode,
            limit=limit,
        )
    )


@api.get("/products/{product_id}/warehouse-stock")
async def product_warehouse_stock(
    product_id: UuidIdValue,
    include_zero: bool = True,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-18.2 / BR-5.4 — per-warehouse stock levels for one product."""
    from app import inventory as inventory_svc

    return env(
        await inventory_svc.list_product_warehouse_stock(
            db,
            claims["tenant_id"],
            product_id,
            include_zero=include_zero,
        )
    )


@api.get("/products/{product_id}/variants")
async def list_product_variants(
    product_id: UuidIdValue,
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List product variants. Optional is_active filters soft-deactivated rows (Inventory manage UI)."""
    rows = await catalog_svc.list_variants(
        db, claims["tenant_id"], product_id, is_active=is_active
    )
    return env([catalog_svc.serialize_variant(v) for v in rows])


@api.get("/products/{product_id}/variants/export")
async def export_product_variants(
    product_id: str,
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 156 V1 — path-scoped per-product variants CSV (distinct from Stage 124 roster)."""
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    workspace_svc.assert_record_company(claims, product)
    text = await variant_role_export_svc.export_product_variants_csv(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        is_active=is_active,
        active_only=active_only,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="product_{product_id}_variants_export.csv"'
            )
        },
    )


@api.post("/products/{product_id}/barcode/generate")
async def generate_product_barcode(
    product_id: str,
    format: str = "code128",
    force: bool = False,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id,
                *workspace_svc.company_scope_filter(m.Product, claims),
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    workspace_svc.assert_record_company(claims, product)
    product = await barcode_svc.assign_product_barcode(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product_id,
        format=format,
        force=force,
        company_id=claims.get("company_id") or getattr(product, "company_id", None),
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
    code_type: str = "barcode",
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 97 I1 — `code_type=barcode|qr` for printable product labels."""
    from app import tenants as tenants_svc

    ctype = (code_type or "barcode").strip().lower()
    if ctype not in {"barcode", "qr"}:
        raise HTTPException(status_code=400, detail="code_type must be barcode or qr")
    labels = await barcode_labels_svc.resolve_label_targets(
        db,
        tenant_id=claims["tenant_id"],
        company_id=claims.get("company_id"),
        items=[{"product_id": product_id, "copies": copies}],
    )
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    currency = tenant.currency or "GHS"
    if not include_price:
        for label in labels:
            label["price"] = None
    fmt = (format or "html").strip().lower()
    if fmt == "html":
        return HTMLResponse(
            barcode_labels_svc.build_labels_html(labels, currency=currency, code_type=ctype)
        )
    if fmt == "png":
        png = barcode_labels_svc.build_labels_sheet_png(
            labels, currency=currency, code_type=ctype
        )
        return Response(
            content=png,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="{"qr" if ctype == "qr" else "barcode"}_labels.png"'
            },
        )
    if fmt == "pdf":
        pdf = barcode_labels_svc.build_labels_pdf(labels, currency=currency, code_type=ctype)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{"qr" if ctype == "qr" else "barcode"}_labels.pdf"'
            },
        )
    raise HTTPException(status_code=400, detail="format must be html, png, or pdf")


@api.post("/inventory/labels")
async def print_barcode_labels(
    payload: BarcodeLabelPrintRequest,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    ctype = (payload.code_type or "barcode").strip().lower()
    if ctype not in {"barcode", "qr"}:
        raise HTTPException(status_code=400, detail="code_type must be barcode or qr")
    labels = await barcode_labels_svc.resolve_label_targets(
        db,
        tenant_id=claims["tenant_id"],
        company_id=claims.get("company_id"),
        items=[i.model_dump() for i in payload.items],
    )
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    currency = tenant.currency or "GHS"
    if not payload.include_price:
        for label in labels:
            label["price"] = None
    fmt = (payload.format or "html").strip().lower()
    if fmt == "html":
        return HTMLResponse(
            barcode_labels_svc.build_labels_html(labels, currency=currency, code_type=ctype)
        )
    if fmt == "png":
        png = barcode_labels_svc.build_labels_sheet_png(
            labels, currency=currency, cols=payload.columns, code_type=ctype
        )
        return Response(
            content=png,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="{"qr" if ctype == "qr" else "barcode"}_labels.png"'
            },
        )
    if fmt == "pdf":
        pdf = barcode_labels_svc.build_labels_pdf(labels, currency=currency, code_type=ctype)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{"qr" if ctype == "qr" else "barcode"}_labels.pdf"'
            },
        )
    raise HTTPException(status_code=400, detail="format must be html, png, or pdf")


@api.post("/products/{product_id}/variants")
async def create_product_variant(
    product_id: UuidIdValue,
    payload: ProductVariantCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    workspace_svc.assert_record_company(claims, product)
    data = payload.model_dump()
    data["barcode"] = await barcode_svc.assert_barcode_available(
        db,
        tenant_id=claims["tenant_id"],
        barcode=data.get("barcode"),
        company_id=claims.get("company_id") or getattr(product, "company_id", None),
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
    product_id: UuidIdValue,
    variant_id: UuidIdValue,
    payload: ProductVariantUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
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
        dosage=data.get("dosage"),
        cost_price=data.get("cost_price"),
        selling_price=data.get("selling_price"),
        is_active=data.get("is_active"),
        clear_barcode="barcode" in data and data["barcode"] is None,
        clear_size="size" in data and data["size"] is None,
        clear_color="color" in data and data["color"] is None,
        clear_flavor="flavor" in data and data["flavor"] is None,
        clear_dosage="dosage" in data and data["dosage"] is None,
    )
    await db.commit()
    return env(catalog_svc.serialize_variant(variant), "Variant updated")


@api.post("/products/{product_id}/variants/{variant_id}/barcode/generate")
async def variant_barcode_generate(
    product_id: UuidIdValue,
    variant_id: UuidIdValue,
    force: bool = False,
    symbology: Annotated[BarcodeSymbologyValue, Query()] = "code128",
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Assign a barcode to a product variant (Code128 / EAN-13 / UPC-A)."""
    sym = barcodes_svc.normalize_symbology(symbology)
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    variant = await catalog_svc.get_variant(db, claims["tenant_id"], variant_id)
    if variant.product_id != product.id:
        raise HTTPException(status_code=404, detail="Variant not found")
    if variant.barcode and not force:
        out = catalog_svc.serialize_variant(variant)
        out["symbology"] = barcodes_svc.detect_symbology(variant.barcode)
        return env(out, "Barcode already set")

    candidate = await barcodes_svc.allocate_unique_barcode(
        db,
        tenant_id=claims["tenant_id"],
        sku=variant.sku,
        symbology=sym,
        seed=f"{variant.id}:{variant.sku}",
        exclude_variant_id=variant.id,
    )
    variant.barcode = candidate
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="inventory",
        action="variant_barcode_generate",
        entity="product_variant",
        entity_id=variant.id,
        details={
            "barcode": variant.barcode,
            "sku": variant.sku,
            "product_id": product.id,
            "symbology": sym,
        },
    )
    await db.commit()
    await db.refresh(variant)
    out = catalog_svc.serialize_variant(variant)
    out["symbology"] = sym
    return env(out, "Barcode generated")


@api.get("/products/{product_id}/variants/{variant_id}/barcode.png")
async def variant_barcode_png(
    product_id: UuidIdValue,
    variant_id: UuidIdValue,
    symbology: Annotated[BarcodeSymbologyValue | None, Query()] = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    variant = await catalog_svc.get_variant(db, claims["tenant_id"], variant_id)
    if variant.product_id != product.id:
        raise HTTPException(status_code=404, detail="Variant not found")
    code = variant.barcode or variant.sku
    if not code:
        raise HTTPException(status_code=404, detail="No barcode or SKU available")
    sym = (
        barcodes_svc.normalize_symbology(symbology)
        if symbology
        else barcodes_svc.detect_symbology(str(code))
    )
    png = barcodes_svc.render_barcode_png(str(code), symbology=sym)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="barcode-{variant.sku}.png"'},
    )


@api.get("/products/{product_id}/variants/{variant_id}/barcode/label")
async def variant_barcode_label(
    product_id: UuidIdValue,
    variant_id: UuidIdValue,
    # omit → 1; 0/negative/>40 → **422** (was free int; service silently clamped 1–40)
    copies: Annotated[int, Query(ge=1, le=40)] = 1,
    symbology: Annotated[BarcodeSymbologyValue | None, Query()] = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    import base64

    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    variant = await catalog_svc.get_variant(db, claims["tenant_id"], variant_id)
    if variant.product_id != product.id:
        raise HTTPException(status_code=404, detail="Variant not found")
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    code = variant.barcode or variant.sku
    if not code:
        raise HTTPException(status_code=404, detail="No barcode or SKU available")
    sym = (
        barcodes_svc.normalize_symbology(symbology)
        if symbology
        else barcodes_svc.detect_symbology(str(code))
    )
    png = barcodes_svc.render_barcode_png(str(code), symbology=sym)
    data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    page = barcodes_svc.label_html(
        company_name=(tenant.company_name if tenant else "RIBDIGI ERP"),
        product_name=f"{product.name} / {variant.name}",
        sku=variant.sku,
        barcode_value=str(code),
        price=money_json(variant.selling_price or product.selling_price or 0),
        currency=(tenant.currency if tenant else "GHS"),
        png_data_uri=data_uri,
        copies=copies,
        symbology=sym,
    )
    return Response(content=page, media_type="text/html; charset=utf-8")


@api.delete("/products/{product_id}/variants/{variant_id}")
async def delete_product_variant(
    product_id: UuidIdValue,
    variant_id: UuidIdValue,
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
    product_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    workspace_svc.assert_record_company(claims, product)
    rows = await catalog_svc.list_batches(db, claims["tenant_id"], product_id=product_id)
    return env([catalog_svc.serialize_batch(b) for b in rows])


@api.get("/products/{product_id}/batches/export")
async def export_product_batches(
    product_id: str,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 154 K1 — per-product batches CSV (distinct from Stage 137 expiring export)."""
    product = await catalog_svc.get_product(db, claims["tenant_id"], product_id)
    workspace_svc.assert_record_company(claims, product)
    text = await inventory_ops_export_svc.export_product_batches_csv(
        db, tenant_id=claims["tenant_id"], product_id=product_id
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="product_{product_id}_batches_export.csv"'
        },
    )


@api.get("/inventory/batches/expiring")
async def inventory_batches_expiring(
    # omit → 30; 0/negative/>365 → **422** (was free int; negative/huge horizons accepted)
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await catalog_svc.list_expiring_batches(
        db,
        claims["tenant_id"],
        within_days=days,
        company_id=claims.get("company_id"),
    )
    return env(
        {
            "within_days": days,
            "count": len(rows),
            "batches": [catalog_svc.serialize_batch(b) for b in rows],
        }
    )


@api.get("/inventory/batches/expiring/export")
async def export_expiring_batches_csv(
    days: int = 30,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 137 E1 — expiring batches CSV."""
    text = await inventory_ops_export_svc.export_expiring_batches_csv(
        db,
        tenant_id=claims["tenant_id"],
        days=days,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="expiring_batches_export.csv"'
        },
    )


async def party_list(kind: str, claims: dict, db: AsyncSession):
    rows = (
        await db.execute(
            select(m.Party).where(m.Party.tenant_id == claims["tenant_id"], m.Party.kind == kind)
        )
    ).scalars().all()
    return env(rows)


_PARTY_PROFILE_TYPES = {
    "customer": frozenset({"walk_in", "registered"}),
    "supplier": frozenset({"registered", "trade", "manufacturer", "service", "other"}),
}
_PARTY_STATUSES = frozenset({"active", "inactive"})


def _serialize_party(row: m.Party, group: m.CustomerGroup | None = None) -> dict:
    lat = getattr(row, "latitude", None)
    lng = getattr(row, "longitude", None)
    data = {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "kind": row.kind,
        "code": getattr(row, "code", None),
        "name": row.name,
        "profile_type": getattr(row, "profile_type", None) or "registered",
        "category": getattr(row, "category", None),
        "status": getattr(row, "status", None) or "active",
        "email": row.email,
        "phone": row.phone,
        "address": getattr(row, "address", None),
        "latitude": money_json(lat) if lat is not None else None,
        "longitude": money_json(lng) if lng is not None else None,
        "credit_limit": money_json(row.credit_limit),
        "payment_terms_days": int(getattr(row, "payment_terms_days", None) or 30),
        "balance": money_json(row.balance),
        "customer_group_id": getattr(row, "customer_group_id", None),
    }
    if group is not None:
        from app.customer_groups import serialize_group

        data["customer_group"] = serialize_group(group)
    else:
        data["customer_group"] = None
    return data


async def _party_with_contacts(
    db: AsyncSession,
    party: m.Party,
    *,
    group: m.CustomerGroup | None = None,
) -> dict:
    data = _serialize_party(party, group)
    contacts = await party_contacts_svc.list_contacts(
        db, tenant_id=party.tenant_id, party_id=party.id, kind=party.kind
    )
    data["contacts"] = [party_contacts_svc.serialize_contact(c) for c in contacts]
    return data


def _normalize_party_profile(data: dict, *, kind: str) -> dict:
    from app.honesty import optional_honest_narrative, require_honest_narrative

    if "name" in data and data["name"] is not None:
        # OpenAPI PartyNameValue → 422; service defense-in-depth → 400.
        data["name"] = require_honest_narrative(
            data["name"], label="party name", max_length=180
        )
    if "code" in data:
        # OpenAPI PartyCodeValue → 422; service defense-in-depth → 400.
        data["code"] = optional_honest_narrative(
            data["code"], label="party code", max_length=64
        )
    if "profile_type" in data:
        pt = data["profile_type"]
        # Defense in depth: PartyCreate/Update Literals reject blank/unknown with
        # 422 first. Empty used to coerce to "registered" — schema honesty closes
        # that gap (R1). Kind-specific allow-list remains here.
        if pt is None or str(pt).strip() == "":
            raise HTTPException(
                status_code=400,
                detail=f"profile_type must be one of {sorted(_PARTY_PROFILE_TYPES[kind])}",
            )
        pt = str(pt).strip().lower()
        allowed = _PARTY_PROFILE_TYPES[kind]
        if pt not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid profile_type; expected one of {sorted(allowed)}",
            )
        data["profile_type"] = pt
    if "status" in data and data["status"] is not None:
        st = str(data["status"]).strip().lower()
        if st not in _PARTY_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status; expected active or inactive")
        data["status"] = st
    if "category" in data and data["category"] is not None:
        # OpenAPI PartyCategoryValue → 422; service defense-in-depth → 400.
        data["category"] = optional_honest_narrative(
            data["category"], label="party category", max_length=80
        )
    if "address" in data and data["address"] is not None:
        # OpenAPI AddressValue → 422; service defense-in-depth → 400.
        data["address"] = optional_honest_narrative(
            data["address"], label="party address", max_length=500
        )
    if "phone" in data and data["phone"] is not None:
        # OpenAPI E164PhoneValue → 422; service defense-in-depth → 400.
        from app.schemas import validate_e164_phone_value

        try:
            data["phone"] = validate_e164_phone_value(str(data["phone"]).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    for coord, lo, hi in (("latitude", -90.0, 90.0), ("longitude", -180.0, 180.0)):
        if coord not in data or data[coord] is None:
            continue
        try:
            val = money_json(data[coord])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {coord}") from exc
        if val < lo or val > hi:
            raise HTTPException(status_code=400, detail=f"{coord} out of range")
        data[coord] = val
    return data


async def _ensure_party_code_unique(
    db: AsyncSession,
    tenant_id: str,
    code: str | None,
    *,
    exclude_id: str | None = None,
) -> None:
    if not code:
        return
    q = select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.code == code)
    if exclude_id:
        q = q.where(m.Party.id != exclude_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Party code already in use for this tenant")


@api.get("/customers/groups")
async def list_customer_groups(
    is_active: bool | None = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List customer groups. Optional is_active filters soft-deactivated rows (Sales manage UI)."""
    from app import customer_groups as customer_groups_svc

    rows = await customer_groups_svc.list_groups(
        db, claims["tenant_id"], is_active=is_active
    )
    await db.commit()
    return env([customer_groups_svc.serialize_group(r) for r in rows])


@api.post("/customers/groups")
async def create_customer_group(
    payload: CustomerGroupCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import customer_groups as customer_groups_svc

    row = await customer_groups_svc.create_group(
        db,
        tenant_id=claims["tenant_id"],
        name=payload.name,
        code=payload.code,
        discount_percent=payload.discount_percent,
    )
    await db.commit()
    await db.refresh(row)
    return env(customer_groups_svc.serialize_group(row))


@api.patch("/customers/groups/{group_id}")
async def patch_customer_group(
    group_id: UuidIdValue,
    payload: CustomerGroupUpdate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import customer_groups as customer_groups_svc

    row = await customer_groups_svc.update_group(
        db,
        tenant_id=claims["tenant_id"],
        group_id=group_id,
        name=payload.name,
        discount_percent=payload.discount_percent,
        is_active=payload.is_active,
    )
    await db.commit()
    await db.refresh(row)
    return env(customer_groups_svc.serialize_group(row))


@api.get("/customers")
async def customers(
    status: Annotated[PartyStatusValue | None, Query()] = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import customer_groups as customer_groups_svc

    await customer_groups_svc.ensure_default_groups(db, claims["tenant_id"])
    q = select(m.Party).where(
        m.Party.tenant_id == claims["tenant_id"], m.Party.kind == "customer"
    )
    # Schema PartyStatusValue rejects blank/invalid → 422; keep allow-list defense-in-depth.
    if status:
        st = status.strip().lower()
        if st not in _PARTY_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid status filter")
        q = q.where(m.Party.status == st)
    rows = (await db.execute(q)).scalars().all()
    group_ids = {r.customer_group_id for r in rows if r.customer_group_id}
    groups: dict[str, m.CustomerGroup] = {}
    if group_ids:
        groups = {
            g.id: g
            for g in (
                await db.execute(
                    select(m.CustomerGroup).where(
                        m.CustomerGroup.tenant_id == claims["tenant_id"],
                        m.CustomerGroup.id.in_(group_ids),
                    )
                )
            ).scalars().all()
        }
    await db.commit()
    return env([_serialize_party(r, groups.get(r.customer_group_id)) for r in rows])


@api.get("/customers/{customer_id}")
async def get_customer(
    customer_id: UuidIdValue,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import customer_groups as customer_groups_svc

    party = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == customer_id,
                m.Party.tenant_id == claims["tenant_id"],
                m.Party.kind == "customer",
            )
        )
    ).scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Customer not found")
    group = None
    if party.customer_group_id:
        group = await customer_groups_svc.get_group(
            db, claims["tenant_id"], party.customer_group_id
        )
    data = await _party_with_contacts(db, party, group=group)
    await db.commit()
    return env(data)


@api.post("/customers")
async def add_customer(
    payload: CustomerCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import customer_groups as customer_groups_svc

    data = _normalize_party_profile(payload.model_dump(), kind="customer")
    group_id = data.pop("customer_group_id", None)
    if group_id:
        await customer_groups_svc.require_active_group(db, claims["tenant_id"], group_id)
    await _ensure_party_code_unique(db, claims["tenant_id"], data.get("code"))
    party = m.Party(
        tenant_id=claims["tenant_id"],
        kind="customer",
        customer_group_id=group_id,
        **data,
    )
    db.add(party)
    await db.flush()
    await webhooks_svc.emit_event(
        db,
        tenant_id=claims["tenant_id"],
        event="customer.created",
        data={
            "customer_id": party.id,
            "code": party.code,
            "name": party.name,
            "customer_group_id": party.customer_group_id,
        },
    )
    await db.commit()
    await db.refresh(party)
    group = None
    if party.customer_group_id:
        group = await customer_groups_svc.get_group(
            db, claims["tenant_id"], party.customer_group_id
        )
    return env(_serialize_party(party, group))


@api.patch("/customers/{customer_id}")
async def patch_customer(
    customer_id: UuidIdValue,
    payload: PartyUpdate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import customer_groups as customer_groups_svc

    party = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == customer_id,
                m.Party.tenant_id == claims["tenant_id"],
                m.Party.kind == "customer",
            )
        )
    ).scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Customer not found")
    data = _normalize_party_profile(payload.model_dump(exclude_unset=True), kind="customer")
    if "customer_group_id" in data:
        group_id = data["customer_group_id"]
        if group_id:
            await customer_groups_svc.require_active_group(db, claims["tenant_id"], group_id)
        party.customer_group_id = group_id
        data.pop("customer_group_id")
    if "code" in data:
        await _ensure_party_code_unique(
            db, claims["tenant_id"], data.get("code"), exclude_id=party.id
        )
    for key, value in data.items():
        setattr(party, key, value)
    await db.commit()
    await db.refresh(party)
    group = None
    if party.customer_group_id:
        group = await customer_groups_svc.get_group(
            db, claims["tenant_id"], party.customer_group_id
        )
    return env(_serialize_party(party, group))


@api.get("/customers/{customer_id}/contacts")
async def list_customer_contacts(
    customer_id: UuidIdValue,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await party_contacts_svc.list_contacts(
        db, tenant_id=claims["tenant_id"], party_id=customer_id, kind="customer"
    )
    return env([party_contacts_svc.serialize_contact(r) for r in rows])


@api.post("/customers/{customer_id}/contacts")
async def create_customer_contact(
    customer_id: UuidIdValue,
    payload: PartyContactCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    row = await party_contacts_svc.create_contact(
        db,
        tenant_id=claims["tenant_id"],
        party_id=customer_id,
        kind="customer",
        name=payload.name,
        phone=payload.phone,
        email=str(payload.email) if payload.email is not None else None,
        designation=payload.designation,
        is_primary=payload.is_primary,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="sales",
        action="party_contact_created",
        entity="party_contact",
        entity_id=row.id,
        details={"party_id": customer_id, "kind": "customer"},
    )
    await db.commit()
    return env(party_contacts_svc.serialize_contact(row), "Contact created")


@api.patch("/customers/{customer_id}/contacts/{contact_id}")
async def patch_customer_contact(
    customer_id: UuidIdValue,
    contact_id: UuidIdValue,
    payload: PartyContactUpdate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    row = await party_contacts_svc.update_contact(
        db,
        tenant_id=claims["tenant_id"],
        party_id=customer_id,
        kind="customer",
        contact_id=contact_id,
        **data,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="sales",
        action="party_contact_updated",
        entity="party_contact",
        entity_id=row.id,
        details={"party_id": customer_id, "kind": "customer"},
    )
    await db.commit()
    return env(party_contacts_svc.serialize_contact(row), "Contact updated")


@api.delete("/customers/{customer_id}/contacts/{contact_id}")
async def delete_customer_contact(
    customer_id: UuidIdValue,
    contact_id: UuidIdValue,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    await party_contacts_svc.delete_contact(
        db,
        tenant_id=claims["tenant_id"],
        party_id=customer_id,
        kind="customer",
        contact_id=contact_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="sales",
        action="party_contact_deleted",
        entity="party_contact",
        entity_id=contact_id,
        details={"party_id": customer_id, "kind": "customer"},
    )
    await db.commit()
    return env({"id": contact_id}, "Contact deleted")


@api.get("/products/{product_id}/price")
async def product_price_for_customer(
    product_id: UuidIdValue,
    # Optional customer/variant ∈ UuidIdValue; omit/`null` OK; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach party/variant lookup).
    customer_id: Annotated[UuidIdValue | None, Query()] = None,
    variant_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.catalog import get_product, get_variant, resolve_sale_line
    from app import customer_groups as customer_groups_svc

    product = await get_product(db, claims["tenant_id"], product_id)
    variant = None
    if variant_id:
        variant = await get_variant(db, claims["tenant_id"], variant_id)
    list_price = money_json(
        (variant.selling_price if variant is not None else product.selling_price) or 0
    )
    _product, _variant, unit_price = await resolve_sale_line(
        db,
        claims["tenant_id"],
        {"product_id": product_id, "variant_id": variant_id},
        customer_id=customer_id,
    )
    pct, group = await customer_groups_svc.customer_group_discount(
        db, claims["tenant_id"], customer_id
    )
    return env(
        {
            "product_id": product_id,
            "variant_id": variant_id,
            "customer_id": customer_id,
            "list_price": list_price,
            "unit_price": unit_price,
            "discount_percent": pct,
            "customer_group": customer_groups_svc.serialize_group(group) if group else None,
        }
    )


@api.get("/suppliers")
async def suppliers(
    status: Annotated[PartyStatusValue | None, Query()] = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    q = select(m.Party).where(
        m.Party.tenant_id == claims["tenant_id"], m.Party.kind == "supplier"
    )
    # Schema PartyStatusValue rejects blank/invalid → 422; keep allow-list defense-in-depth.
    if status:
        st = status.strip().lower()
        if st not in _PARTY_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid status filter")
        q = q.where(m.Party.status == st)
    rows = (await db.execute(q)).scalars().all()
    await db.commit()
    return env([_serialize_party(r) for r in rows])


@api.get("/suppliers/{supplier_id}")
async def get_supplier(
    supplier_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    party = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == supplier_id,
                m.Party.tenant_id == claims["tenant_id"],
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Supplier not found")
    data = await _party_with_contacts(db, party)
    await db.commit()
    return env(data)


@api.post("/suppliers")
async def add_supplier(
    payload: SupplierCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = _normalize_party_profile(payload.model_dump(), kind="supplier")
    data.pop("customer_group_id", None)
    await _ensure_party_code_unique(db, claims["tenant_id"], data.get("code"))
    party = m.Party(tenant_id=claims["tenant_id"], kind="supplier", **data)
    db.add(party)
    await db.flush()
    await webhooks_svc.emit_event(
        db,
        tenant_id=claims["tenant_id"],
        event="supplier.created",
        data={
            "supplier_id": party.id,
            "code": party.code,
            "name": party.name,
            "email": party.email,
            "status": party.status,
        },
    )
    await db.commit()
    await db.refresh(party)
    return env(_serialize_party(party))


@api.patch("/suppliers/{supplier_id}")
async def patch_supplier(
    supplier_id: UuidIdValue,
    payload: PartyUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == supplier_id,
                m.Party.tenant_id == claims["tenant_id"],
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Supplier not found")
    data = _normalize_party_profile(payload.model_dump(exclude_unset=True), kind="supplier")
    data.pop("customer_group_id", None)
    if "code" in data:
        await _ensure_party_code_unique(
            db, claims["tenant_id"], data.get("code"), exclude_id=party.id
        )
    for key, value in data.items():
        setattr(party, key, value)
    await db.commit()
    await db.refresh(party)
    return env(_serialize_party(party))


@api.get("/suppliers/{supplier_id}/contacts")
async def list_supplier_contacts(
    supplier_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await party_contacts_svc.list_contacts(
        db, tenant_id=claims["tenant_id"], party_id=supplier_id, kind="supplier"
    )
    return env([party_contacts_svc.serialize_contact(r) for r in rows])


@api.post("/suppliers/{supplier_id}/contacts")
async def create_supplier_contact(
    supplier_id: UuidIdValue,
    payload: PartyContactCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    row = await party_contacts_svc.create_contact(
        db,
        tenant_id=claims["tenant_id"],
        party_id=supplier_id,
        kind="supplier",
        name=payload.name,
        phone=payload.phone,
        email=str(payload.email) if payload.email is not None else None,
        designation=payload.designation,
        is_primary=payload.is_primary,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="party_contact_created",
        entity="party_contact",
        entity_id=row.id,
        details={"party_id": supplier_id, "kind": "supplier"},
    )
    await db.commit()
    return env(party_contacts_svc.serialize_contact(row), "Contact created")


@api.patch("/suppliers/{supplier_id}/contacts/{contact_id}")
async def patch_supplier_contact(
    supplier_id: UuidIdValue,
    contact_id: UuidIdValue,
    payload: PartyContactUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    row = await party_contacts_svc.update_contact(
        db,
        tenant_id=claims["tenant_id"],
        party_id=supplier_id,
        kind="supplier",
        contact_id=contact_id,
        **data,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="party_contact_updated",
        entity="party_contact",
        entity_id=row.id,
        details={"party_id": supplier_id, "kind": "supplier"},
    )
    await db.commit()
    return env(party_contacts_svc.serialize_contact(row), "Contact updated")


@api.delete("/suppliers/{supplier_id}/contacts/{contact_id}")
async def delete_supplier_contact(
    supplier_id: UuidIdValue,
    contact_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    await party_contacts_svc.delete_contact(
        db,
        tenant_id=claims["tenant_id"],
        party_id=supplier_id,
        kind="supplier",
        contact_id=contact_id,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="party_contact_deleted",
        entity="party_contact",
        entity_id=contact_id,
        details={"party_id": supplier_id, "kind": "supplier"},
    )
    await db.commit()
    return env({"id": contact_id}, "Contact deleted")


async def tx_list(kind: str, claims: dict, db: AsyncSession):
    stmt = (
        select(m.Transaction)
        .where(
            *workspace_svc.company_scope_filter(m.Transaction, claims),
            m.Transaction.tx_type == kind,
        )
        .order_by(m.Transaction.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return env(rows)


async def tx_add(kind: str, payload: TransactionCreate, claims: dict, db: AsyncSession):
    items = [i.model_dump() for i in payload.items]
    if not items and payload.payload and payload.payload.items:
        items = [i.model_dump() for i in payload.payload.items]
    if kind in {"sale", "pos_sale", "purchase"} and not items:
        raise HTTPException(
            status_code=400,
            detail="items are required for sale/purchase/pos so stock can be updated correctly",
        )

    tx_override_info = None
    if kind in {"sale", "pos_sale"} and payload.party_id:
        from app.credit import claims_may_override_credit, enforce_customer_credit_limit
        from app.sales import require_active_customer

        party = await require_active_customer(db, claims["tenant_id"], payload.party_id)
        tx_override_info = enforce_customer_credit_limit(
            party,
            amount=money_json(payload.total or 0),
            override=bool(payload.override_credit_limit),
            override_allowed=claims_may_override_credit(claims),
            override_reason=payload.override_reason,
            extra={"source": kind},
        )

    ref = f"{kind.upper()}-{datetime.utcnow():%Y%m%d%H%M%S%f}"
    body = payload.model_dump()
    body.pop("items", None)
    body.pop("override_credit_limit", None)
    body.pop("override_reason", None)
    body.pop("payload", None)
    # Server-owned bag — only typed LineItem rows (no client poison keys).
    body["payload"] = {"items": items}
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
        company_id=company_id,
    )

    if payload.party_id and kind in {"sale", "pos_sale"}:
        party = await db.get(m.Party, payload.party_id)
        if party and party.tenant_id == claims["tenant_id"]:
            party.balance = money_json(party.balance or 0) + money_json(payload.total or 0)
    if payload.party_id and kind == "purchase":
        party = await db.get(m.Party, payload.party_id)
        if party and party.tenant_id == claims["tenant_id"]:
            party.balance = money_json(party.balance or 0) + money_json(payload.total or 0)

    if tx_override_info:
        db.add(
            m.AuditLog(
                tenant_id=claims["tenant_id"],
                user_id=claims["sub"],
                action="credit_limit_override",
                entity="customer",
                entity_id=tx_override_info["customer_id"],
                details={**tx_override_info, "source": kind, "transaction_id": tx.id, "reference": ref},
            )
        )

    await db.commit()
    return env(
        {
            "id": tx.id,
            "reference": ref,
            "credit_limit_overridden": bool(tx_override_info),
        }
    )


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
    status: Annotated[SalesInvoiceStatusValue | None, Query()] = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.sales import SI_MANAGE_STATUSES

    stmt = (
        select(m.SalesInvoice)
        .where(m.SalesInvoice.tenant_id == claims["tenant_id"])
        .order_by(m.SalesInvoice.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesInvoice, claims)
    # Schema SalesInvoiceStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in SI_MANAGE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid sales invoice status '{wanted}'. "
                    f"Allowed: {sorted(SI_MANAGE_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.SalesInvoice.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await sales_svc.serialize_invoice(db, inv) for inv in rows])


@api.get("/sales/settings")
async def sales_settings(
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import numbering_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(
        {
            "invoice_numbering": numbering_settings(tenant, "sales_invoice"),
            "quotation_numbering": numbering_settings(tenant, "quotation"),
            "sales_order_numbering": numbering_settings(tenant, "sales_order"),
            "sales_return_numbering": numbering_settings(tenant, "sales_return"),
            "credit_note_numbering": numbering_settings(tenant, "credit_note"),
            "payment_receipt_numbering": numbering_settings(tenant, "customer_payment"),
        }
    )


@api.patch("/sales/settings")
async def update_sales_settings(
    payload: SalesSettingsUpdate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import apply_numbering_update, numbering_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    inv = payload.invoice_numbering
    if inv is None and payload.prefix is not None:
        inv = DocumentNumberingFields(
            prefix=payload.prefix, next_number=payload.next_number or 1
        )
    if inv is not None:
        apply_numbering_update(
            tenant, "sales_invoice", prefix=inv.prefix, next_number=inv.next_number
        )
    if payload.quotation_numbering is not None:
        apply_numbering_update(
            tenant,
            "quotation",
            prefix=payload.quotation_numbering.prefix,
            next_number=payload.quotation_numbering.next_number,
        )
    if payload.sales_order_numbering is not None:
        apply_numbering_update(
            tenant,
            "sales_order",
            prefix=payload.sales_order_numbering.prefix,
            next_number=payload.sales_order_numbering.next_number,
        )
    if payload.sales_return_numbering is not None:
        apply_numbering_update(
            tenant,
            "sales_return",
            prefix=payload.sales_return_numbering.prefix,
            next_number=payload.sales_return_numbering.next_number,
        )
    if payload.credit_note_numbering is not None:
        apply_numbering_update(
            tenant,
            "credit_note",
            prefix=payload.credit_note_numbering.prefix,
            next_number=payload.credit_note_numbering.next_number,
        )
    if payload.payment_receipt_numbering is not None:
        apply_numbering_update(
            tenant,
            "customer_payment",
            prefix=payload.payment_receipt_numbering.prefix,
            next_number=payload.payment_receipt_numbering.next_number,
        )
    if (
        inv is None
        and payload.quotation_numbering is None
        and payload.sales_order_numbering is None
        and payload.sales_return_numbering is None
        and payload.credit_note_numbering is None
        and payload.payment_receipt_numbering is None
    ):
        raise HTTPException(status_code=400, detail="No numbering fields to update")
    await db.commit()
    return env(
        {
            "invoice_numbering": numbering_settings(tenant, "sales_invoice"),
            "quotation_numbering": numbering_settings(tenant, "quotation"),
            "sales_order_numbering": numbering_settings(tenant, "sales_order"),
            "sales_return_numbering": numbering_settings(tenant, "sales_return"),
            "credit_note_numbering": numbering_settings(tenant, "credit_note"),
            "payment_receipt_numbering": numbering_settings(tenant, "customer_payment"),
        },
        "Sales document numbering updated",
    )


@api.get("/purchasing/settings")
async def purchasing_settings(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import numbering_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(
        {
            "purchase_order_numbering": numbering_settings(tenant, "purchase_order"),
            "grn_numbering": numbering_settings(tenant, "grn"),
            "purchase_invoice_numbering": numbering_settings(tenant, "purchase_invoice"),
            "purchase_request_numbering": numbering_settings(tenant, "purchase_request"),
            "purchase_return_numbering": numbering_settings(tenant, "purchase_return"),
            "debit_note_numbering": numbering_settings(tenant, "debit_note"),
            "supplier_payment_numbering": numbering_settings(tenant, "supplier_payment"),
        }
    )


@api.patch("/purchasing/settings")
async def update_purchasing_settings(
    payload: PurchasingNumberingUpdate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import apply_numbering_update, numbering_settings

    if (
        payload.purchase_order_numbering is None
        and payload.grn_numbering is None
        and payload.purchase_invoice_numbering is None
        and payload.purchase_request_numbering is None
        and payload.purchase_return_numbering is None
        and payload.debit_note_numbering is None
        and payload.supplier_payment_numbering is None
    ):
        raise HTTPException(status_code=400, detail="No numbering fields to update")
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if payload.purchase_order_numbering is not None:
        apply_numbering_update(
            tenant,
            "purchase_order",
            prefix=payload.purchase_order_numbering.prefix,
            next_number=payload.purchase_order_numbering.next_number,
        )
    if payload.grn_numbering is not None:
        apply_numbering_update(
            tenant,
            "grn",
            prefix=payload.grn_numbering.prefix,
            next_number=payload.grn_numbering.next_number,
        )
    if payload.purchase_invoice_numbering is not None:
        apply_numbering_update(
            tenant,
            "purchase_invoice",
            prefix=payload.purchase_invoice_numbering.prefix,
            next_number=payload.purchase_invoice_numbering.next_number,
        )
    if payload.purchase_request_numbering is not None:
        apply_numbering_update(
            tenant,
            "purchase_request",
            prefix=payload.purchase_request_numbering.prefix,
            next_number=payload.purchase_request_numbering.next_number,
        )
    if payload.purchase_return_numbering is not None:
        apply_numbering_update(
            tenant,
            "purchase_return",
            prefix=payload.purchase_return_numbering.prefix,
            next_number=payload.purchase_return_numbering.next_number,
        )
    if payload.debit_note_numbering is not None:
        apply_numbering_update(
            tenant,
            "debit_note",
            prefix=payload.debit_note_numbering.prefix,
            next_number=payload.debit_note_numbering.next_number,
        )
    if payload.supplier_payment_numbering is not None:
        apply_numbering_update(
            tenant,
            "supplier_payment",
            prefix=payload.supplier_payment_numbering.prefix,
            next_number=payload.supplier_payment_numbering.next_number,
        )
    await db.commit()
    return env(
        {
            "purchase_order_numbering": numbering_settings(tenant, "purchase_order"),
            "grn_numbering": numbering_settings(tenant, "grn"),
            "purchase_invoice_numbering": numbering_settings(tenant, "purchase_invoice"),
            "purchase_request_numbering": numbering_settings(tenant, "purchase_request"),
            "purchase_return_numbering": numbering_settings(tenant, "purchase_return"),
            "debit_note_numbering": numbering_settings(tenant, "debit_note"),
            "supplier_payment_numbering": numbering_settings(tenant, "supplier_payment"),
        },
        "Purchasing document numbering updated",
    )


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
        is_reverse_charge=bool(payload.is_reverse_charge),
        items=[i.model_dump() for i in payload.items],
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await sales_svc.serialize_invoice(db, invoice), "Sales invoice created as draft")


@api.get("/sales/invoices/{invoice_id}")
async def get_sales_invoice(
    invoice_id: UuidIdValue,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    invoice = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, invoice.created_by)
    return env(await sales_svc.serialize_invoice(db, invoice))


@api.get("/sales/invoices/{invoice_id}/print")
async def print_sales_invoice(
    invoice_id: UuidIdValue,
    # omit → tenant print branding default; blank/invalid → 422
    template: Annotated[InvoiceTemplateValue | None, Query()] = None,
    # omit → pdf; blank/invalid → 422 (was `format or "pdf"`)
    format: Annotated[InvoicePrintFormatValue, Query()] = "pdf",
    # omit → branding default receipt paper; blank/invalid → 422 (was silent branding fallback)
    paper: Annotated[ReceiptPaperValue | None, Query()] = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Printable sales invoice: template=a4|thermal, format=pdf|text|json, paper=58mm|80mm (thermal)."""
    from app import invoice_print as invoice_print_svc
    from app.print_branding import print_branding_settings

    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    payload = await invoice_print_svc.build_invoice_print_payload(
        db, tenant_id=claims["tenant_id"], invoice_id=invoice_id
    )
    branding = print_branding_settings(
        await tenants_svc.get_tenant(db, claims["tenant_id"])
    )
    tmpl = (template or branding["default_invoice_template"] or "a4").lower()
    fmt = format
    paper = paper if paper is not None else branding["default_receipt_paper"]
    # Defense in depth: Query Literals reject blank/unknown with 422.
    if tmpl not in {"a4", "thermal"}:
        raise HTTPException(status_code=400, detail="template must be a4 or thermal")
    if fmt not in {"pdf", "text", "json"}:
        raise HTTPException(status_code=400, detail="format must be pdf, text, or json")

    if tmpl == "thermal":
        text = invoice_print_svc.render_invoice_thermal_text(payload, paper=paper)
        if fmt == "json":
            public = {k: v for k, v in payload.items() if k != "logo_key"}
            public["template"] = "thermal"
            public["paper"] = paper
            public["text"] = text
            return env(public)
        if fmt == "text":
            return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
        pdf = invoice_print_svc.to_invoice_thermal_pdf(payload, paper=paper)
        filename = f"invoice_{payload['invoice_number']}_{paper}.pdf".replace("/", "-")
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # A4
    if fmt == "json":
        public = {k: v for k, v in payload.items() if k != "logo_key"}
        public["template"] = "a4"
        public["text"] = invoice_print_svc.render_invoice_thermal_text(payload, paper="80mm")
        return env(public)
    if fmt == "text":
        # Readable plain-text A4-ish dump
        text = invoice_print_svc.render_invoice_thermal_text(payload, paper="80mm")
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
    pdf = invoice_print_svc.to_invoice_a4_pdf(payload)
    filename = f"invoice_{payload['invoice_number']}_a4.pdf".replace("/", "-")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.post("/sales/invoices/{invoice_id}/post")
async def post_sales_invoice(
    invoice_id: UuidIdValue,
    payload: CreditLimitOverrideBody | None = None,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.credit import claims_may_override_credit

    ov = payload or CreditLimitOverrideBody()
    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    invoice = await sales_svc.post_sales_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        invoice_id=invoice_id,
        override_credit_limit=bool(ov.override_credit_limit),
        override_reason=ov.override_reason,
        credit_override_allowed=claims_may_override_credit(claims),
    )
    await webhooks_svc.emit_event(
        db,
        tenant_id=claims["tenant_id"],
        event="sale.created",
        data={
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": money_json(invoice.total_amount or 0),
            "customer_id": invoice.customer_id,
            "status": invoice.status,
        },
    )
    await db.commit()
    data = await sales_svc.serialize_invoice(db, invoice)
    data["credit_limit_overridden"] = bool(getattr(invoice, "credit_limit_overridden", False))
    return env(data, "Invoice posted; stock and AR updated")


@api.post("/sales/invoices/{invoice_id}/send")
async def send_sales_invoice(
    invoice_id: UuidIdValue,
    to: Annotated[EmailStr | None, Query()] = None,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Email invoice. Optional Query `to` ∈ EmailStr; omit → customer email; blank/invalid → 422."""
    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    invoice, delivery = await sales_svc.send_sales_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        invoice_id=invoice_id,
        to=str(to) if to is not None else None,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="sales",
        action="invoice_email",
        entity="sales_invoice",
        entity_id=invoice.id,
        details=delivery,
    )
    await db.commit()
    data = await sales_svc.serialize_invoice(db, invoice)
    data["delivery"] = delivery
    return env(data, f"Invoice emailed to {delivery['to']} ({delivery['mode']})")


@api.post("/sales/invoices/{invoice_id}/cancel")
async def cancel_sales_invoice(
    invoice_id: UuidIdValue,
    payload: SalesInvoiceCancel,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    invoice = await sales_svc.cancel_sales_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        invoice_id=invoice_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await sales_svc.serialize_invoice(db, invoice), "Draft invoice cancelled")


@api.get("/sales/quotations")
async def list_quotations(
    status: Annotated[SalesQuotationStatusValue | None, Query()] = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.sales_docs import QT_MANAGE_STATUSES

    stmt = (
        select(m.SalesQuotation)
        .where(m.SalesQuotation.tenant_id == claims["tenant_id"])
        .order_by(m.SalesQuotation.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesQuotation, claims)
    # Schema SalesQuotationStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in QT_MANAGE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid quotation status '{wanted}'. "
                    f"Allowed: {sorted(QT_MANAGE_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.SalesQuotation.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await sales_docs_svc.serialize_quotation(db, q) for q in rows])


@api.get("/sales/quotations/export")
async def export_sales_quotations_csv(
    status: str | None = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 133 Q1 — sales quotation header CSV (no line dump)."""
    text = await sales_pipeline_export_svc.export_quotations_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, status=status
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="sales_quotations_export.csv"'
        },
    )


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
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_quotation(db, quote), "Quotation created")


@api.get("/sales/quotations/{quotation_id}")
async def get_quotation(
    quotation_id: UuidIdValue,
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
    workspace_svc.assert_record_company(claims, quote)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    company = None
    cid = claims.get("company_id") or getattr(quote, "company_id", None)
    if cid:
        company = await db.get(m.Company, cid)
        if not company or company.tenant_id != claims["tenant_id"]:
            company = None
    customer = await sales_svc.get_customer(db, claims["tenant_id"], quote.customer_id)
    from app.print_branding import tenant_document_brand

    doc_brand = tenant_document_brand(tenant, company)
    tpl = (template or doc_brand.get("invoice_print_template") or "a4").strip().lower()
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
    currency = (company.currency if company and company.currency else None) or tenant.currency or "GHS"
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
    quotation_id: UuidIdValue,
    to: Annotated[EmailStr | None, Query()] = None,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Email quotation. Optional Query `to` ∈ EmailStr; omit → customer email; blank/invalid → 422."""
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
    quote, delivery = await sales_docs_svc.send_quotation(
        db,
        claims["tenant_id"],
        quotation_id,
        to=str(to) if to is not None else None,
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
    quotation_id: UuidIdValue,
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
    quotation_id: UuidIdValue,
    payload: SalesQuotationReject,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
    quote = await sales_docs_svc.reject_quotation(
        db,
        claims["tenant_id"],
        quotation_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_quotation(db, quote), "Quotation rejected")


@api.post("/sales/quotations/{quotation_id}/convert-order")
async def convert_quotation_order(
    quotation_id: UuidIdValue,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.convert_quotation_to_order(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], quotation_id=quotation_id
    )
    await db.commit()
    # Stage 99 T1 — honesty: convert creates draft order; Confirm reserves stock
    return env(
        await sales_docs_svc.serialize_order(db, order),
        "Converted to draft sales order — Confirm required to reserve stock",
    )


@api.post("/sales/quotations/{quotation_id}/convert-invoice")
async def convert_quotation_invoice(
    quotation_id: UuidIdValue,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_quotation(db, claims["tenant_id"], quotation_id)
    assert_record_access(claims, existing.created_by)
    invoice = await sales_docs_svc.convert_quotation_to_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], quotation_id=quotation_id
    )
    await db.commit()
    # Stage 97 S1 — honesty: convert creates draft; Post required before AR recognition
    return env(
        await sales_svc.serialize_invoice(db, invoice),
        "Converted to draft invoice — Post required before AR",
    )


@api.get("/sales/orders")
async def list_sales_orders(
    status: Annotated[SalesOrderStatusValue | None, Query()] = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.sales_docs import SO_MANAGE_STATUSES

    stmt = (
        select(m.SalesOrder)
        .where(m.SalesOrder.tenant_id == claims["tenant_id"])
        .order_by(m.SalesOrder.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesOrder, claims)
    # Schema SalesOrderStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in SO_MANAGE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid sales order status '{wanted}'. "
                    f"Allowed: {sorted(SO_MANAGE_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.SalesOrder.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await sales_docs_svc.serialize_order(db, o) for o in rows])


@api.get("/sales/orders/export")
async def export_sales_orders_csv(
    status: str | None = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 133 O1 — sales order header CSV (no line dump)."""
    text = await sales_pipeline_export_svc.export_orders_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, status=status
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="sales_orders_export.csv"'
        },
    )


@api.post("/sales/orders")
async def create_sales_order(
    payload: SalesOrderCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    if payload.quotation_id:
        quote = await sales_docs_svc.get_quotation(db, claims["tenant_id"], payload.quotation_id)
        assert_record_access(claims, quote.created_by)
        workspace_svc.assert_record_company(claims, quote)
    order = await sales_docs_svc.create_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        customer_id=payload.customer_id,
        quotation_id=payload.quotation_id,
        store_id=payload.store_id,
        delivery_date=reports_svc.parse_date(payload.delivery_date),
        delivery_address=payload.delivery_address,
        discount_amount=payload.discount_amount,
        notes=payload.notes,
        delivery_date=payload.delivery_date,
        delivery_address=payload.delivery_address,
        items=[i.model_dump() for i in payload.items],
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Sales order created")


@api.get("/sales/orders/{order_id}")
async def get_sales_order(
    order_id: UuidIdValue,
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
    workspace_svc.assert_record_company(claims, existing)
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
    order_id: UuidIdValue,
    payload: SalesOrderConfirm = SalesOrderConfirm(),
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.confirm_order(
        db,
        claims["tenant_id"],
        order_id,
        store_id=payload.store_id,
        delivery_date=reports_svc.parse_date(payload.delivery_date),
        delivery_address=payload.delivery_address,
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
    workspace_svc.assert_record_company(claims, existing)
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
    workspace_svc.assert_record_company(claims, existing)
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
    workspace_svc.assert_record_company(claims, existing)
    order = await sales_docs_svc.advance_order_status(
        db,
        tenant_id=claims["tenant_id"],
        order_id=order_id,
        target_status="delivered",
        user_id=claims["sub"],
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order delivered")


@api.post("/sales/orders/{order_id}/process")
async def process_sales_order(
    order_id: UuidIdValue,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.start_processing_order(db, claims["tenant_id"], order_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order processing")


@api.post("/sales/orders/{order_id}/ship")
async def ship_sales_order(
    order_id: UuidIdValue,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.ship_order(db, claims["tenant_id"], order_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order shipped")


@api.post("/sales/orders/{order_id}/deliver")
async def deliver_sales_order(
    order_id: UuidIdValue,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.deliver_order(db, claims["tenant_id"], order_id)
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order delivered")


@api.post("/sales/orders/{order_id}/cancel")
async def cancel_sales_order(
    order_id: UuidIdValue,
    payload: SalesOrderCancel,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_order(db, claims["tenant_id"], order_id)
    assert_record_access(claims, existing.created_by)
    order = await sales_docs_svc.cancel_order(
        db,
        claims["tenant_id"],
        order_id,
        user_id=claims["sub"],
        reason=payload.reason,
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_order(db, order), "Order cancelled")


@api.post("/sales/orders/{order_id}/convert-invoice")
async def convert_order_invoice(
    order_id: UuidIdValue,
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
    status: Annotated[ReturnReportStatusValue | None, Query()] = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.reports import RETURN_REPORT_STATUSES

    stmt = (
        select(m.SalesReturn)
        .where(m.SalesReturn.tenant_id == claims["tenant_id"])
        .order_by(m.SalesReturn.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.SalesReturn, claims)
    # Schema ReturnReportStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in RETURN_REPORT_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid return status '{wanted}'. "
                    f"Allowed: {sorted(RETURN_REPORT_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.SalesReturn.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await sales_docs_svc.serialize_return(db, r) for r in rows])


@api.get("/sales/returns/export")
async def export_sales_returns_csv(
    status: str | None = None,
    claims=Depends(require_permission("sales", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 133 R1 — sales return header CSV (no line dump)."""
    text = await sales_pipeline_export_svc.export_returns_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, status=status
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="sales_returns_export.csv"'
        },
    )


@api.post("/sales/returns")
async def create_sales_return(
    payload: SalesReturnCreate,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    invoice = await sales_svc.get_invoice(db, claims["tenant_id"], payload.sales_invoice_id)
    assert_record_access(claims, invoice.created_by)
    workspace_svc.assert_record_company(claims, invoice)
    ret = await sales_docs_svc.create_return(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        sales_invoice_id=payload.sales_invoice_id,
        reason=payload.reason,
        restock=payload.restock,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_return(db, ret), "Sales return created as draft")


@api.get("/sales/returns/{return_id}")
async def get_sales_return(
    return_id: UuidIdValue,
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
    workspace_svc.assert_record_company(claims, ret)
    if ret.status != "posted" or not ret.credit_note_number:
        raise HTTPException(
            status_code=409,
            detail="Credit note is available after the sales return is posted",
        )
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    company = None
    cid = claims.get("company_id") or getattr(ret, "company_id", None)
    if cid:
        company = await db.get(m.Company, cid)
        if not company or company.tenant_id != claims["tenant_id"]:
            company = None
    customer = await sales_svc.get_customer(db, claims["tenant_id"], ret.customer_id)
    invoice = await sales_svc.get_invoice(db, claims["tenant_id"], ret.sales_invoice_id)
    from app.print_branding import tenant_document_brand

    doc_brand = tenant_document_brand(tenant, company)
    tpl = (template or doc_brand.get("invoice_print_template") or "a4").strip().lower()
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
    currency = (company.currency if company and company.currency else None) or tenant.currency or "GHS"
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
    return_id: UuidIdValue,
    payload: SalesReturnPost = SalesReturnPost(),
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_return(db, claims["tenant_id"], return_id)
    assert_record_access(claims, existing.created_by)
    ret = await sales_docs_svc.post_return(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        return_id=return_id,
        settlement_method=payload.settlement_method,
        payment_method=payload.payment_method,
        liquid_account_id=payload.liquid_account_id,
    )
    await db.commit()
    return env(
        await sales_docs_svc.serialize_return(db, ret),
        f"Return posted ({ret.credit_note_number}); stock/AR/journal updated",
    )


@api.post("/sales/returns/{return_id}/cancel")
async def cancel_sales_return(
    return_id: UuidIdValue,
    payload: SalesReturnCancel,
    claims=Depends(require_permission("sales", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await sales_docs_svc.get_return(db, claims["tenant_id"], return_id)
    assert_record_access(claims, existing.created_by)
    ret = await sales_docs_svc.cancel_return(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        return_id=return_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await sales_docs_svc.serialize_return(db, ret), "Draft sales return cancelled")


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
    party = await customers_svc.get_customer(db, claims["tenant_id"], payload.customer_id)
    workspace_svc.assert_record_company(claims, party)
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
        cheque_date=reports_svc.parse_date(payload.cheque_date),
        apply_early_discount=payload.apply_early_discount,
        liquid_account_id=payload.liquid_account_id,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(
        {
            "id": payment.id,
            "payment_number": payment.payment_number,
            "amount": money_json(payment.amount),
            "sales_invoice_id": payment.sales_invoice_id,
            "currency": getattr(payment, "currency", None) or "",
            "exchange_rate": money_json(getattr(payment, "exchange_rate", None), default=1),
            "fx_gain_loss": money_json(getattr(payment, "fx_gain_loss", 0) or 0),
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
    status: Annotated[PurchaseRequestStatusValue | None, Query()] = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.purchase_requests import PR_MANAGE_STATUSES

    stmt = (
        select(m.PurchaseRequest)
        .where(m.PurchaseRequest.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseRequest.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseRequest, claims)
    # Schema PurchaseRequestStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in PR_MANAGE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid purchase request status '{wanted}'. "
                    f"Allowed: {sorted(PR_MANAGE_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.PurchaseRequest.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await purchase_requests_svc.serialize_request(db, r) for r in rows])


@api.get("/purchasing/requests/settings")
async def purchase_request_settings(
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await purchase_requests_svc.get_approval_settings(db, claims["tenant_id"]))


@api.patch("/purchasing/requests/settings")
async def update_purchase_request_settings(
    payload: PurchaseApprovalSettingsUpdate,
    claims=Depends(require_permission("purchasing", "approve")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    data = await purchase_requests_svc.update_approval_settings(
        db,
        tenant,
        levels=[lvl.model_dump() for lvl in payload.levels],
    )
    await db.commit()
    return env(data, "Purchase approval matrix updated")


@api.get("/purchasing/suggestions/low-stock")
async def list_low_stock_suggestions(
    # Optional location ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach store/warehouse lookup).
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    include_open: bool = False,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await purchase_suggestions_svc.list_low_stock_suggestions(
            db,
            claims["tenant_id"],
            store_id=store_id,
            warehouse_id=warehouse_id,
            include_open=include_open,
        )
    )


@api.post("/purchasing/requests/from-low-stock")
async def create_purchase_requests_from_low_stock(
    payload: LowStockSuggestionsCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    result = await purchase_suggestions_svc.create_requests_from_low_stock(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        lines=[ln.model_dump() for ln in payload.lines],
        notes=payload.notes,
        department=payload.department,
        include_open=payload.include_open,
    )
    await db.commit()
    n = result["created_count"]
    return env(result, f"Created {n} draft purchase request(s) from low-stock suggestions")


@api.post("/purchasing/requests")
async def create_purchase_request(
    payload: PurchaseRequestCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await purchase_requests_svc.create_request(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        preferred_supplier_id=payload.preferred_supplier_id,
        warehouse_id=payload.warehouse_id,
        required_date=reports_svc.parse_date(payload.required_date),
        department=payload.department,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    await db.commit()
    return env(await purchase_requests_svc.serialize_request(db, row), "Purchase request created")


@api.get("/purchasing/requests/{request_id}")
async def get_purchase_request(
    request_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await purchase_requests_svc.get_request(db, claims["tenant_id"], request_id)
    assert_record_access(claims, row.created_by)
    return env(await purchase_requests_svc.serialize_request(db, row))


@api.post("/purchasing/requests/{request_id}/submit")
async def submit_purchase_request(
    request_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchase_requests_svc.get_request(db, claims["tenant_id"], request_id)
    assert_record_access(claims, existing.created_by)
    row = await purchase_requests_svc.submit_request(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], request_id=request_id
    )
    await db.commit()
    return env(await purchase_requests_svc.serialize_request(db, row), "Purchase request submitted")


@api.post("/purchasing/requests/{request_id}/approve")
async def approve_purchase_request(
    request_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "approve")),
    db: AsyncSession = Depends(get_db),
):
    row = await purchase_requests_svc.approve_request(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        request_id=request_id,
        actor_role=claims.get("role"),
    )
    await db.commit()
    data = await purchase_requests_svc.serialize_request(db, row)
    if row.status == "pending":
        msg = (
            f"Level {int(row.approval_step) - 1} approved; "
            f"awaiting level {row.approval_step}"
        )
    else:
        msg = "Purchase request approved"
    return env(data, msg)


@api.post("/purchasing/requests/{request_id}/reject")
async def reject_purchase_request(
    request_id: UuidIdValue,
    payload: PurchaseRequestReject,
    claims=Depends(require_permission("purchasing", "approve")),
    db: AsyncSession = Depends(get_db),
):
    row = await purchase_requests_svc.reject_request(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        request_id=request_id,
        reason=payload.reason,
        actor_role=claims.get("role"),
    )
    await db.commit()
    return env(await purchase_requests_svc.serialize_request(db, row), "Purchase request rejected")


@api.post("/purchasing/requests/{request_id}/convert")
async def convert_purchase_request(
    request_id: UuidIdValue,
    payload: PurchaseRequestConvert | None = None,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchase_requests_svc.get_request(db, claims["tenant_id"], request_id)
    assert_record_access(claims, existing.created_by)
    row, po = await purchase_requests_svc.convert_to_po(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        request_id=request_id,
        supplier_id=(payload.supplier_id if payload else None),
    )
    await db.commit()
    data = await purchase_requests_svc.serialize_request(db, row)
    data["purchase_order"] = await purchasing_svc.serialize_po(db, po)
    return env(data, "Purchase request converted to draft PO")


@api.get("/purchasing/orders")
async def list_purchase_orders(
    status: Annotated[PurchaseOrderStatusValue | None, Query()] = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.purchasing import PO_MANAGE_STATUSES

    stmt = (
        select(m.PurchaseOrder)
        .where(m.PurchaseOrder.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseOrder.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseOrder, claims)
    # Schema PurchaseOrderStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in PO_MANAGE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid purchase order status '{wanted}'. "
                    f"Allowed: {sorted(PO_MANAGE_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.PurchaseOrder.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await purchasing_svc.serialize_po(db, po) for po in rows])


@api.get("/purchasing/orders/export")
async def export_purchase_orders_csv(
    status: str | None = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 134 O1 — purchase order header CSV (no line dump)."""
    text = await purchasing_pipeline_export_svc.export_purchase_orders_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, status=status
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="purchase_orders_export.csv"'
        },
    )


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
        delivery_address=payload.delivery_address,
        items=[i.model_dump() for i in payload.items],
        company_id=claims.get("company_id"),
    )
    await webhooks_svc.emit_event(
        db,
        tenant_id=claims["tenant_id"],
        event="purchase.order.created",
        data={
            "po_id": po.id,
            "po_number": po.po_number,
            "supplier_id": po.supplier_id,
            "warehouse_id": po.warehouse_id,
            "total_amount": money_json(getattr(po, "total_amount", 0) or 0),
            "status": po.status,
        },
    )
    await db.commit()
    return env(await purchasing_svc.serialize_po(db, po), "Purchase order created")


@api.get("/purchasing/orders/{po_id}")
async def get_purchase_order(
    po_id: UuidIdValue,
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
    workspace_svc.assert_record_company(claims, existing)
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
    workspace_svc.assert_record_company(claims, existing)
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
    workspace_svc.assert_record_company(claims, po)
    assert_record_access(claims, po.created_by)
    rows = await purchasing_svc.list_po_amendments(db, claims["tenant_id"], po_id)
    return env([purchasing_svc.serialize_po_amendment(r) for r in rows])


@api.get("/purchasing/orders/{po_id}/amendments/export")
async def export_purchase_order_amendments(
    po_id: str,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 154 A1 — purchase order amendment history CSV."""
    text = await purchasing_pipeline_export_svc.export_po_amendments_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, po_id=po_id
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="po_{po_id}_amendments_export.csv"'
        },
    )


@api.post("/purchasing/orders/{po_id}/send")
async def send_purchase_order(
    po_id: UuidIdValue,
    to: Annotated[EmailStr | None, Query()] = None,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Email PO. Optional Query `to` ∈ EmailStr; omit → supplier email; blank/invalid → 422."""
    existing = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, existing.created_by)
    po, delivery = await purchasing_svc.send_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        to=str(to) if to is not None else None,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="po_email",
        entity="purchase_order",
        entity_id=po.id,
        details=delivery,
    )
    await db.commit()
    data = await purchasing_svc.serialize_po(db, po)
    data["delivery"] = delivery
    return env(data, f"Purchase order emailed to {delivery['to']} ({delivery['mode']})")


@api.post("/purchasing/orders/{po_id}/amend")
async def amend_purchase_order(
    po_id: UuidIdValue,
    payload: PurchaseOrderAmend,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, existing.created_by)
    items = [i.model_dump() for i in payload.items] if payload.items is not None else None
    po, amendment, delivery = await purchasing_svc.amend_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        items=items,
        notes=payload.notes,
        delivery_address=payload.delivery_address,
        due_date=reports_svc.parse_date(payload.due_date),
        clear_due_date=payload.clear_due_date,
        reason=payload.reason,
        notify_supplier=payload.notify_supplier,
        notify_to=str(payload.to) if payload.to is not None else None,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="purchasing",
        action="po_amend",
        entity="purchase_order",
        entity_id=po.id,
        details={
            "revision_no": amendment.revision_no,
            "reason": amendment.reason,
            "notified_supplier": amendment.notified_supplier,
            "delivery": delivery,
        },
    )
    await db.commit()
    data = await purchasing_svc.serialize_po(db, po)
    data["amendment"] = purchasing_svc.serialize_po_amendment(amendment)
    if delivery:
        data["delivery"] = delivery
    msg = f"Purchase order amended (rev.{amendment.revision_no})"
    if delivery:
        msg += f"; emailed {delivery['to']} ({delivery['mode']})"
    return env(data, msg)


@api.get("/purchasing/orders/{po_id}/amendments")
async def list_purchase_order_amendments(
    po_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    po = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, po.created_by)
    rows = await purchasing_svc.list_po_amendments(db, claims["tenant_id"], po_id)
    return env([purchasing_svc.serialize_po_amendment(r) for r in rows])


@api.post("/purchasing/orders/{po_id}/cancel")
async def cancel_purchase_order(
    po_id: UuidIdValue,
    payload: PurchaseOrderCancel,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_po(db, claims["tenant_id"], po_id)
    assert_record_access(claims, existing.created_by)
    po = await purchasing_svc.cancel_purchase_order(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        po_id=po_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await purchasing_svc.serialize_po(db, po), "Purchase order cancelled")


@api.get("/purchasing/grn")
async def list_grns(
    status: str | None = None,
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


@api.get("/purchasing/grn/export")
async def export_grns_csv(
    status: str | None = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 134 G1 — GRN header CSV (no line dump)."""
    text = await purchasing_pipeline_export_svc.export_grns_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, status=status
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="grns_export.csv"'},
    )


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
        items=[
            {
                **i.model_dump(),
                "manufacturing_date": reports_svc.parse_date(i.manufacturing_date),
                "expiry_date": reports_svc.parse_date(i.expiry_date),
            }
            for i in payload.items
        ],
    )
    await webhooks_svc.emit_event(
        db,
        tenant_id=claims["tenant_id"],
        event="purchase.grn.received",
        data={
            "grn_id": grn.id,
            "grn_number": grn.grn_number,
            "purchase_order_id": grn.purchase_order_id,
            "supplier_id": grn.supplier_id,
            "warehouse_id": grn.warehouse_id,
            "status": grn.status,
        },
    )
    await db.commit()
    return env(await purchasing_svc.serialize_grn(db, grn), "GRN posted and stock updated")


@api.get("/purchasing/grn/{grn_id}")
async def get_grn(
    grn_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    grn = await purchasing_svc.get_grn(db, claims["tenant_id"], grn_id)
    assert_record_access(claims, grn.created_by)
    return env(await purchasing_svc.serialize_grn(db, grn))


@api.get("/purchasing/returns")
async def list_purchase_returns(
    status: Annotated[ReturnReportStatusValue | None, Query()] = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.reports import RETURN_REPORT_STATUSES

    stmt = (
        select(m.PurchaseReturn)
        .where(m.PurchaseReturn.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseReturn.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseReturn, claims)
    # Schema ReturnReportStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in RETURN_REPORT_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid return status '{wanted}'. "
                    f"Allowed: {sorted(RETURN_REPORT_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.PurchaseReturn.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await purchasing_svc.serialize_purchase_return(db, r) for r in rows])


@api.get("/purchasing/returns/export")
async def export_purchase_returns_csv(
    status: str | None = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 135 R1 — purchase return header CSV (no line dump)."""
    text = await purchasing_pipeline_export_svc.export_purchase_returns_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, status=status
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="purchase_returns_export.csv"'
        },
    )


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
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_return(db, ret), "Purchase return created as draft")


@api.get("/purchasing/returns/{return_id}")
async def get_purchase_return(
    return_id: UuidIdValue,
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
    workspace_svc.assert_record_company(claims, ret)
    if ret.status != "posted" or not ret.debit_note_number:
        raise HTTPException(
            status_code=409,
            detail="Debit note is available after the purchase return is posted",
        )
    supplier = await purchasing_svc.get_supplier(db, claims["tenant_id"], ret.supplier_id)
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    company = None
    cid = claims.get("company_id") or getattr(ret, "company_id", None)
    if cid:
        company = await db.get(m.Company, cid)
        if not company or company.tenant_id != claims["tenant_id"]:
            company = None
    from app.print_branding import tenant_document_brand

    doc_brand = tenant_document_brand(tenant, company)
    po = await purchasing_svc.get_po(db, claims["tenant_id"], ret.purchase_order_id)
    grn = await purchasing_svc.get_grn(db, claims["tenant_id"], ret.goods_receipt_id)
    data = await purchasing_svc.serialize_purchase_return(db, ret)
    text = purchasing_svc.render_debit_note_text(
        data,
        supplier_name=supplier.name,
        company_name=doc_brand["company_name"],
        po_number=po.po_number,
        grn_number=grn.grn_number,
    )
    return env(
        {
            "return": data,
            "text": text,
            "supplier_name": supplier.name,
            "company_name": doc_brand["company_name"],
            "po_number": po.po_number,
            "grn_number": grn.grn_number,
        }
    )


@api.post("/purchasing/returns/{return_id}/post")
async def post_purchase_return(
    return_id: UuidIdValue,
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


@api.post("/purchasing/returns/{return_id}/cancel")
async def cancel_purchase_return(
    return_id: UuidIdValue,
    payload: PurchaseReturnCancel,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_purchase_return(db, claims["tenant_id"], return_id)
    assert_record_access(claims, existing.created_by)
    ret = await purchasing_svc.cancel_purchase_return(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        return_id=return_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(
        await purchasing_svc.serialize_purchase_return(db, ret),
        "Draft purchase return cancelled",
    )


@api.get("/purchasing/invoices")
async def list_purchase_invoices(
    status: Annotated[PurchaseInvoiceStatusValue | None, Query()] = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.purchasing import PI_MANAGE_STATUSES

    stmt = (
        select(m.PurchaseInvoice)
        .where(m.PurchaseInvoice.tenant_id == claims["tenant_id"])
        .order_by(m.PurchaseInvoice.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.PurchaseInvoice, claims)
    # Schema PurchaseInvoiceStatusValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in PI_MANAGE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid purchase invoice status '{wanted}'. "
                    f"Allowed: {sorted(PI_MANAGE_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.PurchaseInvoice.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await purchasing_svc.serialize_purchase_invoice(db, r) for r in rows])


@api.get("/purchasing/invoices/export")
async def export_purchase_invoices_csv(
    status: str | None = None,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 132 P1 — purchase invoice header CSV (no line dump)."""
    text = await commerce_docs_export_svc.export_purchase_invoices_csv(
        db, tenant_id=claims["tenant_id"], claims=claims, status=status
    )
    await db.commit()
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="purchase_invoices_export.csv"'
        },
    )


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
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Purchase invoice drafted")


@api.get("/purchasing/invoices/{invoice_id}")
async def get_purchase_invoice(
    invoice_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "read")),
    db: AsyncSession = Depends(get_db),
):
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, inv.created_by)
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv))


@api.patch("/purchasing/invoices/{invoice_id}")
async def patch_purchase_invoice(
    invoice_id: UuidIdValue,
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
        invoice_date=reports_svc.parse_date(payload.invoice_date),
        due_date=reports_svc.parse_date(payload.due_date),
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
    invoice_id: UuidIdValue,
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


@api.post("/purchasing/invoices/{invoice_id}/ocr-apply")
async def purchase_invoice_ocr_apply(
    invoice_id: str,
    payload: PurchaseInvoiceOcrApply,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 10 A1 — apply human-reviewed OCR fields to a draft purchase invoice."""
    from app import purchase_ocr as purchase_ocr_svc

    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm must be true to apply OCR suggestions",
        )
    existing = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    workspace_svc.assert_record_company(claims, existing)
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
        action="purchase_invoice_ocr_apply",
        entity="purchase_invoice",
        entity_id=inv.id,
        details={
            "invoice_number": inv.invoice_number,
            "fields": [
                k
                for k, v in {
                    "supplier_invoice_number": payload.supplier_invoice_number,
                    "notes": payload.notes,
                    "invoice_date": payload.invoice_date,
                    "due_date": payload.due_date,
                }.items()
                if v is not None
            ],
        },
    )
    await db.commit()
    return env(
        await purchasing_svc.serialize_purchase_invoice(db, inv),
        "OCR suggestions applied to draft invoice",
    )


@api.post("/purchasing/invoices/{invoice_id}/approve")
async def approve_purchase_invoice(
    invoice_id: UuidIdValue,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    workspace_svc.assert_record_company(claims, existing)
    inv = await purchasing_svc.approve_purchase_invoice(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], invoice_id=invoice_id
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Purchase invoice approved")


@api.post("/purchasing/invoices/{invoice_id}/cancel")
async def cancel_purchase_invoice(
    invoice_id: UuidIdValue,
    payload: PurchaseInvoiceCancel,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    assert_record_access(claims, existing.created_by)
    inv = await purchasing_svc.cancel_purchase_invoice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        invoice_id=invoice_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await purchasing_svc.serialize_purchase_invoice(db, inv), "Purchase invoice cancelled")


@api.post("/purchasing/invoices/{invoice_id}/attachment")
async def upload_purchase_invoice_attachment(
    invoice_id: UuidIdValue,
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
    invoice_id: UuidIdValue,
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
    invoice_id: UuidIdValue,
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


@api.get("/pos/stores")
async def pos_stores(
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Active stores available for POS shift open (cashiers may lack stores:read)."""
    from app import store_access as store_access_svc

    rows = (
        await db.execute(
            select(m.Store)
            .where(
                m.Store.tenant_id == claims["tenant_id"],
                m.Store.is_active == True,  # noqa: E712
            )
            .order_by(m.Store.name.asc())
        )
    ).scalars().all()
    rows = await store_access_svc.filter_stores_for_user(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], stores=list(rows)
    )
    return env(
        [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "address": s.address,
                "phone": s.phone,
            }
            for s in rows
        ]
    )


@api.post("/pos/sessions/open")
async def pos_open_session(
    payload: PosSessionOpen,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import store_access as store_access_svc

    await store_access_svc.assert_store_access(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        store_id=payload.store_id,
    )
    session = await pos_svc.open_session(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        store_id=payload.store_id,
        opening_cash=payload.opening_cash,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await pos_svc.serialize_session(db, session), "POS shift opened")


@api.get("/pos/sessions/current")
async def pos_current_session(
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    session = await pos_svc.get_open_session_for_user(
        db, claims["tenant_id"], claims["sub"], company_id=claims.get("company_id")
    )
    if not session:
        return env(None, "No open POS shift")
    return env(await pos_svc.serialize_session(db, session))


@api.get("/pos/sessions")
async def pos_list_sessions(
    status: Annotated[PosSessionStatusFilterValue | None, Query()] = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    # Schema PosSessionStatusFilterValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all). Runtime statuses: open|closed.
    stmt = (
        select(m.PosSession)
        .where(m.PosSession.tenant_id == claims["tenant_id"])
        .order_by(m.PosSession.opened_at.desc())
        .limit(50)
    )
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in {"open", "closed"}:
            raise HTTPException(
                status_code=422,
                detail="status must be open or closed",
            )
        else:
            stmt = stmt.where(m.PosSession.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await pos_svc.serialize_session(db, s) for s in rows])


@api.get("/pos/sessions/export")
async def pos_sessions_export(
    status: str | None = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 130 P1 — POS session inventory CSV."""
    status_n = (status or "").strip().lower() or None
    if status_n and status_n not in {"open", "closed"}:
        raise HTTPException(status_code=400, detail="status must be open or closed")
    text = await ops_lifecycle_export_svc.export_pos_sessions_csv(
        db,
        tenant_id=claims["tenant_id"],
        status=status_n,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="pos_sessions_export.csv"'
        },
    )


@api.post("/pos/sessions/{session_id}/close")
async def pos_close_session(
    session_id: UuidIdValue,
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
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await pos_svc.serialize_session(db, session), "POS shift closed")


@api.get("/pos/sessions/{session_id}/drawer")
async def pos_session_drawer(
    session_id: UuidIdValue,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    session = await pos_svc.get_session(
        db, claims["tenant_id"], session_id, company_id=claims.get("company_id")
    )
    summary = await pos_svc.drawer_summary(session)
    cfg = await cash_drawer_svc.resolve_config(
        db, tenant_id=claims["tenant_id"], store_id=session.store_id
    )
    return env({**summary, "hardware": cfg, "kick_base64": cash_drawer_svc.kick_base64()})


@api.post("/pos/sessions/{session_id}/drawer/open")
async def pos_open_cash_drawer(
    session_id: UuidIdValue,
    payload: PosDrawerOpen,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    session = await pos_svc.get_session(
        db, claims["tenant_id"], session_id, company_id=claims.get("company_id")
    )
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
        reason=payload.reason,
        user_id=claims.get("sub"),
        require_specific_reason=True,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="pos",
        action="drawer_open",
        entity="pos_session",
        entity_id=session.id,
        details={"reason": result.get("reason") or payload.reason, "result": result},
    )
    await db.commit()
    return env(result, result.get("message") or "Drawer command issued")


@api.get("/pos/sessions/{session_id}/report")
async def pos_session_report(
    session_id: UuidIdValue,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    session = await pos_svc.get_session(
        db, claims["tenant_id"], session_id, company_id=claims.get("company_id")
    )
    return env(await pos_svc.shift_report(db, session))


@api.get("/pos/settings")
async def pos_settings(
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import numbering_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(
        {
            "pos_sale_numbering": numbering_settings(tenant, "pos_sale"),
            "pos_session_numbering": numbering_settings(tenant, "pos_session"),
        }
    )


@api.patch("/pos/settings")
async def update_pos_settings(
    payload: PosSettingsUpdate,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import apply_numbering_update, numbering_settings

    if payload.pos_sale_numbering is None and payload.pos_session_numbering is None:
        raise HTTPException(status_code=400, detail="No numbering fields to update")
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if payload.pos_sale_numbering is not None:
        apply_numbering_update(
            tenant,
            "pos_sale",
            prefix=payload.pos_sale_numbering.prefix,
            next_number=payload.pos_sale_numbering.next_number,
        )
    if payload.pos_session_numbering is not None:
        apply_numbering_update(
            tenant,
            "pos_session",
            prefix=payload.pos_session_numbering.prefix,
            next_number=payload.pos_session_numbering.next_number,
        )
    await db.commit()
    return env(
        {
            "pos_sale_numbering": numbering_settings(tenant, "pos_sale"),
            "pos_session_numbering": numbering_settings(tenant, "pos_session"),
        },
        "POS document numbering updated",
    )


def _serialize_pos_device(row: m.PosDevice) -> dict:
    return {
        "id": row.id,
        "device_id": row.device_id,
        "label": row.label,
        "store_id": row.store_id,
        "user_id": row.user_id,
        "app_version": row.app_version,
        "user_agent": row.user_agent,
        "pending_queue_count": int(row.pending_queue_count or 0),
        "last_seen_at": row.last_seen_at.isoformat() + "Z" if row.last_seen_at else None,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
    }


@api.post("/pos/devices/heartbeat")
async def pos_device_heartbeat(
    payload: PosDeviceHeartbeat,
    request: Request,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Upsert POS terminal last-seen (application monitoring only; not MDM)."""
    now = datetime.utcnow()
    row = (
        await db.execute(
            select(m.PosDevice).where(
                m.PosDevice.tenant_id == claims["tenant_id"],
                m.PosDevice.device_id == payload.device_id,
            )
        )
    ).scalar_one_or_none()
    ua = (request.headers.get("user-agent") or "")[:300] or None
    if row is None:
        row = m.PosDevice(
            tenant_id=claims["tenant_id"],
            device_id=payload.device_id,
            label=(payload.label or None),
            store_id=payload.store_id,
            user_id=claims.get("sub"),
            app_version=payload.app_version,
            user_agent=ua,
            pending_queue_count=payload.pending_queue_count,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.label = payload.label if payload.label is not None else row.label
        if payload.store_id is not None:
            row.store_id = payload.store_id
        row.user_id = claims.get("sub") or row.user_id
        if payload.app_version is not None:
            row.app_version = payload.app_version
        row.user_agent = ua or row.user_agent
        row.pending_queue_count = payload.pending_queue_count
        row.last_seen_at = now
        row.updated_at = now
    await db.commit()
    await db.refresh(row)
    return env(_serialize_pos_device(row), "Device heartbeat recorded")


@api.get("/pos/devices")
async def list_pos_devices(
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List POS terminals by last-seen (managers/admins with pos:read)."""
    rows = (
        await db.execute(
            select(m.PosDevice)
            .where(m.PosDevice.tenant_id == claims["tenant_id"])
            .order_by(m.PosDevice.last_seen_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return env([_serialize_pos_device(r) for r in rows])


@api.post("/pos/sales")
async def pos_sale(
    payload: PosSaleCreate,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    # Idempotent offline/retry: same client_request_id → original sale, never a duplicate.
    client_request_id = (payload.client_request_id or "").strip() or None
    if client_request_id:
        existing = (
            await db.execute(
                select(m.Transaction).where(
                    m.Transaction.tenant_id == claims["tenant_id"],
                    m.Transaction.client_request_id == client_request_id,
                    m.Transaction.tx_type == "pos_sale",
                )
            )
        ).scalar_one_or_none()
        if existing:
            return env(
                {
                    "id": existing.id,
                    "reference": existing.reference,
                    "total": money_json(existing.total or 0),
                    "status": existing.status,
                    "idempotent_replay": True,
                    "client_request_id": client_request_id,
                },
                "POS sale already recorded",
            )

    session = await pos_svc.require_open_session(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        session_id=payload.session_id,
    )
    items = [i.model_dump() for i in payload.items]
    from app.tax import resolve_product_tax
    from app.catalog import resolve_sale_line

    subtotal = 0.0
    tax_total = 0.0
    line_discounts = 0.0
    priced_items = []
    for item in items:
        product, variant, unit_price = await resolve_sale_line(
            db,
            claims["tenant_id"],
            item,
            customer_id=payload.party_id,
        )
        spec = await resolve_product_tax(db, claims["tenant_id"], product)
        line_discount = money_json(round(money_json(item.get("discount") or 0), 2))
        if line_discount < 0:
            raise HTTPException(status_code=400, detail="Line discount must be >= 0")
        gross_before_discount = money_json(round(
            money_json(item["quantity"]) * money_json(unit_price), 2
        ))
        if line_discount <= 0:
            try:
                from app import fmcg as fmcg_svc
                from app import packages as packages_svc
                from app import tenants as tenants_svc

                tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
                if packages_svc.module_allowed(tenant, "fmcg"):
                    scheme_disc, _meta = await fmcg_svc.best_line_scheme_discount(
                        db,
                        tenant_id=claims["tenant_id"],
                        product_id=product.id,
                        line_qty=float(item["quantity"]),
                        line_amount=float(gross_before_discount),
                    )
                    if scheme_disc > 0:
                        line_discount = money_json(min(scheme_disc, gross_before_discount))
            except Exception:
                pass
        if line_discount > gross_before_discount + 1e-9:
            raise HTTPException(status_code=400, detail="Line discount exceeds line amount")
        taxable_base = money_json(round(gross_before_discount - line_discount, 2))
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
                "tax_supply_class": spec.supply_class,
                "line_subtotal": line_sub,
                "line_tax": 0.0 if spec.is_reverse_charge else line_tax,
                "line_total": line_gross,
                "is_reverse_charge": spec.is_reverse_charge,
            }
        )
    cart_discount = money_json(round(money_json(payload.discount_amount or 0), 2))
    if cart_discount < 0:
        raise HTTPException(status_code=400, detail="discount_amount must be >= 0")
    max_cart_discount = money_json(round(subtotal + tax_total, 2))
    if cart_discount > max_cart_discount + 1e-9:
        raise HTTPException(status_code=400, detail="Cart discount exceeds sale total")
    total = money_json(round(subtotal + tax_total - cart_discount, 2))

    payments = pos_svc.resolve_sale_payments(
        total=total,
        payment_method=payload.payment_method,
        payments=[p.model_dump() for p in payload.payments] if payload.payments else None,
    )
    payment_method = pos_svc.primary_payment_method(payments)
    credit_amount = pos_svc.credit_portion(payments)
    if credit_amount > 0 and not payload.party_id:
        raise HTTPException(
            status_code=400,
            detail="Select a customer for credit sales",
        )

    party = None
    # OpenAPI PosCustomerNameValue → 422; service defense-in-depth → 400.
    from app.honesty import optional_honest_narrative

    customer_name = optional_honest_narrative(
        payload.customer_name, label="POS customer name", max_length=180
    )
    if payload.party_id:
        from app.sales import require_active_customer

        party = await require_active_customer(db, claims["tenant_id"], payload.party_id)
        if not customer_name:
            customer_name = party.name

    pos_override_info = None
    if party is not None and credit_amount > 0:
        from app.credit import claims_may_override_credit, enforce_customer_credit_limit

        pos_override_info = enforce_customer_credit_limit(
            party,
            amount=money_json(credit_amount),
            override=bool(payload.override_credit_limit),
            override_allowed=claims_may_override_credit(claims),
            override_reason=payload.override_reason,
            extra={"source": "pos_sale"},
        )

    ref = await pos_svc.next_pos_sale_number(db, claims["tenant_id"])
    body = payload.model_dump()
    body.pop("items", None)
    body.pop("session_id", None)
    body.pop("payment_method", None)
    body.pop("payments", None)
    body.pop("customer_name", None)
    body.pop("discount_amount", None)
    body.pop("override_credit_limit", None)
    body.pop("override_reason", None)
    body.pop("client_request_id", None)
    body["payload"] = {
        "items": priced_items,
        "payment_method": payment_method,
        "payments": payments,
        "session_id": session.id,
        "customer_name": customer_name,
        "discount_amount": cart_discount,
        "line_discounts": money_json(round(line_discounts, 2)),
        "client_request_id": client_request_id,
    }
    tx = m.Transaction(
        tenant_id=claims["tenant_id"],
        tx_type="pos_sale",
        reference=ref,
        party_id=payload.party_id,
        session_id=session.id,
        client_request_id=client_request_id,
        subtotal=money_json(round(subtotal, 2)),
        tax=money_json(round(tax_total, 2)),
        total=money_json(total),
        # Schema Literal["completed"] already rejects blank/unknown with 422.
        status=payload.status,
        payload=body["payload"],
    )
    db.add(tx)
    await db.flush()
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
            party.balance = money_json(party.balance or 0) + money_json(credit_amount)

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
    if pos_override_info:
        db.add(
            m.AuditLog(
                tenant_id=claims["tenant_id"],
                user_id=claims["sub"],
                action="credit_limit_override",
                entity="customer",
                entity_id=pos_override_info["customer_id"],
                details={
                    **pos_override_info,
                    "source": "pos_sale",
                    "transaction_id": tx.id,
                    "reference": ref,
                },
            )
        )
    await webhooks_svc.emit_event(
        db,
        tenant_id=claims["tenant_id"],
        event="sale.created",
        data={
            "sale_id": tx.id,
            "reference": ref,
            "amount": money_json(tx.total or 0),
            "customer_id": payload.party_id,
            "payment_method": payment_method,
            "status": tx.status,
            "source": "pos",
            "session_id": session.id,
            "credit_amount": money_json(credit_amount or 0),
        },
    )
    # Fully settled at till (no on-account credit tender) → also emit sale.paid.
    if money_json(credit_amount or 0) <= 0:
        await webhooks_svc.emit_event(
            db,
            tenant_id=claims["tenant_id"],
            event="sale.paid",
            data={
                "sale_id": tx.id,
                "reference": ref,
                "amount": money_json(tx.total or 0),
                "customer_id": payload.party_id,
                "payment_method": payment_method,
                "payments": [
                    {
                        "payment_method": p.get("payment_method"),
                        "amount": money_json(p.get("amount") or 0),
                    }
                    for p in payments
                ],
                "source": "pos",
            },
        )
    await db.commit()
    payload_out = {
        "id": tx.id,
        "reference": ref,
        "session_id": session.id,
        "subtotal": money_json(tx.subtotal),
        "tax": money_json(tx.tax),
        "total": money_json(tx.total),
        "discount_amount": money_json(cart_discount),
        "line_discounts": money_json(round(line_discounts, 2)),
        "payment_method": payment_method,
        "payments": [pos_svc.serialize_payment(p) for p in payment_rows],
        "customer_name": customer_name,
        "party_id": payload.party_id,
        "credit_limit_overridden": bool(pos_override_info),
        "client_request_id": client_request_id,
        "idempotent_replay": False,
    }
    if drawer is not None:
        payload_out["drawer"] = drawer
    return env(payload_out, "POS sale recorded")


@api.get("/pos/products/search")
async def pos_search(
    q: Annotated[ProductSearchQueryValue, Query()] = "",
    barcode: Annotated[ProductBarcodeValue | None, Query()] = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.tax import resolve_product_tax

    stmt = select(m.Product).where(
        m.Product.tenant_id == claims["tenant_id"],
        m.Product.is_active == True,  # noqa: E712
    )
    q_clean = (q or "").strip()
    # Exact barcode param, or treat scanner wedge input in `q` as a barcode first.
    barcode_key = (barcode or "").strip() or (q_clean if barcodes_svc.looks_like_barcode(q_clean) else "")
    if barcode_key:
        stmt = stmt.where(
            (m.Product.barcode == barcode_key)
            | (m.Product.sku == barcode_key)
            | (func.lower(m.Product.barcode) == barcode_key.lower())
            | (func.lower(m.Product.sku) == barcode_key.lower())
        )
    elif q_clean:
        like = f"%{q_clean}%"
        stmt = stmt.where(
            m.Product.name.ilike(like)
            | m.Product.sku.ilike(like)
            | m.Product.barcode.ilike(like)
        )
    products = (await db.execute(stmt.limit(48))).scalars().all()
    product_by_id = {p.id: p for p in products}
    tax_cache: dict[str, dict] = {}

    async def tax_fields_for(product: m.Product) -> dict:
        cached = tax_cache.get(product.id)
        if cached is not None:
            return cached
        spec = await resolve_product_tax(db, claims["tenant_id"], product)
        payload = {
            "tax_rate_pct": money_json(spec.rate_pct or 0),
            "tax_pricing_mode": (spec.pricing_mode or "exclusive"),
            "tax_reverse_charge": bool(spec.is_reverse_charge),
            "tax_components": list(spec.components) if spec.components else None,
            "tax_supply_class": spec.supply_class,
        }
        tax_cache[product.id] = payload
        return payload

    out = []
    for p in products:
        row = {
            "id": p.id,
            "product_id": p.id,
            "variant_id": None,
            "name": p.name,
            "sku": p.sku,
            "barcode": p.barcode,
            "cost_price": money_json(p.cost_price or 0),
            "selling_price": money_json(p.selling_price or 0),
            "stock_qty": money_json(p.stock_qty or 0),
            "kind": "product",
            "has_image": bool(p.image_url),
        }
        row.update(await tax_fields_for(p))
        out.append(row)
    # Also surface matching variants for barcode/SKU search
    vstmt = select(m.ProductVariant).where(
        m.ProductVariant.tenant_id == claims["tenant_id"],
        m.ProductVariant.is_active == True,  # noqa: E712
    )
    if barcode_key:
        vstmt = vstmt.where(
            (m.ProductVariant.barcode == barcode_key)
            | (m.ProductVariant.sku == barcode_key)
            | (func.lower(m.ProductVariant.barcode) == barcode_key.lower())
            | (func.lower(m.ProductVariant.sku) == barcode_key.lower())
        )
    elif q_clean:
        like = f"%{q_clean}%"
        vstmt = vstmt.where(
            m.ProductVariant.name.ilike(like)
            | m.ProductVariant.sku.ilike(like)
            | m.ProductVariant.barcode.ilike(like)
        )
    else:
        vstmt = None
    if vstmt is not None:
        variants = (await db.execute(vstmt.limit(20))).scalars().all()
        missing_ids = {v.product_id for v in variants if v.product_id not in product_by_id}
        if missing_ids:
            parents = (
                await db.execute(
                    select(m.Product).where(
                        m.Product.tenant_id == claims["tenant_id"],
                        m.Product.id.in_(missing_ids),
                    )
                )
            ).scalars().all()
            for parent in parents:
                product_by_id[parent.id] = parent
        for v in variants:
            parent = product_by_id.get(v.product_id)
            row = {
                "id": v.id,
                "product_id": v.product_id,
                "variant_id": v.id,
                "name": v.name,
                "sku": v.sku,
                "barcode": v.barcode,
                "cost_price": money_json(
                    v.cost_price
                    if v.cost_price is not None
                    else (parent.cost_price if parent is not None and parent.cost_price is not None else 0)
                ),
                "selling_price": money_json(v.selling_price or 0),
                "stock_qty": money_json(v.stock_qty or 0),
                "kind": "variant",
                "has_image": False,
            }
            if parent is not None:
                row.update(await tax_fields_for(parent))
            else:
                row.update(
                    {
                        "tax_rate_pct": 0.0,
                        "tax_pricing_mode": "exclusive",
                        "tax_reverse_charge": False,
                        "tax_components": None,
                    }
                )
            out.append(row)
    return env(out[:40])


@api.get("/pos/sales/{sale_id}/receipt")
async def pos_receipt(
    sale_id: UuidIdValue,
    # omit → json; blank/invalid → 422 (was `format or "json"`)
    format: Annotated[ReceiptPrintFormatValue, Query()] = "json",
    # omit → branding default; blank/invalid → 422 (was silent branding fallback)
    paper: Annotated[ReceiptPaperValue | None, Query()] = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import receipts as receipts_svc
    from app.print_branding import print_branding_settings

    receipt = await receipts_svc.build_sale_receipt(
        db,
        tenant_id=claims["tenant_id"],
        sale_id=sale_id,
        user_id=claims.get("sub"),
        company_id=claims.get("company_id"),
    )
    branding = print_branding_settings(
        await tenants_svc.get_tenant(db, claims["tenant_id"])
    )
    fmt = format
    paper = paper if paper is not None else branding["default_receipt_paper"]
    if fmt == "json":
        public = {k: v for k, v in receipt.items() if k != "logo_key"}
        public["paper"] = paper
        public["text"] = receipts_svc.render_thermal_text(receipt, paper=paper)
        from app import cash_drawer as cash_drawer_svc

        public["drawer_kick_base64"] = cash_drawer_svc.kick_base64()
        public["drawer_kick_hex"] = cash_drawer_svc.kick_hex()
        return env(public)
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
    # Defense in depth: ReceiptPrintFormatValue Literal rejects unknown with 422.
    raise HTTPException(status_code=400, detail="format must be json, text, or pdf")


@api.post("/pos/sales/{sale_id}/receipt/send")
async def pos_receipt_send(
    sale_id: UuidIdValue,
    # omit → email; blank/invalid → 422 (was `channel or "email"`)
    channel: Annotated[ReceiptChannelValue, Query()] = "email",
    # omit → cashier email/phone; blank/invalid → 422 via ReceiptOverrideToValue
    # (email or E.164); channel refine remains below (email vs sms).
    to: Annotated[ReceiptOverrideToValue | None, Query()] = None,
    # omit → 80mm; blank/invalid → 422 (was silent 80mm for garbage)
    paper: Annotated[ReceiptPaperValue, Query()] = "80mm",
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
        company_id=claims.get("company_id"),
    )
    text = receipts_svc.render_thermal_text(receipt, paper=paper)
    channel = channel.lower() if isinstance(channel, str) else channel

    override: str | None = None
    if to is not None:
        # Channel refine: schema already ensured email|E.164 shape.
        try:
            if channel == "email":
                override = str(TypeAdapter(EmailStr).validate_python(to))
            else:
                override = TypeAdapter(E164PhoneValue).validate_python(to)
        except PydanticValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    "to must be a valid email"
                    if channel == "email"
                    else "to must be E.164 (+ and 8–15 digits)"
                ),
            ) from exc

    from app import audit as audit_svc

    if channel == "email":
        user = await db.get(m.User, claims["sub"])
        recipient = override or (user.email if user else None)
        if not recipient:
            raise HTTPException(status_code=400, detail="No email recipient")
        tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
        import html as html_lib

        inner = f'<pre style="font-family:monospace;white-space:pre-wrap;">{html_lib.escape(text)}</pre>'
        branded = emailer.render_branded_html(
            body_html=inner,
            company_name=getattr(tenant, "company_name", None),
            tenant=tenant,
            title=f"Receipt {receipt['reference']}",
        )
        result = await emailer.send_email(
            to=recipient,
            subject=f"Receipt {receipt['reference']}",
            text_body=text,
            html_body=branded,
            tenant=tenant,
        )
        if not result.sent and result.mode == "smtp":
            raise HTTPException(status_code=502, detail=result.error or "Email send failed")
        # Stage 13 H2 — domain audit after successful digital receipt send
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims.get("sub"),
            action="pos_receipt_sent",
            entity="pos_sale",
            entity_id=sale_id,
            details={
                "channel": "email",
                "to": recipient,
                "mode": result.mode,
                "reference": receipt.get("reference"),
                "total": float(receipt.get("total") or 0),
            },
            module="pos",
        )
        await db.commit()
        return env(
            {"channel": "email", "to": recipient, "sent": result.sent, "mode": result.mode},
            "Receipt emailed",
        )

    if channel == "sms":
        user = await db.get(m.User, claims["sub"])
        recipient = override or (user.phone if user else None)
        if not recipient:
            raise HTTPException(status_code=400, detail="No SMS recipient phone")
        body = (
            f"RIBDIGI receipt {receipt['reference']}: "
            f"{receipt.get('currency', '')} {_money_safe(receipt.get('total'))} "
            f"via {receipt.get('payment_method')}"
        )
        tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
        result = await sms_svc.send_sms(to=recipient, body=body, tenant=tenant)
        await db.commit()
        if not result.sent and result.mode == "twilio":
            raise HTTPException(status_code=502, detail=result.error or "SMS send failed")
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims.get("sub"),
            action="pos_receipt_sent",
            entity="pos_sale",
            entity_id=sale_id,
            details={
                "channel": "sms",
                "to": result.recipients,
                "mode": result.mode,
                "reference": receipt.get("reference"),
                "total": float(receipt.get("total") or 0),
            },
            module="pos",
        )
        await db.commit()
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
        return f"{money_json(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


@api.get("/expenses/categories")
async def list_expense_categories(
    is_active: bool | None = None,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List expense categories. Optional is_active filters soft-deactivated rows (Expenses manage UI)."""
    await expenses_svc.ensure_default_categories(db, claims["tenant_id"])
    await db.commit()
    stmt = (
        select(m.ExpenseCategory)
        .where(m.ExpenseCategory.tenant_id == claims["tenant_id"])
        .order_by(m.ExpenseCategory.name)
    )
    if is_active is not None:
        stmt = stmt.where(m.ExpenseCategory.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt)).scalars().all()
    account_ids = {c.account_id for c in rows if getattr(c, "account_id", None)}
    accounts: dict[str, m.Account] = {}
    if account_ids:
        accounts = {
            a.id: a
            for a in (
                await db.execute(
                    select(m.Account).where(
                        m.Account.tenant_id == claims["tenant_id"],
                        m.Account.id.in_(account_ids),
                    )
                )
            )
            .scalars()
            .all()
        }
    return env(
        [
            expenses_svc.serialize_category(c, accounts.get(c.account_id) if c.account_id else None)
            for c in rows
        ]
    )


@api.get("/expenses/categories/export")
async def expense_categories_export(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 123 X1 — expense categories CSV export."""
    text = await finance_meta_export_svc.export_expense_categories_csv(
        db,
        tenant_id=claims["tenant_id"],
        is_active=is_active,
        active_only=active_only,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="expense_categories_export.csv"'},
    )


@api.post("/expenses/categories")
async def create_expense_category(
    payload: ExpenseCategoryCreate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    account = await expenses_svc.resolve_expense_category_account(
        db, claims["tenant_id"], payload.account_id
    )
    cat = m.ExpenseCategory(
        tenant_id=claims["tenant_id"],
        # OpenAPI ExpenseCategoryCodeValue → 422; service defense-in-depth → 400.
        code=require_honest_narrative(
            payload.code.strip().upper(), label="expense category code", max_length=40
        ),
        name=require_honest_narrative(
            payload.name, label="expense category name", max_length=120
        ),
        budget_amount=payload.budget_amount,
        account_id=account.id if account else None,
    )
    db.add(cat)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Category code already exists") from exc
    await db.refresh(cat)
    return env(expenses_svc.serialize_category(cat, account))


@api.patch("/expenses/categories/{category_id}")
async def patch_expense_category(
    category_id: UuidIdValue,
    payload: ExpenseCategoryUpdate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    cat = await expenses_svc.update_category(
        db,
        claims["tenant_id"],
        category_id,
        name=data.get("name"),
        budget_amount=data.get("budget_amount"),
        is_active=data.get("is_active"),
        account_id=data.get("account_id"),
        clear_account=bool(data.get("clear_account")),
    )
    await db.commit()
    await db.refresh(cat)
    account = None
    if cat.account_id:
        account = await db.get(m.Account, cat.account_id)
    return env(expenses_svc.serialize_category(cat, account))


@api.get("/expenses/settings")
async def expense_settings(
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import numbering_settings

    data = await expenses_svc.get_approval_settings(db, claims["tenant_id"])
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    data["expense_numbering"] = numbering_settings(tenant, "expense")
    return env(data)


@api.get("/expenses/settings/export")
async def export_expense_settings(
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 138 E1 — expense approval settings CSV (levels as levels_json)."""
    text = await approval_settings_export_svc.export_expense_approval_settings_csv(
        db, tenant_id=claims["tenant_id"]
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="expense_settings_export.csv"'
        },
    )


@api.patch("/expenses/settings")
async def update_expense_settings(
    payload: ExpenseThresholdUpdate,
    claims=Depends(require_permission("expenses", "approve")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import apply_numbering_update, numbering_settings

    tenant = await db.get(m.Tenant, claims["tenant_id"])
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if (
        payload.levels is None
        and payload.expense_approval_threshold is None
        and payload.expense_l2_threshold is None
        and payload.expense_numbering is None
    ):
        raise HTTPException(status_code=400, detail="No settings fields provided")
    data = None
    if (
        payload.levels is not None
        or payload.expense_approval_threshold is not None
        or payload.expense_l2_threshold is not None
    ):
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
    else:
        data = await expenses_svc.get_approval_settings(db, claims["tenant_id"])
    if payload.expense_numbering is not None:
        # Numbering can be updated by expense writers; approve gate already covers admins.
        apply_numbering_update(
            tenant,
            "expense",
            prefix=payload.expense_numbering.prefix,
            next_number=payload.expense_numbering.next_number,
        )
    data["expense_numbering"] = numbering_settings(tenant, "expense")
    await db.commit()
    return env(data, "Expense settings updated")


@api.get("/expenses/recurring")
async def list_recurring_expenses(
    is_active: bool | None = None,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List recurring schedules. Optional is_active filters soft-deactivated rows (Expenses manage UI)."""
    stmt = (
        select(m.RecurringExpense)
        .where(m.RecurringExpense.tenant_id == claims["tenant_id"])
        .order_by(m.RecurringExpense.created_at.desc())
    )
    if is_active is not None:
        stmt = stmt.where(m.RecurringExpense.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt)).scalars().all()
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
        branch_id=payload.branch_id,
        department_id=payload.department_id,
    )
    await db.commit()
    return env(expenses_svc.serialize_recurring(row), "Recurring expense created")


@api.patch("/expenses/recurring/{recurring_id}")
async def update_recurring_expense(
    recurring_id: UuidIdValue,
    payload: RecurringExpenseUpdate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await expenses_svc.update_recurring(
        db,
        tenant_id=claims["tenant_id"],
        recurring_id=recurring_id,
        is_active=payload.is_active,
        amount=payload.amount,
        payee=payload.payee,
        clear_payee=payload.clear_payee,
        description=payload.description,
        payment_method=payload.payment_method,
        frequency=payload.frequency,
        category_id=payload.category_id,
        category=payload.category,
        branch_id=payload.branch_id,
        department_id=payload.department_id,
        clear_branch=payload.clear_branch,
        clear_department=payload.clear_department,
    )
    await db.commit()
    if payload.is_active is True:
        msg = "Recurring expense activated"
    elif payload.is_active is False:
        msg = "Recurring expense deactivated"
    else:
        msg = "Recurring schedule updated"
    return env(expenses_svc.serialize_recurring(row), msg)


@api.post("/expenses/recurring/{recurring_id}/skip-next")
async def skip_next_recurring_expense(
    recurring_id: UuidIdValue,
    payload: RecurringSkipNext,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Skip the next occurrence: advance next_run_at by one period (no expense created)."""
    row = await expenses_svc.skip_next_recurring(
        db,
        tenant_id=claims["tenant_id"],
        recurring_id=recurring_id,
        user_id=claims["sub"],
        reason=payload.reason,
    )
    await db.commit()
    msg = "Next occurrence skipped"
    if not row.is_active:
        msg = "Next occurrence skipped; schedule ended past end_date"
    return env(expenses_svc.serialize_recurring(row), msg)


@api.post("/expenses/recurring/generate")
async def generate_recurring_expenses(
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    created = await expenses_svc.generate_due_recurring(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(
        [await expenses_svc.serialize_expense_full(db, e) for e in created],
        f"Generated {len(created)} expense(s)",
    )


@api.get("/expenses")
async def expenses(
    status: Annotated[ExpenseStatusFilterValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(m.Expense)
        .where(m.Expense.tenant_id == claims["tenant_id"])
        .order_by(m.Expense.created_at.desc())
    )
    stmt = apply_created_by_scope(stmt, m.Expense, claims)
    # Schema ExpenseStatusFilterValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in {"pending", "approved", "rejected"}:
            raise HTTPException(
                status_code=422,
                detail="status must be pending, approved, or rejected",
            )
        else:
            stmt = stmt.where(m.Expense.status == wanted)
    if store_id:
        stmt = stmt.where(m.Expense.store_id == store_id)
    rows = (await db.execute(stmt)).scalars().all()
    return env([await expenses_svc.serialize_expense_full(db, e) for e in rows])


@api.get("/expenses/export")
async def expenses_export(
    store_id: str | None = None,
    department_id: str | None = None,
    status: str | None = None,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 120 X1 — expenses CSV export (record-scope aware)."""
    text = await expense_export_svc.export_expenses_csv(
        db,
        tenant_id=claims["tenant_id"],
        claims=claims,
        status=status,
        store_id=store_id,
        department_id=department_id,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="expenses_export.csv"'},
    )


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
        branch_id=payload.branch_id,
        department_id=payload.department_id,
        liquid_account_id=payload.liquid_account_id,
        expense_date=reports_svc.parse_date(payload.expense_date),
    )
    await db.commit()
    return env(await expenses_svc.serialize_expense_full(db, expense), "Expense recorded")


@api.get("/expenses/{expense_id}")
async def get_expense(
    expense_id: UuidIdValue,
    claims=Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    return env(await expenses_svc.serialize_expense_full(db, expense))


@api.patch("/expenses/{expense_id}")
async def patch_expense(
    expense_id: UuidIdValue,
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
        expense_date=reports_svc.parse_date(payload.expense_date),
        payment_method=payload.payment_method,
        category_id=payload.category_id,
        category=payload.category,
        store_id=payload.store_id,
        branch_id=payload.branch_id,
        department_id=payload.department_id,
        clear_store=payload.clear_store,
        clear_branch=payload.clear_branch,
        clear_department=payload.clear_department,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="expenses",
        action="expense_ocr_apply",
        entity="expense",
        entity_id=expense.id,
        details={"status": expense.status, "amount": money_json(expense.amount)},
    )
    await db.commit()
    return env(await expenses_svc.serialize_expense_full(db, expense), "Expense updated")


@api.post("/expenses/{expense_id}/ocr-suggest")
async def expense_ocr_suggest(
    expense_id: UuidIdValue,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import expense_ocr as ocr_svc

    expense = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    assert_record_access(claims, expense.created_by)
    result = await ocr_svc.suggest_for_expense(
        db, tenant_id=claims["tenant_id"], expense_id=expense_id
    )


@api.post("/expenses/{expense_id}/attachment")
async def upload_expense_attachment(
    expense_id: UuidIdValue,
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
    expense_id: UuidIdValue,
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
    expense_id: UuidIdValue,
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
    expense_id: UuidIdValue,
    payload: ExpenseDecision = ExpenseDecision(),
    claims=Depends(require_permission("expenses", "approve")),
    db: AsyncSession = Depends(get_db),
):
    existing = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    workspace_svc.assert_record_company(claims, existing)
    expense = await expenses_svc.approve_expense(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        expense_id=expense_id,
        comment=payload.comment,
        actor_role=claims.get("role"),
    )
    if expense.status == "approved":
        await webhooks_svc.emit_event(
            db,
            tenant_id=claims["tenant_id"],
            event="expense.approved",
            data={
                "expense_id": expense.id,
                "amount": money_json(expense.amount or 0),
                "category": expense.category,
                "approved_by": expense.approved_by,
                "approved_at": expense.approved_at.isoformat()
                if getattr(expense, "approved_at", None)
                else None,
            },
        )
    await db.commit()
    if expense.status == "approved":
        await cache_svc.app_cache.invalidate_dashboard(claims["tenant_id"])
    msg = "Expense approved" if expense.status == "approved" else f"Level {int(expense.approval_step) - 1} approved; awaiting next level"
    return env(await expenses_svc.serialize_expense_full(db, expense), msg)


@api.post("/expenses/{expense_id}/reject")
async def reject_expense(
    expense_id: UuidIdValue,
    payload: ExpenseReject,
    claims=Depends(require_permission("expenses", "approve")),
    db: AsyncSession = Depends(get_db),
):
    existing = await expenses_svc.get_expense(db, claims["tenant_id"], expense_id)
    workspace_svc.assert_record_company(claims, existing)
    expense = await expenses_svc.reject_expense(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        expense_id=expense_id,
        reason=payload.reason,
        actor_role=claims.get("role"),
    )
    await db.commit()
    return env(await expenses_svc.serialize_expense_full(db, expense), "Expense rejected")


@api.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: UuidIdValue,
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
    is_active: bool | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List COA accounts. Optional is_active filters soft-deactivated rows (Accounting manage UI)."""
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    await accounting_svc.ensure_default_accounts(
        db, claims["tenant_id"], company_id=claims.get("company_id")
    )
    await db.commit()
    stmt = (
        select(m.Account)
        .where(m.Account.tenant_id == claims["tenant_id"])
        .order_by(m.Account.code)
    )
    if is_active is not None:
        stmt = stmt.where(m.Account.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt)).scalars().all()
    return env([bank_recon_svc.serialize_account(r) for r in rows])


@api.post("/accounting/accounts")
async def create_account(
    payload: AccountCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_transfers as cash_xfer_svc
    from app import audit as audit_svc

    row = await cash_xfer_svc.create_account(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        account_type=payload.account_type,
        liquid_kind=payload.liquid_kind,
        bank_name=payload.bank_name,
        account_number=payload.account_number,
        bank_branch=payload.bank_branch,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="account_create",
        entity="account",
        entity_id=row.id,
        details={"code": row.code, "liquid_kind": payload.liquid_kind},
    )
    await db.commit()
    await db.refresh(row)
    return env(cash_xfer_svc.serialize_account(row), "Account created")


@api.patch("/accounting/accounts/{account_id}")
async def patch_account(
    account_id: UuidIdValue,
    payload: AccountUpdate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_transfers as cash_xfer_svc
    from app import audit as audit_svc

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    row = await cash_xfer_svc.update_account(
        db,
        tenant_id=claims["tenant_id"],
        account_id=account_id,
        name=data.get("name"),
        bank_name=data.get("bank_name"),
        account_number=data.get("account_number"),
        bank_branch=data.get("bank_branch"),
        is_active=data.get("is_active"),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="account_update",
        entity="account",
        entity_id=row.id,
        details=data,
    )
    await db.commit()
    await db.refresh(row)
    return env(cash_xfer_svc.serialize_account(row), "Account updated")


@api.get("/accounting/accounts/{account_id}")
async def get_account(
    account_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_transfers as cash_xfer_svc

    row = await cash_xfer_svc.get_account(db, claims["tenant_id"], account_id)
    return env(cash_xfer_svc.serialize_account(row))


@api.get("/accounting/opening-balances")
async def coa_opening_status(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import opening_balances as opening_bal_svc

    status = await opening_bal_svc.opening_status(db, claims["tenant_id"])
    await db.commit()
    return env(status)


@api.post("/accounting/opening-balances")
async def coa_opening_post(
    payload: OpeningBalanceCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-10.1 — post COA opening balances as a balanced journal (equity plug to 3000)."""
    from app import opening_balances as opening_bal_svc

    result = await opening_bal_svc.post_coa_opening_balances(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        lines=[line.model_dump() for line in payload.lines],
        reference=payload.reference,
        notes=payload.notes,
    )
    await db.commit()
    return env(result, "COA opening balances posted")


@api.get("/accounting/liquid-accounts")
async def liquid_accounts(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 125 L1 — active_only / is_active for honest inactive-only liquid lists."""
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    await ensure_default_accounts(db, claims["tenant_id"], company_id=claims.get("company_id"))
    await db.commit()
    rows = await bank_recon_svc.list_liquid_accounts(
        db,
        claims["tenant_id"],
        active_only=active_only,
        is_active=is_active,
        company_id=claims.get("company_id"),
    )
    return env([bank_recon_svc.serialize_account(r) for r in rows])


@api.get("/accounting/transfers")
async def list_cash_transfers(
    kind: Annotated[CashTransferKindFilterValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_transfers as cash_xfer_svc

    # Schema CashTransferKindFilterValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    rows = await cash_xfer_svc.list_transfers(db, claims["tenant_id"], kind=kind)
    amap = await cash_xfer_svc.accounts_map_for_transfers(db, claims["tenant_id"], rows)
    return env([cash_xfer_svc.serialize_transfer(r, accounts=amap) for r in rows])


@api.post("/accounting/transfers")
async def create_cash_transfer(
    payload: CashTransferCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_transfers as cash_xfer_svc
    from app import audit as audit_svc

    row = await cash_xfer_svc.create_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        kind=payload.kind,
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        amount=payload.amount,
        reference=payload.reference,
        notes=payload.notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="accounting",
        action="cash_transfer",
        entity="cash_transfer",
        entity_id=row.id,
        details={
            "kind": row.kind,
            "amount": money_json(row.amount),
            "from_account_id": row.from_account_id,
            "to_account_id": row.to_account_id,
        },
    )
    await db.commit()
    await db.refresh(row)
    amap = await cash_xfer_svc.accounts_map_for_transfers(db, claims["tenant_id"], [row])
    return env(
        cash_xfer_svc.serialize_transfer(row, accounts=amap),
        "Cash/bank movement posted",
    )


@api.get("/accounting/transfers/{transfer_id}")
async def get_cash_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_transfers as cash_xfer_svc

    row = await cash_xfer_svc.get_transfer(db, claims["tenant_id"], transfer_id)
    amap = await cash_xfer_svc.accounts_map_for_transfers(db, claims["tenant_id"], [row])
    return env(cash_xfer_svc.serialize_transfer(row, accounts=amap))


@api.get("/settings/bank-feed")
async def bank_feed_settings(claims=Depends(require_permission("accounting", "read"))):
    from app import bank_connectors as bank_connectors_svc

    return env(bank_connectors_svc.settings_payload())


@api.get("/settings/bank-feed/export")
async def bank_feed_settings_export(
    claims=Depends(require_permission("accounting", "read")),
):
    """Stage 156 F1 — secret-free bank-feed settings CSV (no tokens/credentials)."""
    text = bank_webhook_export_svc.export_bank_feed_settings_csv()
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="bank_feed_settings_export.csv"'
        },
    )


@api.get("/accounting/bank-connections")
async def list_bank_connections(
    is_active: bool | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List bank feed connections. Optional is_active filters soft-deactivated rows (Reconcile manage UI)."""
    from app import bank_connectors as bank_connectors_svc

    rows = await bank_connectors_svc.list_connections(
        db, claims["tenant_id"], is_active=is_active
    )
    return env([bank_connectors_svc.serialize_connection(r) for r in rows])


@api.get("/accounting/bank-connections/export")
async def bank_connections_export(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 126 X1 — bank connections CSV export (no credentials)."""
    text = await bank_webhook_export_svc.export_bank_connections_csv(
        db,
        tenant_id=claims["tenant_id"],
        is_active=is_active,
        active_only=active_only,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bank_connections_export.csv"'},
    )


@api.post("/accounting/bank-connections")
async def create_bank_connection(
    payload: BankConnectionCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts
    from app import bank_connectors as bank_connectors_svc
    from app import audit as audit_svc

    await ensure_default_accounts(db, claims["tenant_id"], company_id=claims.get("company_id"))
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
        company_id=claims.get("company_id"),
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
    connection_id: UuidIdValue,
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
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(bank_connectors_svc.serialize_connection(row), "Bank connection updated")


@api.delete("/accounting/bank-connections/{connection_id}")
async def delete_bank_connection(
    connection_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_connectors as bank_connectors_svc
    from app import audit as audit_svc

    await bank_connectors_svc.delete_connection(
        db,
        tenant_id=claims["tenant_id"],
        connection_id=connection_id,
        company_id=claims.get("company_id"),
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
    connection_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts
    from app import bank_connectors as bank_connectors_svc
    from app import audit as audit_svc

    await ensure_default_accounts(db, claims["tenant_id"], company_id=claims.get("company_id"))
    result = await bank_connectors_svc.sync_connection(
        db,
        tenant_id=claims["tenant_id"],
        connection_id=connection_id,
        user_id=claims.get("sub"),
        force=False,
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
    status: Annotated[BankStatementStatusFilterValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 131 B1 — optional status=draft|in_progress|reconciled for statement honesty."""
    from app import bank_recon as bank_recon_svc

    rows = await bank_recon_svc.list_statements(
        db, claims["tenant_id"], status=status
    )
    out = []
    for row in rows:
        lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], row.id)
        out.append(bank_recon_svc.serialize_statement(row, lines))
    return env(out)


@api.get("/accounting/bank-statements/export")
async def bank_statements_export(
    status: str | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 131 B1 — bank statement header CSV (line details omitted)."""
    status_n = (status or "").strip().lower() or None
    if status_n and status_n not in {"draft", "in_progress", "reconciled"}:
        raise HTTPException(
            status_code=400,
            detail="status must be draft, in_progress, or reconciled",
        )
    text = await finance_ops_export_svc.export_bank_statements_csv(
        db,
        tenant_id=claims["tenant_id"],
        status=status_n,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="bank_statements_export.csv"'
        },
    )


@api.post("/accounting/bank-statements")
async def create_bank_statement(
    payload: BankStatementCreateBody,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    # Schema BankStatementCreateBody rejects unknown keys / blank account_id /
    # zero line amounts → 422.
    await ensure_default_accounts(db, claims["tenant_id"])
    stmt = await bank_recon_svc.create_statement(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        account_id=payload.account_id,
        statement_date=payload.statement_date,
        opening_balance=money_json(payload.opening_balance or 0),
        closing_balance=money_json(payload.closing_balance or 0),
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines],
    )
    await db.commit()
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], stmt.id)
    return env(bank_recon_svc.serialize_statement(stmt, lines), "Bank statement created")


@api.post("/accounting/bank-statements/import")
async def import_bank_statement(
    account_id: UuidIdValue,
    file: UploadFile = File(...),
    # omit/`null` → feed/default; nan/inf/out-of-range → **422** (was free float)
    opening_balance: Annotated[FiniteMoneyValue | None, Query()] = None,
    closing_balance: Annotated[FiniteMoneyValue | None, Query()] = None,
    statement_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    notes: Annotated[BankStatementNotesValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Import a CSV or OFX/QFX bank statement file into a reconcilable statement."""
    from app.accounting import ensure_default_accounts
    from app import bank_recon as bank_recon_svc

    await ensure_default_accounts(db, claims["tenant_id"], company_id=claims.get("company_id"))
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
        company_id=claims.get("company_id"),
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
    statement_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(
        db,
        claims["tenant_id"],
        statement_id,
        company_id=claims.get("company_id"),
    )
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
    statement_id: UuidIdValue,
    payload: BankClearGroupBody,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Clear N bank lines against M book lines when totals match."""
    from app import bank_recon as bank_recon_svc

    # Schema BankClearGroupBody rejects unknown keys / empty id lists → 422.
    result = await bank_recon_svc.create_clearing_group(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        statement_id=statement_id,
        statement_line_ids=payload.statement_line_ids,
        journal_line_ids=payload.journal_line_ids,
        notes=payload.notes,
    )
    await db.commit()
    stmt = await bank_recon_svc.get_statement(
        db,
        claims["tenant_id"],
        statement_id,
        company_id=claims.get("company_id"),
    )
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
    statement_id: UuidIdValue,
    group_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(
        db,
        claims["tenant_id"],
        statement_id,
        company_id=claims.get("company_id"),
    )
    result = await bank_recon_svc.dissolve_clearing_group(
        db,
        tenant_id=claims["tenant_id"],
        group_id=group_id,
        statement_id=statement_id,
        company_id=claims.get("company_id"),
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
    statement_id: UuidIdValue,
    payload: BankAutoClearBody | None = None,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Apply high-confidence (default) bank↔book matches in one shot."""
    from app import bank_recon as bank_recon_svc

    body = payload or BankAutoClearBody()
    result = await bank_recon_svc.apply_auto_matches(
        db,
        tenant_id=claims["tenant_id"],
        statement_id=statement_id,
        min_confidence=body.min_confidence,
        date_window_days=body.date_window_days,
    )
    await db.commit()
    stmt = await bank_recon_svc.get_statement(
        db,
        claims["tenant_id"],
        statement_id,
        company_id=claims.get("company_id"),
    )
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], statement_id)
    data = bank_recon_svc.serialize_statement(stmt, lines)
    data["auto_clear"] = result
    data["suggestions"] = await bank_recon_svc.auto_match_suggestions(
        db, tenant_id=claims["tenant_id"], statement_id=statement_id
    )
    return env(data, f"Auto-cleared {result['applied_count']} line(s)")


@api.post("/accounting/bank-statements/{statement_id}/lines/{line_id}/match")
async def match_bank_statement_line(
    statement_id: UuidIdValue,
    line_id: UuidIdValue,
    payload: BankStatementMatchBody,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    # Schema BankStatementMatchBody rejects unknown keys / blank journal_line_id → 422.
    stmt = await bank_recon_svc.get_statement(db, claims["tenant_id"], statement_id)
    line = await bank_recon_svc.match_line(
        db,
        tenant_id=claims["tenant_id"],
        line_id=line_id,
        journal_line_id=payload.journal_line_id,
    )
    if line.statement_id != stmt.id:
        raise HTTPException(status_code=404, detail="Statement line not found")
    await db.commit()
    return env(bank_recon_svc.serialize_line(line), "Line matched")


@api.post("/accounting/bank-statements/{statement_id}/lines/{line_id}/unmatch")
async def unmatch_bank_statement_line(
    statement_id: UuidIdValue,
    line_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(
        db,
        claims["tenant_id"],
        statement_id,
        company_id=claims.get("company_id"),
    )
    line = await bank_recon_svc.unmatch_line(db, tenant_id=claims["tenant_id"], line_id=line_id)
    if line.statement_id != stmt.id:
        raise HTTPException(status_code=404, detail="Statement line not found")
    await db.commit()
    return env(bank_recon_svc.serialize_line(line), "Line unmatched")


@api.post("/accounting/bank-statements/{statement_id}/lines/{line_id}/ignore")
async def ignore_bank_statement_line(
    statement_id: UuidIdValue,
    line_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.get_statement(
        db,
        claims["tenant_id"],
        statement_id,
        company_id=claims.get("company_id"),
    )
    line = await bank_recon_svc.ignore_line(db, tenant_id=claims["tenant_id"], line_id=line_id)
    if line.statement_id != stmt.id:
        raise HTTPException(status_code=404, detail="Statement line not found")
    await db.commit()
    return env(bank_recon_svc.serialize_line(line), "Line ignored")


@api.post("/accounting/bank-statements/{statement_id}/complete")
async def complete_bank_statement(
    statement_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bank_recon as bank_recon_svc

    stmt = await bank_recon_svc.complete_statement(
        db,
        tenant_id=claims["tenant_id"],
        statement_id=statement_id,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    lines = await bank_recon_svc.list_statement_lines(db, claims["tenant_id"], stmt.id)
    return env(bank_recon_svc.serialize_statement(stmt, lines), "Statement reconciled")


@api.get("/accounting/cheques")
async def list_cheques(
    direction: Annotated[ChequeDirectionValue | None, Query()] = None,
    status: Annotated[ChequeStatusValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await cheques_svc.list_cheques(
        db,
        claims["tenant_id"],
        direction=direction,
        status=status,
        company_id=claims.get("company_id"),
    )
    return env([cheques_svc.serialize_cheque(r) for r in rows])


@api.get("/accounting/cheques/export")
async def cheques_export(
    direction: str | None = None,
    status: str | None = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 130 C1 — cheques CSV honoring direction/status filters."""
    text = await ops_lifecycle_export_svc.export_cheques_csv(
        db,
        tenant_id=claims["tenant_id"],
        direction=direction,
        status=status,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cheques_export.csv"'},
    )


@api.get("/accounting/cheques/{cheque_id}")
async def get_cheque_detail(
    cheque_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.get_cheque(
        db, claims["tenant_id"], cheque_id, company_id=claims.get("company_id")
    )
    return env(cheques_svc.serialize_cheque(row))


@api.post("/accounting/cheques/{cheque_id}/deposit")
async def deposit_cheque_api(
    cheque_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.deposit_cheque(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        cheque_id=cheque_id,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque deposited to bank")


@api.post("/accounting/cheques/{cheque_id}/clear")
async def clear_cheque_api(
    cheque_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.clear_cheque(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        cheque_id=cheque_id,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque cleared")


@api.post("/accounting/cheques/{cheque_id}/bounce")
async def bounce_cheque_api(
    cheque_id: UuidIdValue,
    payload: ChequeLifecycleReason,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.bounce_cheque(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        cheque_id=cheque_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque bounced")


@api.post("/accounting/cheques/{cheque_id}/cancel")
async def cancel_cheque_api(
    cheque_id: UuidIdValue,
    payload: ChequeLifecycleReason,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await cheques_svc.cancel_cheque(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        cheque_id=cheque_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(cheques_svc.serialize_cheque(row), "Cheque cancelled")


@api.get("/accounting/settings")
async def accounting_settings(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import numbering_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(
        {
            "journal_numbering": numbering_settings(tenant, "journal_entry"),
            "cash_transfer_numbering": numbering_settings(tenant, "cash_transfer"),
        }
    )


@api.patch("/accounting/settings")
async def update_accounting_settings(
    payload: AccountingSettingsUpdate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import apply_numbering_update, numbering_settings

    if payload.journal_numbering is None and payload.cash_transfer_numbering is None:
        raise HTTPException(status_code=400, detail="No numbering fields to update")
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if payload.journal_numbering is not None:
        apply_numbering_update(
            tenant,
            "journal_entry",
            prefix=payload.journal_numbering.prefix,
            next_number=payload.journal_numbering.next_number,
        )
    if payload.cash_transfer_numbering is not None:
        apply_numbering_update(
            tenant,
            "cash_transfer",
            prefix=payload.cash_transfer_numbering.prefix,
            next_number=payload.cash_transfer_numbering.next_number,
        )
    await db.commit()
    return env(
        {
            "journal_numbering": numbering_settings(tenant, "journal_entry"),
            "cash_transfer_numbering": numbering_settings(tenant, "cash_transfer"),
        },
        "Accounting document numbering updated",
    )


@api.get("/accounting/journal-entries")
async def list_journals(
    status: Annotated[JournalStatusFilterValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    # Schema JournalStatusFilterValue rejects blank/invalid → 422; keep allow-list
    # defense-in-depth (no silent empty filter / blank→all).
    stmt = (
        select(m.JournalEntry)
        .where(m.JournalEntry.tenant_id == claims["tenant_id"])
        .order_by(m.JournalEntry.created_at.desc())
        .limit(100)
    )
    if status is not None:
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in {"posted", "unposted"}:
            raise HTTPException(
                status_code=422,
                detail="status must be posted or unposted",
            )
        else:
            stmt = stmt.where(m.JournalEntry.status == wanted)
    rows = (await db.execute(stmt)).scalars().all()
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
        entry_date=reports_svc.parse_date(payload.entry_date),
        lines=[ln.model_dump() for ln in payload.lines],
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await accounting_svc.serialize_journal(db, entry), "Journal entry posted")


@api.get("/accounting/period")
async def accounting_period_status(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    return env(await accounting_svc.period_status(db, claims["tenant_id"]))


@api.post("/accounting/period/close")
async def accounting_period_close(
    payload: PeriodCloseBody,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-10.2 — close books through an inclusive calendar date."""
    from app import accounting as accounting_svc

    parsed = reports_svc.parse_date(payload.through_date)
    status = await accounting_svc.close_books(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        through_date=accounting_svc.as_calendar_date(parsed),
        reason=payload.reason,
    )
    await db.commit()
    return env(status, "Books closed")


@api.post("/accounting/period/reopen")
async def accounting_period_reopen(
    payload: PeriodReopenBody,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-10.2 — reopen books (earlier through_date or clear)."""
    from app import accounting as accounting_svc

    parsed = reports_svc.parse_date(payload.through_date)
    status = await accounting_svc.reopen_books(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        through_date=accounting_svc.as_calendar_date(parsed),
        reason=payload.reason,
    )
    await db.commit()
    return env(status, "Books reopened")


@api.post("/accounting/journal-entries/{entry_id}/unpost")
async def unpost_journal(
    entry_id: UuidIdValue,
    payload: JournalUnpost,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.unpost_journal_entry(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        entry_id=entry_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await accounting_svc.serialize_journal(db, entry), "Journal entry unposted")


@api.post("/accounting/journal-entries/{entry_id}/attachment")
async def upload_journal_attachment(
    entry_id: UuidIdValue,
    file: UploadFile = File(...),
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.get_journal_entry(db, claims["tenant_id"], entry_id)
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="journals",
        upload=file,
        allowed_types=storage_svc.ATTACHMENT_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_ATTACHMENT_BYTES),
    )
    if entry.attachment_url and "://" not in entry.attachment_url:
        storage_svc.delete_key(entry.attachment_url, tenant_id=claims["tenant_id"])
    entry.attachment_url = stored.key
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="accounting",
        action="journal_attachment_upload",
        entity="journal_entry",
        entity_id=entry.id,
        details={"key": stored.key, "size": stored.size, "content_type": stored.content_type},
    )
    await db.commit()
    data = await accounting_svc.serialize_journal(db, entry)
    data["uploaded"] = {
        "key": stored.key,
        "size": stored.size,
        "content_type": stored.content_type,
        "filename": stored.original_filename,
    }
    return env(data, "Attachment uploaded")


@api.get("/accounting/journal-entries/{entry_id}/attachment")
async def download_journal_attachment(
    entry_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.get_journal_entry(db, claims["tenant_id"], entry_id)
    if not entry.attachment_url:
        raise HTTPException(status_code=404, detail="No attachment uploaded")
    if "://" in entry.attachment_url:
        raise HTTPException(
            status_code=400,
            detail="Attachment is an external URL; open attachment_url directly",
        )
    return storage_svc.media_response(
        entry.attachment_url, tenant_id=claims["tenant_id"], as_attachment=True
    )


@api.delete("/accounting/journal-entries/{entry_id}/attachment")
async def delete_journal_attachment(
    entry_id: UuidIdValue,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import accounting as accounting_svc

    entry = await accounting_svc.get_journal_entry(db, claims["tenant_id"], entry_id)
    if not entry.attachment_url:
        raise HTTPException(status_code=404, detail="No attachment uploaded")
    if "://" not in entry.attachment_url:
        storage_svc.delete_key(entry.attachment_url, tenant_id=claims["tenant_id"])
    entry.attachment_url = None
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="accounting",
        action="journal_attachment_delete",
        entity="journal_entry",
        entity_id=entry.id,
    )
    await db.commit()
    return env(await accounting_svc.serialize_journal(db, entry), "Attachment removed")


@api.get("/accounting/trial-balance")
async def get_trial_balance(
    as_of: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Optional location filters ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/
    # `http://…`/non-UUID → **422** (was free `str`; garbage could reach store/branch lookup).
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts, trial_balance

    await ensure_default_accounts(
        db, claims["tenant_id"], company_id=claims.get("company_id")
    )
    await db.commit()
    return env(
        await trial_balance(
            db,
            claims["tenant_id"],
            as_of=reports_svc.parse_date(as_of, end_of_day=True),
            store_id=store_id or None,
            branch_id=branch_id or None,
        )
    )


@api.get("/accounting/profit-loss")
async def get_profit_loss(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Same UuidIdValue Query honesty as trial-balance location filters.
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.accounting import ensure_default_accounts

    await ensure_default_accounts(
        db, claims["tenant_id"], company_id=claims.get("company_id")
    )
    await db.commit()
    return env(
        await profit_and_loss(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            store_id=store_id or None,
            branch_id=branch_id or None,
        )
    )


@api.get("/reports/profit-loss")
async def report_profit_loss(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
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
            store_id=store_id or None,
            branch_id=branch_id or None,
        )
    )


@api.get("/reports/trial-balance")
async def report_trial_balance(
    as_of: Annotated[IsoDateQueryValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return await get_trial_balance(
        as_of=as_of,
        store_id=store_id,
        branch_id=branch_id,
        claims=claims,
        db=db,
    )


@api.get("/reports/cash-flow")
async def report_cash_flow(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.cash_flow_with_optional_compare(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            store_id=store_id,
            branch_id=branch_id,
        )
    )


@api.get("/reports/cash-flow/export")
async def reports_cash_flow_export(
    from_date: str | None = None,
    to_date: str | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 160 C1 — reports cash-flow path CSV (distinct from generic /reports/export)."""
    text = await finance_ops_export_svc.export_cash_flow_csv(
        db,
        tenant_id=claims["tenant_id"],
        from_date=reports_svc.parse_date(from_date),
        to_date=reports_svc.parse_date(to_date, end_of_day=True),
        store_id=store_id,
        branch_id=branch_id,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="reports_cash_flow_export.csv"'
        },
    )


@api.get("/reports/balance-sheet")
async def report_balance_sheet(
    as_of: Annotated[IsoDateQueryValue | None, Query()] = None,
    # omit → no compare; blank/invalid → 422 (was free str → service 400; "" → no compare)
    compare: Annotated[BalanceSheetCompareValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.balance_sheet(
            db,
            claims["tenant_id"],
            as_of=reports_svc.parse_date(as_of, end_of_day=True),
            compare=compare,
            store_id=store_id or None,
            branch_id=branch_id or None,
        )
    )


@api.get("/accounting/balance-sheet")
async def accounting_balance_sheet(
    as_of: Annotated[IsoDateQueryValue | None, Query()] = None,
    compare: Annotated[BalanceSheetCompareValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.balance_sheet(
            db,
            claims["tenant_id"],
            as_of=reports_svc.parse_date(as_of, end_of_day=True),
            compare=compare,
            store_id=store_id or None,
            branch_id=branch_id or None,
        )
    )


@api.get("/reports/export")
async def reports_export(
    # required; blank/unknown → 422 (was free str → service 400)
    report_type: Annotated[ReportTypeValue, Query()],
    # omit → csv; blank/invalid → 422 (was `fmt or "csv"`)
    format: Annotated[ReportExportFormatValue, Query()] = "csv",
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # omit/`null` → export default year; <2000/>2100 → **422** (was free int)
    year: Annotated[int, Query(ge=2000, le=2100)] | None = None,
    # omit/`null` → export default month; <1/>12 → **422** (was free int)
    month: Annotated[int, Query(ge=1, le=12)] | None = None,
    # Optional location/category filters ∈ UuidIdValue; omit/`null` OK; blank/`!!!`/
    # `http://…`/non-UUID → **422** (was free `str`).
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    # omit → export default (tax_filing_gh → GH); blank/unsupported → 422
    jurisdiction: Annotated[TaxFilingJurisdictionValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    category_id: Annotated[UuidIdValue | None, Query()] = None,
    # omit/`null` → export default horizon; 0/negative/>365 → **422** (was free int)
    days: Annotated[int, Query(ge=1, le=365)] | None = None,
    as_of: Annotated[IsoDateQueryValue | None, Query()] = None,
    # omit → no compare; blank/invalid → 422 (same Literal as balance-sheet routes)
    compare: Annotated[BalanceSheetCompareValue | None, Query()] = None,
    department_id: Annotated[UuidIdValue | None, Query()] = None,
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
        as_of_date=as_of_date,
        year=year,
        month=month,
        warehouse_id=warehouse_id,
        store_id=store_id,
        branch_id=branch_id,
        category_id=category_id,
        jurisdiction=jurisdiction,
        store_id=store_id or None,
        branch_id=branch_id or None,
        category_id=category_id or None,
        days=days,
        as_of=as_of or None,
        compare=compare or None,
        department_id=department_id or None,
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
    enabled: bool | None = None,
    frequency: Annotated[ScheduleFrequencyValue | None, Query()] = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    # enabled: FastAPI bool Query (omit → all; invalid → 422).
    # frequency: ScheduleFrequencyValue rejects blank/invalid → 422; service allow-list
    # remains defense-in-depth.
    rows = await report_schedules_svc.list_schedules(
        db,
        claims["tenant_id"],
        enabled=enabled,
        frequency=frequency,
    )
    return env([report_schedules_svc.serialize_schedule(r) for r in rows])


@api.get("/reports/schedules/export")
async def report_schedules_export(
    enabled: bool | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 127 S1 — report schedules CSV export."""
    text = await api_fx_schedule_export_svc.export_report_schedules_csv(
        db,
        tenant_id=claims["tenant_id"],
        enabled=enabled,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="report_schedules_export.csv"'},
    )


@api.post("/reports/schedules")
async def report_schedules_create(
    payload: ReportScheduleCreate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await report_schedules_svc.create_schedule(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        name=payload.name,
        report_type=payload.report_type,
        format=payload.format,
        frequency=payload.frequency,
        weekday=payload.weekday,
        hour_utc=payload.hour_utc,
        recipients=payload.recipients,
        enabled=payload.enabled,
    )
    await db.commit()
    return env(report_schedules_svc.serialize_schedule(row), "Report schedule created")


@api.patch("/reports/schedules/{schedule_id}")
async def report_schedules_patch(
    schedule_id: UuidIdValue,
    payload: ReportScheduleUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    row = await report_schedules_svc.update_schedule(
        db,
        claims["tenant_id"],
        schedule_id,
        name=data.get("name"),
        report_type=data.get("report_type"),
        format=data.get("format"),
        frequency=data.get("frequency"),
        weekday=data.get("weekday"),
        hour_utc=data.get("hour_utc"),
        recipients=data.get("recipients"),
        enabled=data.get("enabled"),
    )
    await db.commit()
    return env(report_schedules_svc.serialize_schedule(row), "Report schedule updated")


@api.delete("/reports/schedules/{schedule_id}")
async def report_schedules_delete(
    schedule_id: UuidIdValue,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await report_schedules_svc.delete_schedule(
        db, claims["tenant_id"], schedule_id, company_id=claims.get("company_id")
    )
    await db.commit()
    return env({"id": schedule_id}, "Report schedule deleted")


@api.post("/reports/schedules/{schedule_id}/run")
async def report_schedules_run(
    schedule_id: UuidIdValue,
    force: bool = True,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await report_schedules_svc.get_schedule(
        db, claims["tenant_id"], schedule_id, company_id=claims.get("company_id")
    )
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
    date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Optional store ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach store lookup).
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.sales_daily(
            db,
            claims["tenant_id"],
            reports_svc.parse_date(date),
            store_id=store_id or None,
        )
    )


@api.get("/reports/sales/monthly")
async def report_sales_monthly(
    # omit/`null` → current UTC year; <2000/>2100 → **422** (was free int)
    year: Annotated[int, Query(ge=2000, le=2100)] | None = None,
    # omit/`null` → current UTC month; <1/>12 → **422** (was free int)
    month: Annotated[int, Query(ge=1, le=12)] | None = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    return env(
        await reports_svc.sales_monthly(
            db,
            claims["tenant_id"],
            year or now.year,
            month or now.month,
            store_id=store_id or None,
        )
    )


@api.get("/reports/sales/products")
async def report_sales_products(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    # Optional category ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach category lookup).
    category_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-14.1 — product sales with optional store / category filters."""
    return env(
        await reports_svc.sales_by_product(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            store_id=store_id or None,
            category_id=category_id or None,
        )
    )


@api.get("/reports/sales/customers")
async def report_sales_customers(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    limit: int | None = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-14.1 — top customers by revenue and sale frequency."""
    return env(
        await reports_svc.sales_by_customer(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            store_id=store_id or None,
            limit=limit,
        )
    )


@api.get("/reports/sales/returns")
async def report_sales_returns(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Optional customer ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach party lookup).
    customer_id: Annotated[UuidIdValue | None, Query()] = None,
    reason: Annotated[SalesReturnReportReasonValue | None, Query()] = None,
    status: Annotated[ReturnReportStatusValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-14.1 — sales return summary by reason / customer."""
    return env(
        await reports_svc.sales_returns_summary(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            customer_id=customer_id or None,
            reason=reason,
            status=status,
            store_id=store_id or None,
        )
    )


@api.get("/reports/sales/salesperson")
async def report_sales_salesperson(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Optional department ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach department lookup).
    department_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.sales_by_salesperson(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            department_id=department_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/sales/by-store")
async def report_sales_by_store(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    department_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.sales_by_store(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            department_id=department_id or None,
        )
    )


@api.get("/reports/sales/by-department")
async def report_sales_by_department(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    department_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-2.5 — sales aggregated by seller department; optional department filter."""
    return env(
        await reports_svc.sales_by_department(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            department_id=department_id or None,
        )
    )


@api.get("/reports/inventory/balance")
async def report_inventory_balance(
    # Same UuidIdValue Query honesty as low-stock / expiry location filters.
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.inventory_balance(
            db,
            claims["tenant_id"],
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/inventory/valuation")
async def report_inventory_valuation(
    method: Annotated[InventoryValuationMethodValue, Query()] = "standard",
    # Same UuidIdValue Query honesty as low-stock / expiry / balance location filters.
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.inventory_valuation(
            db,
            claims["tenant_id"],
            method=method,
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/inventory/movements")
async def report_inventory_movements(
    # Same UuidIdValue Query honesty as GET /inventory/movements.
    product_id: Annotated[UuidIdValue | None, Query()] = None,
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    movement_type: Annotated[MovementTypeValue | None, Query()] = None,
    created_by: Annotated[UuidIdValue | None, Query()] = None,
    reason: Annotated[StockAdjustReasonValue | None, Query()] = None,
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
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
            movement_type=movement_type or None,
            created_by=created_by or None,
            reason=reason or None,
        )
    )


@api.get("/reports/inventory/low-stock")
async def report_low_stock(
    # Optional location filters ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/
    # `http://…`/non-UUID → **422** (was free `str`; garbage could reach store/warehouse lookup).
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.inventory_low_stock(
            db,
            claims["tenant_id"],
            store_id=store_id,
            warehouse_id=warehouse_id,
            company_id=claims.get("company_id"),
        )
    )


@api.get("/reports/transfers")
async def report_transfer_history(
    status: str | None = None,
    store_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    scope: str = "all",
    limit: int = 200,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 16 M2 — consolidated stock transfer history (inter-store + warehouse)."""
    return env(
        await stores_svc.transfer_history(
            db,
            claims["tenant_id"],
            status=status,
            store_id=store_id,
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            scope=scope,
            limit=limit,
            company_id=claims.get("company_id"),
        )
    )


@api.get("/reports/inventory/expiry")
async def report_inventory_expiry(
    # omit → 30; 0/negative/>365 → **422** (was free int; Reports UI max was 3650)
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    # Same UuidIdValue Query honesty as low-stock location filters.
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-14.2 — batches nearing expiry (pharmacy/food)."""
    return env(
        await reports_svc.inventory_expiry(
            db,
            claims["tenant_id"],
            within_days=days,
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/inventory/transfers")
async def report_inventory_transfers(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    status: Annotated[TransferReportStatusValue | None, Query()] = None,
    # Optional store filters ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/
    # non-UUID → **422** (was free `str`; garbage could reach store lookup).
    from_store_id: Annotated[UuidIdValue | None, Query()] = None,
    to_store_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-13.2 — inter-store transfer history and aggregates."""
    return env(
        await reports_svc.inventory_transfers(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            status=status,
            from_store_id=from_store_id or None,
            to_store_id=to_store_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/inventory/stock-counts")
async def report_inventory_stock_counts(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Same UuidIdValue Query honesty as other inventory report location filters.
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    variance_only: bool = True,
    status: Annotated[StockCountReportStatusValue, Query()] = "completed",
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-5.2 — physical stock count variance report."""
    return env(
        await reports_svc.inventory_stock_counts(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
            variance_only=variance_only,
            status=status,
        )
    )


@api.get("/reports/purchases/summary")
async def report_purchases_summary(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Optional location ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach warehouse/store lookup).
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.purchases_summary(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/purchases/suppliers")
async def report_purchases_suppliers(
    # Optional supplier ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach party lookup).
    supplier_id: Annotated[UuidIdValue | None, Query()] = None,
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
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
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/purchases/pending-orders")
async def report_purchases_pending_orders(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    supplier_id: Annotated[UuidIdValue | None, Query()] = None,
    status: Annotated[PendingPoReportStatusValue | None, Query()] = None,
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-14.3 — POs not yet fully received (draft/sent/partially_received)."""
    return env(
        await reports_svc.purchases_pending_orders(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            supplier_id=supplier_id or None,
            status=status,
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/purchases/returns")
async def report_purchases_returns(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    supplier_id: Annotated[UuidIdValue | None, Query()] = None,
    reason: Annotated[PurchaseReturnReportReasonValue | None, Query()] = None,
    status: Annotated[ReturnReportStatusValue | None, Query()] = None,
    warehouse_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-14.3 — purchase return summary by reason / supplier."""
    return env(
        await reports_svc.purchases_returns_summary(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            supplier_id=supplier_id or None,
            reason=reason,
            status=status,
            warehouse_id=warehouse_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/expenses/summary")
async def report_expenses_summary(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Optional filters ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach category/branch/department/store lookup).
    category_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    department_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.expenses_summary(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            category_id=category_id or None,
            branch_id=branch_id or None,
            department_id=department_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/reports/expenses/budget-vs-actual")
async def report_expenses_budget_vs_actual(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    category_id: Annotated[UuidIdValue | None, Query()] = None,
    branch_id: Annotated[UuidIdValue | None, Query()] = None,
    department_id: Annotated[UuidIdValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await reports_svc.budget_vs_actual(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            category_id=category_id or None,
            branch_id=branch_id or None,
            department_id=department_id or None,
            store_id=store_id or None,
        )
    )


@api.get("/credit/aging")
async def credit_aging(
    kind: Annotated[CreditAgingKindValue, Query()] = "receivable",
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    # Schema CreditAgingKindValue rejects blank/invalid → 422 (no silent AR for "Payable"/garbage).
    if kind == "payable":
        return env(
            await credit_svc.ap_aging(
                db, claims["tenant_id"], company_id=claims.get("company_id")
            )
        )
    return env(
        await credit_svc.ar_aging(
            db, claims["tenant_id"], company_id=claims.get("company_id")
        )
    )


@api.get("/credit/aging/export")
async def credit_aging_export(
    kind: str = "receivable",
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 136 A1 — aging document CSV (party/totals omitted; document rows only)."""
    text = await credit_ops_export_svc.export_aging_csv(
        db,
        tenant_id=claims["tenant_id"],
        kind=kind,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="credit_aging_export.csv"'},
    )


@api.get("/credit/customer-payments")
async def list_credit_customer_payments(
    customer_id: str | None = None,
    payment_method: str | None = None,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 136 C1 — tenant customer payment register."""
    rows = await credit_ops_export_svc.list_customer_payments(
        db,
        tenant_id=claims["tenant_id"],
        claims=claims,
        customer_id=customer_id,
        payment_method=payment_method,
    )
    return env([credit_ops_export_svc.serialize_customer_payment(r) for r in rows])


@api.get("/credit/customer-payments/export")
async def export_credit_customer_payments(
    customer_id: str | None = None,
    payment_method: str | None = None,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 136 C1 — customer payment header CSV."""
    text = await credit_ops_export_svc.export_customer_payments_csv(
        db,
        tenant_id=claims["tenant_id"],
        claims=claims,
        customer_id=customer_id,
        payment_method=payment_method,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="customer_payments_export.csv"'
        },
    )


@api.get("/credit/supplier-payments")
async def list_credit_supplier_payments(
    supplier_id: str | None = None,
    payment_method: str | None = None,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 136 S1 — tenant supplier payment register."""
    rows = await credit_ops_export_svc.list_supplier_payments(
        db,
        tenant_id=claims["tenant_id"],
        claims=claims,
        supplier_id=supplier_id,
        payment_method=payment_method,
    )
    return env([credit_ops_export_svc.serialize_supplier_payment(r) for r in rows])


@api.get("/credit/supplier-payments/export")
async def export_credit_supplier_payments(
    supplier_id: str | None = None,
    payment_method: str | None = None,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 136 S1 — supplier payment header CSV."""
    text = await credit_ops_export_svc.export_supplier_payments_csv(
        db,
        tenant_id=claims["tenant_id"],
        claims=claims,
        supplier_id=supplier_id,
        payment_method=payment_method,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="supplier_payments_export.csv"'
        },
    )


@api.get("/credit/settings")
async def credit_settings(
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(credit_svc.early_pay_settings(tenant))


@api.get("/credit/settings/export")
async def export_credit_settings(
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 138 C1 — early-pay settings CSV (tenant terms; no secrets)."""
    text = await approval_settings_export_svc.export_early_pay_settings_csv(
        db, tenant_id=claims["tenant_id"]
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="early_pay_settings_export.csv"'
        },
    )


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


@api.get("/credit/exchange-rates/export")
async def exchange_rates_export(
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 127 F1 — exchange rates CSV export."""
    text = await api_fx_schedule_export_svc.export_exchange_rates_csv(
        db,
        tenant_id=claims["tenant_id"],
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="exchange_rates_export.csv"'},
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
    # Path + body CurrencyCodeValue → 422 on blank/non-ISO (was late service **400**)
    currency_code: Annotated[CurrencyCodeValue, Path()],
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
    currency_code: Annotated[CurrencyCodeValue, Path()],
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import fx as fx_svc

    await fx_svc.delete_rate(db, claims["tenant_id"], currency_code)
    await db.commit()
    return env({"currency_code": currency_code.upper()}, "Exchange rate deleted")


@api.get("/credit/invoices/{invoice_id}/early-discount")
async def invoice_early_discount_quote(
    invoice_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    ep = credit_svc.early_pay_settings(tenant)
    inv = await sales_svc.get_invoice(db, claims["tenant_id"], invoice_id)
    workspace_svc.assert_record_company(claims, inv)
    quote = credit_svc.invoice_early_discount(
        inv,
        pct=ep["early_pay_discount_pct"],
        days=ep["early_pay_discount_days"],
    )
    return env({"invoice_id": inv.id, "invoice_number": inv.invoice_number, **quote})


@api.get("/credit/purchase-invoices/{invoice_id}/early-discount")
async def purchase_invoice_early_discount_quote(
    invoice_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    inv = await purchasing_svc.get_purchase_invoice(db, claims["tenant_id"], invoice_id)
    workspace_svc.assert_record_company(claims, inv)
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
    customer_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await credit_svc.customer_statement(
            db,
            claims["tenant_id"],
            customer_id,
            company_id=claims.get("company_id"),
        )
    )


@api.get("/credit/customers/{customer_id}/statement/export")
async def export_customer_credit_statement(
    customer_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 141 T1 — customer statement lines CSV."""
    text = await credit_ops_export_svc.export_customer_statement_csv(
        db,
        tenant_id=claims["tenant_id"],
        customer_id=customer_id,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="customer_statement_export.csv"'
        },
    )


@api.get("/customers/{customer_id}/history")
async def customer_history(
    customer_id: UuidIdValue,
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-7.1 — customer purchase / return / payment history."""
    return env(
        await credit_svc.customer_history(
            db,
            claims["tenant_id"],
            customer_id,
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.get("/credit/suppliers/{supplier_id}/statement")
async def supplier_credit_statement(
    supplier_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await credit_svc.supplier_statement(
            db,
            claims["tenant_id"],
            supplier_id,
            company_id=claims.get("company_id"),
        )
    )


@api.get("/credit/suppliers/{supplier_id}/statement/export")
async def export_supplier_credit_statement(
    supplier_id: str,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 141 T1 — supplier statement lines CSV."""
    text = await credit_ops_export_svc.export_supplier_statement_csv(
        db,
        tenant_id=claims["tenant_id"],
        supplier_id=supplier_id,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="supplier_statement_export.csv"'
        },
    )


@api.get("/suppliers/{supplier_id}/history")
async def supplier_history(
    supplier_id: UuidIdValue,
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-6.1 — supplier purchase / return / payment history."""
    return env(
        await credit_svc.supplier_history(
            db,
            claims["tenant_id"],
            supplier_id,
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
        )
    )


@api.patch("/customers/{customer_id}/credit-limit")
async def update_customer_credit_limit(
    customer_id: UuidIdValue,
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
    if payload.payment_terms_days is not None:
        customer.payment_terms_days = payload.payment_terms_days
    await db.commit()
    return env(
        {
            "id": customer.id,
            "name": customer.name,
            "credit_limit": money_json(customer.credit_limit),
            "payment_terms_days": int(customer.payment_terms_days or 30),
            "balance": money_json(customer.balance),
        }
    )


@api.get("/customers/{customer_id}/credit")
async def customer_credit(
    customer_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-7.1 — customer balance + credit limit + open credit sales."""
    return env(await credit_svc.customer_credit_info(db, claims["tenant_id"], customer_id))


@api.get("/customers/{customer_id}/outstanding")
async def customer_outstanding(
    customer_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == claims["tenant_id"],
                m.SalesInvoice.customer_id == customer_id,
                m.SalesInvoice.status.in_(["posted", "sent", "partial", "overdue"]),
            )
        )
    ).scalars().all()
    rows = []
    for inv in invoices:
        due = max(money_json(inv.total_amount) - money_json(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        rows.append(
            {
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": money_json(due),
                "due_date": inv.due_date,
                "status": inv.status,
            }
        )
    return env(rows)


@api.post("/customers/{customer_id}/payments")
async def customer_payment_alias(
    customer_id: UuidIdValue,
    payload: CustomerPaymentCreate,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = await customers_svc.get_customer(db, claims["tenant_id"], customer_id)
    workspace_svc.assert_record_company(claims, party)
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
        cheque_date=reports_svc.parse_date(payload.cheque_date),
        apply_early_discount=payload.apply_early_discount,
        liquid_account_id=payload.liquid_account_id,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(
        {
            "id": payment.id,
            "payment_number": payment.payment_number,
            "amount": money_json(payment.amount),
            "currency": getattr(payment, "currency", None) or "",
            "exchange_rate": money_json(getattr(payment, "exchange_rate", None), default=1),
            "fx_gain_loss": money_json(getattr(payment, "fx_gain_loss", 0) or 0),
        },
        "Payment recorded",
    )


@api.get("/suppliers/{supplier_id}/credit")
async def supplier_credit(
    supplier_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-6.1 — supplier outstanding payable balance + open bills."""
    return env(await credit_svc.supplier_credit_info(db, claims["tenant_id"], supplier_id))


@api.get("/suppliers/{supplier_id}/outstanding")
async def supplier_outstanding(
    supplier_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    schedule = await credit_svc.supplier_payment_schedule(
        db,
        claims["tenant_id"],
        supplier_id,
        company_id=claims.get("company_id"),
    )
    # Flat list kept for existing clients; schedule adds buckets/early-pay.
    out = []
    for inv in invoices:
        due = max(money_json(inv.total_amount) - money_json(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        out.append(
            {
                "purchase_invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "purchase_order_id": inv.purchase_order_id,
                "amount": money_json(due),
                "due_date": inv.due_date,
                "status": inv.status,
                "document_type": "purchase_invoice",
            }
        )
    invoiced_pos = {i.purchase_order_id for i in invoices if i.purchase_order_id}
    for po in orders:
        if po.id in invoiced_pos:
            continue
        due = max(money_json(po.total_amount) - money_json(po.paid_amount or 0), 0)
        if due <= 0:
            continue
        out.append(
            {
                "purchase_order_id": po.id,
                "po_number": po.po_number,
                "amount": money_json(due),
                "due_date": po.due_date,
                "status": po.status,
                "document_type": "purchase_order",
            }
        )
    return env(out)


@api.get("/suppliers/{supplier_id}/payment-schedule")
async def supplier_payment_schedule(
    supplier_id: UuidIdValue,
    claims=Depends(require_permission("credit", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import credit as credit_svc

    data = await credit_svc.supplier_payment_schedule(
        db, claims["tenant_id"], supplier_id
    )
    await db.commit()
    return env(data)


@api.post("/suppliers/{supplier_id}/payments")
async def supplier_payment(
    supplier_id: UuidIdValue,
    payload: SupplierPaymentCreate,
    claims=Depends(require_permission("credit", "write")),
    db: AsyncSession = Depends(get_db),
):
    party = await suppliers_svc.get_supplier(db, claims["tenant_id"], supplier_id)
    workspace_svc.assert_record_company(claims, party)
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
        cheque_date=reports_svc.parse_date(payload.cheque_date),
        liquid_account_id=payload.liquid_account_id,
        apply_early_discount=payload.apply_early_discount,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(
        {
            "id": payment.id,
            "payment_number": payment.payment_number,
            "amount": money_json(payment.amount),
            "early_payment_discount": money_json(
                getattr(payment, "early_payment_discount", 0) or 0
            ),
            "currency": getattr(payment, "currency", None) or "",
            "exchange_rate": money_json(getattr(payment, "exchange_rate", None), default=1),
            "fx_gain_loss": money_json(getattr(payment, "fx_gain_loss", 0) or 0),
        },
        "Supplier payment recorded",
    )


@api.get("/tax/rates")
async def taxes(
    is_active: bool | None = None,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List tax rates. Optional is_active filters soft-deactivated rows (Tax manage UI)."""
    stmt = (
        select(m.TaxRate)
        .where(m.TaxRate.tenant_id == claims["tenant_id"])
        .order_by(m.TaxRate.name)
    )
    if is_active is not None:
        stmt = stmt.where(m.TaxRate.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt)).scalars().all()
    return env([tax_svc.serialize_tax_rate(r) for r in rows])


@api.post("/tax/rates")
async def add_tax(
    payload: TaxCreate,
    claims=Depends(require_permission("tax", "write")),
    db: AsyncSession = Depends(get_db),
):
    company_id = claims.get("company_id")
    if payload.is_default:
        await tax_svc.clear_default_flags(db, claims["tenant_id"], company_id=company_id)
    data = payload.model_dump()
    data["tax_type"] = tax_svc.normalize_tax_type(data.get("tax_type"))
    data["pricing_mode"] = tax_svc.normalize_pricing_mode(data.get("pricing_mode"))
    comps = tax_svc.normalize_components(data.pop("components", None))
    if comps:
        data["components"] = comps
        data["rate"] = tax_svc.effective_rate_from_components(comps, data.get("rate") or 0)
    else:
        data["components"] = None
    data["name"] = require_honest_narrative(
        data.get("name"), label="tax rate name", max_length=80
    )
    tax = m.TaxRate(tenant_id=claims["tenant_id"], **data)
    db.add(tax)
    await db.commit()
    return env(tax_svc.serialize_tax_rate(tax), "Tax rate created")


@api.get("/tax/rates/export")
async def tax_rates_export(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 121 X1 — tax rates CSV export."""
    text = await location_export_svc.export_tax_rates_csv(
        db,
        tenant_id=claims["tenant_id"],
        is_active=is_active,
        active_only=active_only,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tax_rates_export.csv"'},
    )


@api.get("/tax/rates/{rate_id}")
async def get_tax_rate(
    rate_id: UuidIdValue,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    rate = await tax_svc.get_tax_rate(
        db, claims["tenant_id"], rate_id, company_id=claims.get("company_id")
    )
    return env(tax_svc.serialize_tax_rate(rate))


@api.patch("/tax/rates/{rate_id}")
async def patch_tax_rate(
    rate_id: UuidIdValue,
    payload: TaxUpdate,
    claims=Depends(require_permission("tax", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        rate = await tax_svc.get_tax_rate(db, claims["tenant_id"], rate_id)
        return env(tax_svc.serialize_tax_rate(rate), "No changes")
    clear_components = "components" in data and data.get("components") is None
    rate = await tax_svc.update_tax_rate(
        db,
        tenant_id=claims["tenant_id"],
        rate_id=rate_id,
        name=data.get("name"),
        rate=data.get("rate"),
        tax_type=data.get("tax_type"),
        pricing_mode=data.get("pricing_mode"),
        components=data.get("components") if "components" in data else None,
        clear_components=clear_components,
        is_reverse_charge=data.get("is_reverse_charge"),
        is_active=data.get("is_active"),
    )
    await db.commit()
    await db.refresh(rate)
    return env(tax_svc.serialize_tax_rate(rate), "Tax rate updated")


@api.post("/tax/rates/{rate_id}/default")
async def set_default_tax(
    rate_id: UuidIdValue,
    claims=Depends(require_permission("tax", "write")),
    db: AsyncSession = Depends(get_db),
):
    rate = await tax_svc.get_tax_rate(db, claims["tenant_id"], rate_id)
    if not rate.is_active:
        raise HTTPException(status_code=400, detail="Cannot set inactive tax rate as default")
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
    mode = payload.pricing_mode
    rate_pct = payload.rate
    components = payload.components
    is_rc = bool(payload.is_reverse_charge) if payload.is_reverse_charge is not None else False
    if payload.tax_rate_id:
        row = await tax_svc.get_tax_rate(db, claims["tenant_id"], payload.tax_rate_id)
        rate_pct = money_json(row.rate)
        mode = payload.pricing_mode or row.pricing_mode
        if components is None:
            components = row.components
        if payload.is_reverse_charge is None:
            is_rc = bool(row.is_reverse_charge)
    if rate_pct is None and not components:
        default = await tax_svc.get_default_tax_rate(
            db, claims["tenant_id"], company_id=company_id
        )
        if not default:
            raise HTTPException(status_code=400, detail="No tax rate available")
        rate_pct = money_json(default.rate)
        mode = payload.pricing_mode or default.pricing_mode
        if components is None:
            components = default.components
        if payload.is_reverse_charge is None:
            is_rc = bool(default.is_reverse_charge)
    if rate_pct is None:
        rate_pct = tax_svc.effective_rate_from_components(
            tax_svc.normalize_components(components), 0
        )
    mode = tax_svc.normalize_pricing_mode(mode)
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
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # Optional store ∈ UuidIdValue; omit/`null` → all; blank/`!!!`/`http://…`/non-UUID → **422**
    # (was free `str`; garbage could reach store lookup).
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await tax_svc.tax_report(
            db,
            claims["tenant_id"],
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            store_id=store_id or None,
        )
    )


@api.get("/reports/tax/filing")
async def reports_tax_filing(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # omit → tenant tax_jurisdiction (neutral pack if unsupported); blank/unsupported → 422
    jurisdiction: Annotated[TaxFilingJurisdictionValue | None, Query()] = None,
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import tax_filings as tax_filings_svc

    # Schema TaxFilingJurisdictionValue rejects blank/unknown → 422 (blank was silent omit).
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
                store_id=store_id or None,
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
                store_id=store_id or None,
            )
        )
    except HTTPException as exc:
        if exc.status_code == 400:
            pack = await tax_svc.tax_filing_pack(
                db,
                claims["tenant_id"],
                from_date=fd,
                to_date=td,
                store_id=store_id or None,
            )
            pack["jurisdiction"] = juris
            pack["government"] = None
            pack["supported_jurisdictions"] = tax_filings_svc.list_supported()
            return env(_with_period(pack))
        raise


@api.get("/taxes/rates")
async def taxes_alias(
    is_active: bool | None = None,
    claims=Depends(require_permission("tax", "read")),
    db: AsyncSession = Depends(get_db),
):
    return await taxes(is_active=is_active, claims=claims, db=db)


@api.get("/stores/entitlement")
async def stores_entitlement(
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Store usage + subscription entitlement for Multi-Store UI."""
    from app import store_entitlements as store_ent_svc

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(await store_ent_svc.get_store_usage(db, tenant))


@api.get("/stores")
async def stores(
    is_active: bool | None = None,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List stores. Optional is_active filters soft-deactivated rows (Multi-Store manage UI)."""
    from app import cash_drawer as cash_drawer_svc

    stmt = select(m.Store).where(m.Store.tenant_id == claims["tenant_id"])
    if is_active is not None:
        stmt = stmt.where(m.Store.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt)).scalars().all()
    return env(
        [
            stores_svc.serialize_store(
                s,
                drawer=cash_drawer_svc.serialize_drawer_settings(s),
            )
            for s in rows
        ]
    )


@api.post("/stores")
async def add_store(
    payload: StoreCreate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc
    from app import store_entitlements as store_ent_svc

    try:
        store = await stores_svc.create_store(
            db,
            tenant_id=claims["tenant_id"],
            name=payload.name,
            code=payload.code,
            address=payload.address,
            phone=payload.phone,
            manager_id=payload.manager_id,
            branch_id=payload.branch_id,
            operating_hours=(
                payload.operating_hours.model_dump(exclude_none=True)
                if payload.operating_hours is not None
                else None
            ),
        )
    except HTTPException as exc:
        if (
            isinstance(exc.detail, dict)
            and exc.detail.get("code") == store_ent_svc.STORE_LIMIT_REACHED
        ):
            await audit_svc.record_event(
                db,
                tenant_id=claims["tenant_id"],
                user_id=claims["sub"],
                module="stores",
                action="create_rejected_limit",
                entity="store",
                entity_id=None,
                details=dict(exc.detail),
            )
            await db.commit()
        raise
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="stores",
        action="create",
        entity="store",
        entity_id=store.id,
        details={"code": store.code, "name": store.name},
    )
    await db.commit()
    await db.refresh(store)
    return env(
        stores_svc.serialize_store(
            store,
            drawer=cash_drawer_svc.serialize_drawer_settings(store),
        ),
        "Store created with warehouse",
    )


@api.patch("/stores/{store_id}")
async def patch_store(
    store_id: UuidIdValue,
    payload: StoreUpdate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    data = payload.model_dump(exclude_unset=True)
    prev = await stores_svc.get_store(db, claims["tenant_id"], store_id)
    prev_active = bool(prev.is_active)
    store = await stores_svc.update_store(
        db,
        tenant_id=claims["tenant_id"],
        store_id=store_id,
        name=data.get("name"),
        address=data.get("address"),
        phone=data.get("phone"),
        manager_id=data.get("manager_id"),
        clear_manager=bool(data.get("clear_manager")),
        branch_id=data.get("branch_id"),
        clear_branch=bool(data.get("clear_branch")),
        is_active=data.get("is_active"),
        operating_hours=data.get("operating_hours"),
        set_operating_hours="operating_hours" in data,
    )
    if "is_active" in data and bool(store.is_active) != prev_active:
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="stores",
            action="activate" if store.is_active else "deactivate",
            entity="store",
            entity_id=store.id,
            details={"code": store.code, "old": prev_active, "new": bool(store.is_active)},
        )
    await db.commit()
    await db.refresh(store)
    return env(
        stores_svc.serialize_store(
            store,
            drawer=cash_drawer_svc.serialize_drawer_settings(store),
        ),
        "Store updated",
    )


@api.patch("/stores/{store_id}/drawer")
async def update_store_drawer(
    store_id: UuidIdValue,
    payload: StoreDrawerSettingsUpdate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    store = await stores_svc.get_store(
        db, claims["tenant_id"], store_id, company_id=claims.get("company_id")
    )
    data = payload.model_dump(exclude_unset=True)
    if "drawer_mode" in data and data["drawer_mode"] is not None:
        store.drawer_mode = cash_drawer_svc.normalize_mode(data["drawer_mode"])
    if "drawer_host" in data:
        raw_host = data["drawer_host"]
        if raw_host is None or not str(raw_host).strip():
            store.drawer_host = None
        else:
            # OpenAPI SmtpHostValue → 422; service defense-in-depth → 400.
            from app.schemas import validate_smtp_host_value

            try:
                store.drawer_host = validate_smtp_host_value(str(raw_host).strip())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    store_id: UuidIdValue,
    include_zero: bool = False,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await stores_svc.store_inventory(
            db,
            claims["tenant_id"],
            store_id,
            include_zero=include_zero,
            company_id=claims.get("company_id"),
        )
    )


@api.get("/stores/{store_id}/inventory/export")
async def store_inventory_export(
    store_id: str,
    include_zero: bool = False,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 155 I1 — store inventory / reorder CSV."""
    text = await location_export_svc.export_store_inventory_csv(
        db,
        tenant_id=claims["tenant_id"],
        store_id=store_id,
        include_zero=include_zero,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="store_{store_id}_inventory_export.csv"'
            )
        },
    )


@api.get("/stores/{store_id}/sales")
async def store_sales(
    store_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    recent_limit: int = 50,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await stores_svc.store_sales(
            db,
            claims["tenant_id"],
            store_id,
            from_date=reports_svc.parse_date(from_date),
            to_date=reports_svc.parse_date(to_date, end_of_day=True),
            recent_limit=recent_limit,
            company_id=claims.get("company_id"),
        )
    )


@api.get("/stores/{store_id}/sales/export")
async def store_sales_export(
    store_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    recent_limit: int = 50,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 155 S1 — store sales summary + recent lines CSV."""
    text = await location_export_svc.export_store_sales_csv(
        db,
        tenant_id=claims["tenant_id"],
        store_id=store_id,
        from_date=reports_svc.parse_date(from_date),
        to_date=reports_svc.parse_date(to_date, end_of_day=True),
        recent_limit=recent_limit,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="store_{store_id}_sales_export.csv"'
        },
    )


@api.put("/stores/{store_id}/reorder-policy")
async def set_store_reorder_policy(
    store_id: UuidIdValue,
    payload: StoreReorderPolicyUpdate,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    store = await stores_svc.get_store(
        db, claims["tenant_id"], store_id, company_id=claims.get("company_id")
    )
    workspace_svc.assert_record_company(claims, store)
    product = await catalog_svc.get_product(db, claims["tenant_id"], payload.product_id)
    workspace_svc.assert_record_company(claims, product)
    row = await stores_svc.set_store_reorder_policy(
        db,
        tenant_id=claims["tenant_id"],
        store_id=store_id,
        product_id=payload.product_id,
        minimum_stock=payload.minimum_stock,
        reorder_level=payload.reorder_level,
        reorder_qty=payload.reorder_qty,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(row, "Store reorder policy saved")


@api.get("/inventory/settings")
async def inventory_settings(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import numbering_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    return env(
        {
            "fefo_strict_warehouse": bool(getattr(tenant, "fefo_strict_warehouse", False)),
            "stock_transfer_numbering": numbering_settings(tenant, "stock_transfer"),
            "stock_count_numbering": numbering_settings(tenant, "stock_count"),
            "opening_stock_numbering": numbering_settings(tenant, "opening_stock"),
        }
    )


@api.get("/inventory/settings/export")
async def inventory_settings_export(
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 144 F1 — inventory FEFO settings CSV."""
    text = await ops_compliance_export_svc.export_fefo_settings_csv(
        db, tenant_id=claims["tenant_id"]
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="inventory_fefo_settings_export.csv"'
        },
    )


@api.patch("/inventory/settings")
async def update_inventory_settings(
    payload: InventoryFefoSettingsUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.doc_numbers import apply_numbering_update, numbering_settings

    tenant = await tenants_svc.get_tenant(db, claims["tenant_id"])
    if (
        payload.fefo_strict_warehouse is None
        and payload.stock_transfer_numbering is None
        and payload.stock_count_numbering is None
        and payload.opening_stock_numbering is None
    ):
        raise HTTPException(status_code=400, detail="No inventory settings to update")
    if payload.fefo_strict_warehouse is not None:
        tenant.fefo_strict_warehouse = bool(payload.fefo_strict_warehouse)
    if payload.stock_transfer_numbering is not None:
        apply_numbering_update(
            tenant,
            "stock_transfer",
            prefix=payload.stock_transfer_numbering.prefix,
            next_number=payload.stock_transfer_numbering.next_number,
        )
    if payload.stock_count_numbering is not None:
        apply_numbering_update(
            tenant,
            "stock_count",
            prefix=payload.stock_count_numbering.prefix,
            next_number=payload.stock_count_numbering.next_number,
        )
    if payload.opening_stock_numbering is not None:
        apply_numbering_update(
            tenant,
            "opening_stock",
            prefix=payload.opening_stock_numbering.prefix,
            next_number=payload.opening_stock_numbering.next_number,
        )
    await db.commit()
    return env(
        {
            "fefo_strict_warehouse": bool(getattr(tenant, "fefo_strict_warehouse", False)),
            "stock_transfer_numbering": numbering_settings(tenant, "stock_transfer"),
            "stock_count_numbering": numbering_settings(tenant, "stock_count"),
            "opening_stock_numbering": numbering_settings(tenant, "opening_stock"),
        },
        "Inventory settings updated",
    )


@api.get("/stores/transfers")
async def list_transfers(
    status: Annotated[TransferReportStatusValue | None, Query()] = None,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await stores_svc.list_transfers(
        db, claims["tenant_id"], status=status
    )
    return env([await stores_svc.serialize_transfer(db, t) for t in rows])


@api.get("/stores/transfers/export")
async def export_stores_transfers_csv(
    status: str | None = None,
    store_id: str | None = None,
    scope: str = "all",
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 135 T1 — stores-permission inter-store transfer header CSV (no line dump)."""
    text = await commerce_docs_export_svc.export_stock_transfers_csv(
        db,
        tenant_id=claims["tenant_id"],
        status=status,
        store_id=store_id,
        scope=scope,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="stores_transfers_export.csv"'
        },
    )


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
        from_warehouse_id=payload.from_warehouse_id,
        to_warehouse_id=payload.to_warehouse_id,
        items=[i.model_dump() for i in payload.items],
        notes=payload.notes,
        submit=payload.submit,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer created")


@api.get("/stores/transfers/{transfer_id}")
async def get_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    # Transfers are operationally shared (ship/receive); record scope is not applied.
    transfer = await stores_svc.get_transfer(db, claims["tenant_id"], transfer_id)
    return env(await stores_svc.serialize_transfer(db, transfer))


@api.post("/stores/transfers/{transfer_id}/submit")
async def submit_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.submit_transfer(
        db, tenant_id=claims["tenant_id"], transfer_id=transfer_id,
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer requested")


@api.post("/stores/transfers/{transfer_id}/approve")
async def approve_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.approve_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        actor_role=claims.get("role"),
    )
    await db.commit()
    data = await stores_svc.serialize_transfer(db, transfer)
    if data.get("fully_approved"):
        msg = "Transfer fully approved; ready to ship"
    elif data.get("awaiting_approval") == "dest":
        msg = "Source approved; awaiting destination manager"
    else:
        msg = "Transfer approved"
    return env(data, msg)


@api.post("/stores/transfers/{transfer_id}/reject")
async def reject_transfer(
    transfer_id: UuidIdValue,
    payload: StockTransferReject,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.reject_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        reason=payload.reason,
        actor_role=claims.get("role"),
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer rejected")


@api.post("/stores/transfers/{transfer_id}/ship")
async def ship_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.ship_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        role=claims.get("role") or "",
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer shipped")


@api.post("/stores/transfers/{transfer_id}/receive")
async def receive_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.receive_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        role=claims.get("role") or "",
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer received")


@api.post("/stores/transfers/{transfer_id}/cancel")
async def cancel_transfer(
    transfer_id: UuidIdValue,
    payload: StockTransferReject,
    claims=Depends(require_permission("stores", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.cancel_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer cancelled")


# --- Inventory aliases for stock transfers (BR-5.2 / BR-5.4) ---


@api.get("/inventory/stock-transfers")
async def inventory_list_transfers(
    status: Annotated[TransferReportStatusValue | None, Query()] = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await stores_svc.list_transfers(
        db, claims["tenant_id"], status=status
    )
    return env([await stores_svc.serialize_transfer(db, t) for t in rows])


@api.post("/inventory/stock-transfers")
async def inventory_create_transfer(
    payload: StockTransferCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.create_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        from_store_id=payload.from_store_id,
        to_store_id=payload.to_store_id,
        from_warehouse_id=payload.from_warehouse_id,
        to_warehouse_id=payload.to_warehouse_id,
        items=[i.model_dump() for i in payload.items],
        notes=payload.notes,
        submit=payload.submit,
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer created")


@api.get("/inventory/stock-transfers/{transfer_id}")
async def inventory_get_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.get_transfer(db, claims["tenant_id"], transfer_id)
    return env(await stores_svc.serialize_transfer(db, transfer))


@api.post("/inventory/stock-transfers/{transfer_id}/submit")
async def inventory_submit_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.submit_transfer(
        db, tenant_id=claims["tenant_id"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer requested")


@api.post("/inventory/stock-transfers/{transfer_id}/approve")
async def inventory_approve_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.approve_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        actor_role=claims.get("role"),
    )
    await db.commit()
    data = await stores_svc.serialize_transfer(db, transfer)
    if data.get("fully_approved"):
        msg = "Transfer fully approved; ready to ship"
    elif data.get("awaiting_approval") == "dest":
        msg = "Source approved; awaiting destination manager"
    else:
        msg = "Transfer approved"
    return env(data, msg)


@api.post("/inventory/stock-transfers/{transfer_id}/reject")
async def inventory_reject_transfer(
    transfer_id: UuidIdValue,
    payload: StockTransferReject,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.reject_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        reason=payload.reason,
        actor_role=claims.get("role"),
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer rejected")


@api.post("/inventory/stock-transfers/{transfer_id}/ship")
async def inventory_ship_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.ship_transfer(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer shipped")


@api.post("/inventory/stock-transfers/{transfer_id}/receive")
async def inventory_receive_transfer(
    transfer_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.receive_transfer(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"], transfer_id=transfer_id
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer received")


@api.post("/inventory/stock-transfers/{transfer_id}/cancel")
async def inventory_cancel_transfer(
    transfer_id: UuidIdValue,
    payload: StockTransferReject,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    transfer = await stores_svc.cancel_transfer(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        transfer_id=transfer_id,
        reason=payload.reason,
    )
    await db.commit()
    return env(await stores_svc.serialize_transfer(db, transfer), "Transfer cancelled")


@api.get("/stores/{store_id}")
async def get_store(
    store_id: UuidIdValue,
    claims=Depends(require_permission("stores", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import cash_drawer as cash_drawer_svc

    store = await stores_svc.get_store(db, claims["tenant_id"], store_id)
    return env(
        stores_svc.serialize_store(
            store,
            drawer=cash_drawer_svc.serialize_drawer_settings(store),
        )
    )


@api.get("/warehouses")
async def warehouses(
    is_active: bool | None = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List warehouses. Optional is_active filters soft-deactivated rows (Multi-Store manage UI)."""
    from app import warehouses as warehouses_svc

    stmt = select(m.Warehouse).where(m.Warehouse.tenant_id == claims["tenant_id"])
    if is_active is not None:
        stmt = stmt.where(m.Warehouse.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt)).scalars().all()
    return env([warehouses_svc.serialize_warehouse(r) for r in rows])


@api.get("/warehouses/{warehouse_id}")
async def get_warehouse(
    warehouse_id: UuidIdValue,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import warehouses as warehouses_svc

    row = await warehouses_svc.get_warehouse(db, claims["tenant_id"], warehouse_id)
    return env(warehouses_svc.serialize_warehouse(row))


@api.post("/warehouses")
async def add_warehouse(
    payload: WarehouseCreate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import warehouses as warehouses_svc

    warehouse = await warehouses_svc.create_warehouse(
        db,
        tenant_id=claims["tenant_id"],
        name=payload.name,
        code=payload.code,
        store_id=payload.store_id,
        warehouse_type=payload.warehouse_type,
        manager_id=payload.manager_id,
        address=payload.address,
        capacity=payload.capacity,
    )
    await db.commit()
    await db.refresh(warehouse)
    return env(warehouses_svc.serialize_warehouse(warehouse), "Warehouse created")


@api.patch("/warehouses/{warehouse_id}")
async def patch_warehouse(
    warehouse_id: UuidIdValue,
    payload: WarehouseUpdate,
    claims=Depends(require_permission("inventory", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import warehouses as warehouses_svc

    warehouse = await warehouses_svc.update_warehouse(
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
        clear_capacity=payload.clear_capacity,
        is_active=payload.is_active,
    )
    await db.commit()
    await db.refresh(warehouse)
    return env(warehouses_svc.serialize_warehouse(warehouse), "Warehouse updated")


@api.get("/reports/summary")
async def report(claims=Depends(require_permission("reports", "read")), db: AsyncSession = Depends(get_db)):
    dash = await dashboard(claims, db)
    now = datetime.utcnow()
    daily = await reports_svc.sales_daily(
        db, claims["tenant_id"], now, company_id=claims.get("company_id")
    )
    monthly = await reports_svc.sales_monthly(
        db, claims["tenant_id"], now.year, now.month, company_id=claims.get("company_id")
    )
    low = await reports_svc.inventory_low_stock(
        db, claims["tenant_id"], company_id=claims.get("company_id")
    )
    expenses = await reports_svc.expenses_summary(
        db, claims["tenant_id"], company_id=claims.get("company_id")
    )
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
    # omit → all statuses; blank/invalid → 422 (was free str; garbage silently empty list)
    status: Annotated[NotificationStatusValue | None, Query()] = None,
    # omit → all categories; blank/invalid → 422
    category: Annotated[NotificationCategoryValue | None, Query()] = None,
    # omit → 100; 0/negative/>200 → **422** (was free int; API silently clamped 1–200)
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    lim = max(1, min(int(limit or 100), 200))
    rows = await notifications_svc.list_notifications(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        status=status,
        category=category,
        limit=lim,
    )
    # Array payload preserved for existing clients; history window is HISTORY_DAYS (BR-4.4).
    return env([notifications_svc.serialize_notification(n) for n in rows])


@api.get("/notifications/export")
async def notifications_export(
    status: str | None = None,
    category: str | None = None,
    group: str | None = None,
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 129 N1 — notifications CSV honoring status/group/category filters."""
    text = await admin_ops_export_svc.export_notifications_csv(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        status=status,
        category=category,
        group=group,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="notifications_export.csv"'
        },
    )


@api.get("/notifications/unread-count")
async def notifications_unread_count(
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    count = await notifications_svc.unread_count(
        db, claims["tenant_id"], claims["sub"], company_id=claims.get("company_id")
    )
    return env({"count": count})


@api.patch("/notifications/{nid}/read")
async def notification_read(
    nid: UuidIdValue,
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    note = await notifications_svc.mark_read(
        db,
        tenant_id=claims["tenant_id"],
        notification_id=nid,
        user_id=claims["sub"],
        company_id=claims.get("company_id"),
    )
    await db.commit()
    return env(notifications_svc.serialize_notification(note), "Marked read")


@api.patch("/notifications/{nid}/unread")
async def notification_unread(
    nid: UuidIdValue,
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
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        company_id=claims.get("company_id"),
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


@api.get("/notifications/settings/export")
async def export_notification_settings(
    claims=Depends(require_permission("notifications", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 140 N1 — notification channel preferences CSV for the calling user."""
    text = await ops_settings_export_svc.export_notification_preferences_csv(
        db, tenant_id=claims["tenant_id"], user_id=claims["sub"]
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="notification_preferences_export.csv"'
        },
    )


@api.patch("/notifications/settings")
async def update_notification_settings(
    payload: NotificationPreferencesUpdate,
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    prefs = await notifications_svc.update_preferences(
        db,
        claims["tenant_id"],
        claims["sub"],
        payload.preferences.model_dump(exclude_none=True),
    )
    await db.commit()
    return env(prefs, "Notification preferences updated")


@api.post("/notifications/scan-due")
async def scan_due_notifications(
    claims=Depends(require_permission("notifications", "write")),
    db: AsyncSession = Depends(get_db),
):
    payment_due = await notifications_svc.scan_payment_due(db, claims["tenant_id"])
    quotation_expiry = await notifications_svc.scan_quotation_expiry(db, claims["tenant_id"])
    recurring_expense_due = await notifications_svc.scan_recurring_expense_due(
        db, claims["tenant_id"]
    )
    await db.commit()
    total = int(payment_due) + int(quotation_expiry) + int(recurring_expense_due)
    return env(
        {
            "created": total,
            "payment_due": payment_due,
            "quotation_expiry": quotation_expiry,
            "recurring_expense_due": recurring_expense_due,
        },
        f"Created {total} due notification(s)",
    )


@api.get("/jobs")
async def list_jobs(
    claims=Depends(require_roles("super_admin", "company_admin", "platform_owner")),
):
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
                "scan_recurring_expense_due_minutes": app_settings.CELERY_RECURRING_NOTIFY_INTERVAL_MINUTES,
                "generate_recurring_expenses_minutes": app_settings.CELERY_RECURRING_INTERVAL_MINUTES,
                "run_due_backups_minutes": app_settings.CELERY_BACKUP_INTERVAL_MINUTES,
                "scan_trial_lifecycle_minutes": app_settings.CELERY_TRIAL_INTERVAL_MINUTES,
                "run_due_report_emails_minutes": app_settings.CELERY_REPORT_EMAIL_INTERVAL_MINUTES,
                "refresh_fx_rates_minutes": app_settings.CELERY_FX_INTERVAL_MINUTES,
                "sync_bank_feeds_minutes": app_settings.CELERY_BANK_FEED_INTERVAL_MINUTES,
                "archive_cold_audit_logs_minutes": app_settings.CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES,
                "retry_due_webhooks_seconds": app_settings.CELERY_WEBHOOK_RETRY_INTERVAL_SECONDS,
                "scan_ai_security_alerts_minutes": app_settings.CELERY_AI_SECURITY_INTERVAL_MINUTES,
                "send_weekly_ai_insight_digest_schedule": "Monday 07:00 UTC",
            },
        }
    )


@api.get("/jobs/export")
async def jobs_catalog_export(
    claims=Depends(require_roles("super_admin", "company_admin")),
):
    """Stage 143 J1 — jobs catalog CSV (broker/result URLs never included)."""
    text = tenant_bootstrap_export_svc.export_jobs_catalog_csv()
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="jobs_catalog_export.csv"'},
    )


@api.post("/jobs/{job_name}/run")
async def run_job_now(
    job_name: Annotated[JobNameValue, Path()],
    enqueue: bool = False,
    claims=Depends(require_roles("super_admin", "platform_owner")),
):
    """Run a scheduled job immediately (sync) or enqueue to Celery."""
    from app import jobs as jobs_svc
    from app.config import settings as app_settings

    # Schema JobNameValue rejects unknown/blank path → 422 (was late **404**).
    # Keep allow-list defense-in-depth if Literal and JOB_HANDLERS drift.
    if job_name not in jobs_svc.JOB_HANDLERS:
        raise HTTPException(status_code=422, detail=f"Unknown job: {job_name}")

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
    user_id: Annotated[UuidIdValue | None, Query()] = None,
    module: Annotated[AuditModuleValue | None, Query()] = None,
    action: Annotated[AuditActionValue | None, Query()] = None,
    entity: Annotated[AuditEntityValue | None, Query()] = None,
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    # omit → 200; 0/negative/>1000 → **422** (was free int; service only capped at 1000)
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
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
        company_id=claims.get("company_id"),
    )
    return env([audit_svc.serialize_audit(r) for r in rows])


@api.get("/audit-logs/retention")
async def audit_logs_retention(
    claims=Depends(require_permission("audit", "read")),
):
    return env(audit_svc.retention_policy())


@api.get("/audit-logs/archives")
async def audit_logs_archives(
    # omit → 50; 0/negative/>200 → **422** (was free int; service capped at 200)
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = await audit_svc.list_cold_archives(
        db, tenant_id=claims["tenant_id"], limit=limit
    )
    return env([audit_svc.serialize_cold_archive(r) for r in rows])


@api.post("/audit-logs/archive-cold")
async def audit_logs_archive_cold(
    # omit/`null` → retention policy days; 0/negative/>3650 → **422** (was free int; service max(1, days))
    older_than_days: Annotated[int, Query(ge=1, le=3650)] | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    result = await audit_svc.archive_cold_logs(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        older_than_days=older_than_days,
    )
    await db.commit()
    msg = (
        f"Cold-archived {result['archived']} audit event(s)"
        if result.get("archived")
        else "No aged audit events to archive"
    )
    return env(result, msg)


@api.get("/audit-logs/export")
async def audit_logs_export(
    user_id: Annotated[UuidIdValue | None, Query()] = None,
    module: Annotated[AuditModuleValue | None, Query()] = None,
    action: Annotated[AuditActionValue | None, Query()] = None,
    entity: Annotated[AuditEntityValue | None, Query()] = None,
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
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
        limit=1000,
        company_id=claims.get("company_id"),
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


@api.get("/audit-logs/archives/export")
async def audit_logs_archives_export(
    claims=Depends(require_permission("audit", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 144 A1 — cold audit archive manifest CSV (no blob download)."""
    text = await ops_compliance_export_svc.export_audit_archives_csv(
        db, tenant_id=claims["tenant_id"]
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="audit_archives_export.csv"'
        },
    )


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
    log_id: UuidIdValue,
    claims=Depends(require_permission("audit", "read")),
):
    audit_svc.reject_mutation()


@api.patch("/audit-logs/{log_id}")
async def audit_logs_patch_blocked(
    log_id: UuidIdValue,
    claims=Depends(require_permission("audit", "read")),
):
    audit_svc.reject_mutation()


@api.get("/sync/status")
async def sync_status(
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Stage 164 Q1 — real queue counts (supersedes Stage 163 deferred-only status)."""
    return env(await sync_engine_svc.sync_status(db, claims["tenant_id"]))


@api.post("/sync/push")
async def sync_push(
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 164 P1 — device-scoped push ops (idempotent pos_sale via client_op_id)."""
    tenants_svc.assert_writable(claims)
    body = payload or {}
    data = await sync_engine_svc.push_ops(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        claims=claims,
        device_id=str(body.get("device_id") or ""),
        ops=body.get("ops") or [],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="pos",
        action="sync_push",
        entity="sync_queue",
        entity_id=str(body.get("device_id") or ""),
        details={"result_count": len(data.get("results") or [])},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(data, "Sync push processed")


@api.post("/sync/pull")
async def sync_pull(
    payload: dict | None = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 164 L1 — pending pull ops + bounded catalog snapshot."""
    body = payload or {}
    data = await sync_engine_svc.pull_ops(
        db,
        tenant_id=claims["tenant_id"],
        device_id=str(body.get("device_id") or ""),
        limit=int(body.get("limit") or 50),
        include_catalog=bool(body.get("include_catalog", True)),
    )
    await db.commit()
    return env(data, "Sync pull ready")


@api.post("/sync/ack")
async def sync_ack(
    payload: dict | None = None,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 164 A1 — acknowledge delivered sync ops."""
    body = payload or {}
    data = await sync_engine_svc.ack_ops(
        db,
        tenant_id=claims["tenant_id"],
        device_id=str(body.get("device_id") or ""),
        op_ids=body.get("op_ids") or [],
    )
    await db.commit()
    return env(data, "Sync ops acknowledged")


@api.get("/sync/conflicts")
async def sync_conflicts_list(
    status: str | None = "open",
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 164 C1 — list sync conflicts (default open)."""
    rows = await sync_engine_svc.list_conflicts(
        db, claims["tenant_id"], status=status
    )
    return env([sync_engine_svc.serialize_conflict(r) for r in rows])


@api.post("/sync/conflicts/{conflict_id}/resolve")
async def sync_conflicts_resolve(
    conflict_id: str,
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 165 R1 / Stage 166 A1 — resolve conflict; accept_client may re-apply safely."""
    tenants_svc.assert_writable(claims)
    body = payload or {}
    data = await sync_engine_svc.resolve_conflict(
        db,
        tenant_id=claims["tenant_id"],
        conflict_id=conflict_id,
        resolution=str(body.get("resolution") or ""),
        claims=claims,
        user_id=claims.get("sub"),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="pos",
        action="sync_conflict_resolve",
        entity="sync_conflict",
        entity_id=data["id"],
        details={
            "resolution": data.get("resolution"),
            "reapplied": data.get("reapplied"),
            "reapply_blocked_reason": data.get("reapply_blocked_reason"),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(data, data.get("message") or "Sync conflict resolved")


@api.get("/offline/devices")
async def offline_devices_list(
    status: str | None = None,
    active_only: bool = False,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 163 V1 — tenant offline device list (soft-revoke status)."""
    rows = await offline_devices_svc.list_devices(
        db, claims["tenant_id"], status=status, active_only=active_only
    )
    return env([offline_devices_svc.serialize_device(r) for r in rows])


@api.post("/offline/devices")
async def offline_devices_create(
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 163 V1 — register an offline/PWA device for this tenant."""
    tenants_svc.assert_writable(claims)
    body = payload or {}
    row = await offline_devices_svc.create_device(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        name=str(body.get("name") or ""),
        platform=body.get("platform"),
        user_agent=request.headers.get("user-agent"),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="company",
        action="offline_device_register",
        entity="offline_device",
        entity_id=row.id,
        details={
            "name": row.name,
            "device_code": row.device_code,
            "platform": row.platform,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(offline_devices_svc.serialize_device(row), "Offline device registered")


@api.get("/offline/devices/{device_id}")
async def offline_devices_get(
    device_id: str,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await offline_devices_svc.get_device(db, claims["tenant_id"], device_id)
    return env(offline_devices_svc.serialize_device(row))


@api.delete("/offline/devices/{device_id}")
async def offline_devices_revoke(
    device_id: str,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 163 V1 / Stage 168 R1 — soft-revoke; pending queue retained (not auto-applied)."""
    tenants_svc.assert_writable(claims)
    pending = await sync_engine_svc.device_pending_queue_stats(
        db, tenant_id=claims["tenant_id"], device_id=device_id
    )
    row = await offline_devices_svc.revoke_device(db, claims["tenant_id"], device_id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="company",
        action="offline_device_revoke",
        entity="offline_device",
        entity_id=row.id,
        details={
            "name": row.name,
            "device_code": row.device_code,
            "pending_queue": pending,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    data = offline_devices_svc.serialize_device(row)
    data["pending_queue"] = pending
    data["message"] = (
        "Offline device revoked (soft). Pending queue ops were not deleted or auto-applied; "
        "push/pull/ack remain blocked for this device (Stage 168 R1)."
    )
    return env(data, "Offline device revoked")


@api.get("/api-keys")
async def api_keys_list(
    status: str | None = None,
    active_only: bool = False,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 127 K1 — status / active_only for honest API-key status lists."""
    rows = await api_keys_svc.list_keys(
        db, claims["tenant_id"], status=status, active_only=active_only
    )
    return env([api_keys_svc.serialize_key(r) for r in rows])


@api.get("/api-keys/export")
async def api_keys_export(
    status: str | None = None,
    active_only: bool = False,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 127 K1 — API keys CSV export (raw secrets never included)."""
    text = await api_fx_schedule_export_svc.export_api_keys_csv(
        db,
        tenant_id=claims["tenant_id"],
        status=status,
        active_only=active_only,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="api_keys_export.csv"'},
    )


@api.post("/api-keys")
async def api_keys_create(
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create an API key. Raw secret is returned once in the response."""
    tenants_svc.assert_writable(claims)
    body = payload or {}
    expires_at = None
    raw_exp = body.get("expires_at")
    if raw_exp:
        try:
            expires_at = datetime.fromisoformat(str(raw_exp).replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="expires_at must be ISO-8601") from exc
    row, raw = await api_keys_svc.create_key(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        name=str(body.get("name") or ""),
        permissions=body.get("permissions"),
        expires_at=expires_at,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="api_key_create",
        entity="api_key",
        entity_id=row.id,
        details={"name": row.name, "key_prefix": row.key_prefix, "permissions": row.permissions},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(api_keys_svc.serialize_key(row, include_secret=raw), "API key created — store the secret now")


@api.get("/api-keys/{key_id}")
async def api_keys_get(
    key_id: str,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await api_keys_svc.get_key(db, claims["tenant_id"], key_id)
    return env(api_keys_svc.serialize_key(row))


@api.get("/api-keys/{key_id}/usage")
async def api_keys_usage(
    key_id: str,
    days: int = 30,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 7 K2 — request totals and per-day series for the usage chart."""
    return env(await api_keys_svc.usage_stats(db, claims["tenant_id"], key_id, days=days))


@api.get("/api-keys/{key_id}/usage/export")
async def api_keys_usage_export(
    key_id: str,
    days: int = 30,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 154 U1 — API key usage series CSV (no raw secrets)."""
    text = await api_fx_schedule_export_svc.export_api_key_usage_csv(
        db, tenant_id=claims["tenant_id"], key_id=key_id, days=days
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="api_key_{key_id}_usage_export.csv"'
        },
    )


@api.delete("/api-keys/{key_id}")
async def api_keys_revoke(
    key_id: str,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    row = await api_keys_svc.revoke_key(db, claims["tenant_id"], key_id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="api_key_revoke",
        entity="api_key",
        entity_id=row.id,
        details={"name": row.name, "key_prefix": row.key_prefix},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(api_keys_svc.serialize_key(row), "API key revoked")


@api.get("/webhooks")
async def webhooks_list(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 126 W1 — active_only / is_active for honest paused-only webhook lists."""
    rows = await webhooks_svc.list_endpoints(
        db,
        claims["tenant_id"],
        active_only=active_only,
        is_active=is_active,
    )
    return env([webhooks_svc.serialize_endpoint(r) for r in rows])


@api.get("/webhooks/export")
async def webhooks_export(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 126 X1 — webhooks CSV export (signing secrets excluded)."""
    text = await bank_webhook_export_svc.export_webhooks_csv(
        db,
        tenant_id=claims["tenant_id"],
        is_active=is_active,
        active_only=active_only,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="webhooks_export.csv"'},
    )


@api.get("/webhooks/deliveries")
async def webhooks_deliveries_list(
    webhook_id: str | None = None,
    status: str | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 144 W1 — webhook delivery attempt list (payload excluded)."""
    rows = await webhooks_svc.list_deliveries(
        db,
        claims["tenant_id"],
        webhook_id=webhook_id,
        status=status,
    )
    return env([webhooks_svc.serialize_delivery(r) for r in rows])


@api.get("/webhooks/deliveries/export")
async def webhooks_deliveries_export(
    webhook_id: str | None = None,
    status: str | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 144 W1 — webhook deliveries CSV (payload / secrets never included)."""
    text = await bank_webhook_export_svc.export_webhook_deliveries_csv(
        db,
        tenant_id=claims["tenant_id"],
        webhook_id=webhook_id,
        status=status,
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="webhook_deliveries_export.csv"'
        },
    )


@api.post("/webhooks")
async def webhooks_create(
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    body = payload or {}
    row, secret = await webhooks_svc.create_endpoint(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        url=str(body.get("url") or ""),
        events=body.get("events"),
        secret=body.get("secret"),
        description=body.get("description"),
        is_active=bool(body.get("is_active", True)),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_create",
        entity="webhook",
        entity_id=row.id,
        details={"url": row.url, "events": row.events},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        webhooks_svc.serialize_endpoint(row, include_secret=secret),
        "Webhook created — store the signing secret now",
    )


@api.get("/webhooks/{webhook_id}")
async def webhooks_get(
    webhook_id: str,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await webhooks_svc.get_endpoint(db, claims["tenant_id"], webhook_id)
    return env(webhooks_svc.serialize_endpoint(row))


@api.patch("/webhooks/{webhook_id}")
async def webhooks_patch(
    webhook_id: str,
    request: Request,
    payload: dict | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    body = payload or {}
    row, new_secret = await webhooks_svc.update_endpoint(
        db,
        claims["tenant_id"],
        webhook_id,
        url=body.get("url"),
        events=body.get("events"),
        description=body.get("description"),
        is_active=body.get("is_active"),
        rotate_secret=bool(body.get("rotate_secret")),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_update",
        entity="webhook",
        entity_id=row.id,
        details={"url": row.url, "events": row.events, "rotated_secret": bool(new_secret)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        webhooks_svc.serialize_endpoint(row, include_secret=new_secret),
        "Webhook updated",
    )


@api.delete("/webhooks/{webhook_id}")
async def webhooks_delete(
    webhook_id: str,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    await webhooks_svc.delete_endpoint(db, claims["tenant_id"], webhook_id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_delete",
        entity="webhook",
        entity_id=webhook_id,
        details={},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env({"id": webhook_id}, "Webhook deleted")


@api.post("/webhooks/{webhook_id}/test")
async def webhooks_test_delivery(
    webhook_id: str,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Send a signed webhook.test event to the endpoint (delivery proof)."""
    tenants_svc.assert_writable(claims)
    endpoint = await webhooks_svc.get_endpoint(db, claims["tenant_id"], webhook_id)
    delivery = await webhooks_svc.deliver_to_endpoint(
        db,
        endpoint,
        event="webhook.test",
        data={"message": "RIBDIGI webhook test ping"},
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_test",
        entity="webhook",
        entity_id=webhook_id,
        details={"delivery_id": delivery.id, "status": delivery.status},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(webhooks_svc.serialize_delivery(delivery), "Webhook test attempted")


@api.get("/onboarding/checklist")
async def onboarding_checklist_get(
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Stage 6 N2 — tenant onboarding checklist with auto-detected progress."""
    data = await onboarding_svc.build_checklist(db, claims["tenant_id"])
    return env(data)


@api.get("/onboarding/checklist/export")
async def onboarding_checklist_export(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 143 O1 — onboarding checklist CSV."""
    text = await tenant_bootstrap_export_svc.export_onboarding_checklist_csv(
        db, tenant_id=claims["tenant_id"]
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="onboarding_checklist_export.csv"'
        },
    )


@api.post("/onboarding/checklist/steps/{step_id}/skip")
async def onboarding_checklist_skip(
    step_id: str,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.skip_step(db, claims["tenant_id"], step_id)
    await db.commit()
    return env(data, "Step skipped")


@api.post("/onboarding/checklist/steps/{step_id}/unskip")
async def onboarding_checklist_unskip(
    step_id: str,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.unskip_step(db, claims["tenant_id"], step_id)
    await db.commit()
    return env(data, "Step restored")


@api.post("/onboarding/checklist/dismiss")
async def onboarding_checklist_dismiss(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss banner when progress ≥ 80% (or 100% complete)."""
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.dismiss(db, claims["tenant_id"])
    await db.commit()
    return env(data, "Onboarding checklist dismissed")


@api.post("/onboarding/checklist/restore")
async def onboarding_checklist_restore(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.restore(db, claims["tenant_id"])
    await db.commit()
    return env(data, "Onboarding checklist restored")


@api.get("/backup/settings")
async def backup_settings_get(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    workspace_svc.assert_tenant_workspace(claims)
    row = await backup_svc.get_or_create_settings(db, claims["tenant_id"])
    await db.commit()
    return env(backup_svc.serialize_settings(row))


@api.get("/backup/settings/export")
async def backup_settings_export(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 140 B1 — backup schedule settings CSV (no archive bytes / credentials)."""
    workspace_svc.assert_tenant_workspace(claims)
    text = await ops_settings_export_svc.export_backup_settings_csv(
        db, tenant_id=claims["tenant_id"]
    )
    await db.commit()
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="backup_settings_export.csv"'
        },
    )


@api.patch("/backup/settings")
async def backup_settings_patch(
    payload: BackupSettingsUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    row = await backup_svc.update_settings(
        db,
        claims["tenant_id"],
        enabled=data.get("enabled"),
        frequency=data.get("frequency"),
        retention_count=data.get("retention_count"),
        hour_utc=data.get("hour_utc"),
    )
    await db.commit()
    return env(backup_svc.serialize_settings(row), "Backup settings updated")


@api.get("/backup")
async def backup_list(
    status: Annotated[BackupJobStatusFilterValue | None, Query()] = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = await backup_svc.list_backups(db, claims["tenant_id"], status=status)
    return env([backup_svc.serialize_job(r) for r in rows])


@api.get("/backup/export")
async def backup_export(
    status: str | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 129 B1 — backup job metadata CSV (archive bytes not included)."""
    workspace_svc.assert_tenant_workspace(claims)
    status_n = (status or "").strip().lower() or None
    text = await admin_ops_export_svc.export_backup_jobs_csv(
        db, tenant_id=claims["tenant_id"], status=status_n
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="backup_jobs_export.csv"'},
    )


@api.post("/backup")
async def backup_create(
    request: Request,
    payload: BackupCreateBody | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    workspace_svc.assert_tenant_workspace(claims)
    backup_svc.ensure_backup_dir_writable()
    # Schema BackupCreateBody rejects unknown keys → 422.
    body = payload or BackupCreateBody()
    job = await backup_svc.create_backup(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        notes=body.notes,
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
    workspace_svc.assert_tenant_workspace(claims)
    result = await backup_svc.run_scheduled_backup_if_due(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub")
    )
    await db.commit()
    if result.get("ran"):
        return env(result, "Scheduled backup created")
    return env(result)


@api.get("/backup/{backup_id}")
async def backup_get(
    backup_id: UuidIdValue,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    workspace_svc.assert_tenant_workspace(claims)
    job = await backup_svc.get_backup(db, claims["tenant_id"], backup_id)
    return env(backup_svc.serialize_job(job))


@api.get("/backup/{backup_id}/download")
async def backup_download(
    backup_id: UuidIdValue,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    workspace_svc.assert_tenant_workspace(claims)
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


@api.post("/backup/{backup_id}/verify")
async def backup_verify(
    backup_id: UuidIdValue,
    request: Request,
    payload: BackupVerifyBody | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Decrypt backup and prove field match against live tenant data."""
    # Schema BackupVerifyBody rejects unknown keys / bad sample_limit → 422.
    body = payload or BackupVerifyBody()
    report = await backup_svc.verify_backup(
        db,
        tenant_id=claims["tenant_id"],
        backup_id=backup_id,
        sample_limit=body.sample_limit,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="backup",
        action="restore_verify",
        entity="backup_job",
        entity_id=backup_id,
        details={
            "proof_ok": (report.get("proof") or {}).get("ok"),
            "checked": (report.get("proof") or {}).get("checked"),
            "mismatch_count": (report.get("proof") or {}).get("mismatch_count"),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    msg = (
        "Backup verify passed"
        if (report.get("proof") or {}).get("ok")
        else "Backup verify found mismatches"
    )
    return env(report, msg)


@api.post("/backup/{backup_id}/restore")
async def backup_restore(
    backup_id: UuidIdValue,
    request: Request,
    payload: BackupRestoreBody | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    # Schema BackupRestoreBody rejects unknown keys / bad confirm_text → 422
    # (destructive apply without confirm_text="RESTORE" was late route 400).
    body = payload or BackupRestoreBody()
    dry_run = bool(body.dry_run)
    confirm = bool(body.confirm)
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
        details={
            "applied": report.get("applied"),
            "counts": report.get("record_counts"),
            "proof_ok": (report.get("proof") or {}).get("ok"),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    msg = "Restore dry-run completed" if report.get("dry_run") else "Restore applied"
    return env(report, msg)


@api.get("/api-keys")
async def api_keys_list(
    status: Annotated[ApiKeyStatusFilterValue | None, Query()] = None,
    active_only: bool = False,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = await api_keys_svc.list_keys(
        db, claims["tenant_id"], status=status, active_only=active_only
    )
    return env([api_keys_svc.serialize_key(r) for r in rows])


@api.post("/api-keys")
async def api_keys_create(
    request: Request,
    payload: ApiKeyCreate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    # Schema ApiKeyCreate rejects unknown keys / bad name / expires_at / modules → 422.
    row, raw = await api_keys_svc.create_key(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        name=payload.name,
        permissions=payload.permissions,
        expires_at=reports_svc.parse_datetime(payload.expires_at),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="api_key_create",
        entity="api_key",
        entity_id=row.id,
        details={"name": row.name, "key_prefix": row.key_prefix, "permissions": row.permissions},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        api_keys_svc.serialize_key(row, include_secret=raw),
        "API key created — store the secret now",
    )


@api.get("/api-keys/{key_id}")
async def api_keys_get(
    key_id: UuidIdValue,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await api_keys_svc.get_key(db, claims["tenant_id"], key_id)
    return env(api_keys_svc.serialize_key(row))


@api.get("/api-keys/{key_id}/usage")
async def api_keys_usage(
    key_id: UuidIdValue,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    return env(await api_keys_svc.usage_stats(db, claims["tenant_id"], key_id))


@api.delete("/api-keys/{key_id}")
async def api_keys_revoke(
    key_id: UuidIdValue,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app import tenants as tenants_svc

    tenants_svc.assert_writable(claims)
    row = await api_keys_svc.revoke_key(db, claims["tenant_id"], key_id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="api_key_revoke",
        entity="api_key",
        entity_id=row.id,
        details={"name": row.name, "key_prefix": row.key_prefix},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(api_keys_svc.serialize_key(row), "API key revoked")


@api.get("/webhooks")
async def webhooks_list(
    active_only: bool = False,
    is_active: bool | None = None,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = await webhooks_svc.list_endpoints(
        db,
        claims["tenant_id"],
        active_only=active_only,
        is_active=is_active,
    )
    return env([webhooks_svc.serialize_endpoint(r) for r in rows])


@api.post("/webhooks")
async def webhooks_create(
    request: Request,
    payload: WebhookCreate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    row, secret = await webhooks_svc.create_endpoint(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        url=payload.url,
        events=payload.events,
        secret=payload.secret,
        description=payload.description,
        is_active=payload.is_active,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_create",
        entity="webhook",
        entity_id=row.id,
        details={"url": row.url, "events": row.events},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        webhooks_svc.serialize_endpoint(row, include_secret=secret),
        "Webhook created — store the signing secret now",
    )


@api.get("/webhooks/{webhook_id}")
async def webhooks_get(
    webhook_id: UuidIdValue,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await webhooks_svc.get_endpoint(db, claims["tenant_id"], webhook_id)
    return env(webhooks_svc.serialize_endpoint(row))


@api.patch("/webhooks/{webhook_id}")
async def webhooks_patch(
    webhook_id: UuidIdValue,
    request: Request,
    payload: WebhookUpdate,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    data = payload.model_dump(exclude_unset=True)
    row, new_secret = await webhooks_svc.update_endpoint(
        db,
        claims["tenant_id"],
        webhook_id,
        url=data.get("url"),
        events=data.get("events"),
        description=data.get("description"),
        is_active=data.get("is_active"),
        rotate_secret=bool(data.get("rotate_secret")),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_update",
        entity="webhook",
        entity_id=row.id,
        details={"url": row.url, "events": row.events, "rotated_secret": bool(new_secret)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(
        webhooks_svc.serialize_endpoint(row, include_secret=new_secret),
        "Webhook updated",
    )


@api.delete("/webhooks/{webhook_id}")
async def webhooks_delete(
    webhook_id: UuidIdValue,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    await webhooks_svc.delete_endpoint(db, claims["tenant_id"], webhook_id)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_delete",
        entity="webhook",
        entity_id=webhook_id,
        details={},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env({"id": webhook_id}, "Webhook deleted")


@api.post("/webhooks/{webhook_id}/test")
async def webhooks_test_delivery(
    webhook_id: UuidIdValue,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Send a signed webhook.test event to the endpoint (delivery proof)."""
    tenants_svc.assert_writable(claims)
    endpoint = await webhooks_svc.get_endpoint(db, claims["tenant_id"], webhook_id)
    delivery = await webhooks_svc.deliver_to_endpoint(
        db,
        endpoint,
        event="webhook.test",
        data={"message": "RIBDIGI webhook test ping"},
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_test",
        entity="webhook",
        entity_id=webhook_id,
        details={"delivery_id": delivery.id, "status": delivery.status},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(webhooks_svc.serialize_delivery(delivery), "Webhook test attempted")


@api.get("/webhooks/{webhook_id}/deliveries")
async def webhooks_list_deliveries(
    webhook_id: UuidIdValue,
    status: Annotated[WebhookDeliveryStatusFilterValue | None, Query()] = None,
    # omit → 50; 0/negative/>200 → **422** (was free int; service silently clamped 1–200)
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Recent outbound delivery attempts for one webhook (Integrations UI)."""
    rows = await webhooks_svc.list_deliveries(
        db, claims["tenant_id"], webhook_id, status=status, limit=limit
    )
    return env([webhooks_svc.serialize_delivery(r) for r in rows])


@api.post("/webhooks/{webhook_id}/deliveries/{delivery_id}/retry")
async def webhooks_retry_delivery(
    webhook_id: UuidIdValue,
    delivery_id: UuidIdValue,
    request: Request,
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Manually retry a pending_retry or failed delivery."""
    tenants_svc.assert_writable(claims)
    delivery = await webhooks_svc.get_delivery(
        db, claims["tenant_id"], webhook_id, delivery_id
    )
    updated = await webhooks_svc.retry_delivery(db, delivery)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        module="security",
        action="webhook_delivery_retry",
        entity="webhook_delivery",
        entity_id=delivery_id,
        details={
            "webhook_id": webhook_id,
            "status": updated.status,
            "attempt_count": updated.attempt_count,
            "response_status": updated.response_status,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return env(webhooks_svc.serialize_delivery(updated), "Webhook delivery retry attempted")


@api.get("/onboarding/checklist")
async def onboarding_checklist_get(
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Tenant onboarding checklist with auto-detected progress."""
    data = await onboarding_svc.build_checklist(db, claims["tenant_id"])
    return env(data)


@api.post("/onboarding/checklist/steps/{step_id}/skip")
async def onboarding_checklist_skip(
    step_id: Annotated[OnboardingStepIdValue, Path()],
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    # Schema OnboardingStepIdValue rejects blank/unknown → 422 (was late service **400**).
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.skip_step(db, claims["tenant_id"], step_id)
    await db.commit()
    return env(data, "Step skipped")


@api.post("/onboarding/checklist/steps/{step_id}/unskip")
async def onboarding_checklist_unskip(
    step_id: Annotated[OnboardingStepIdValue, Path()],
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.unskip_step(db, claims["tenant_id"], step_id)
    await db.commit()
    return env(data, "Step restored")


@api.post("/onboarding/checklist/dismiss")
async def onboarding_checklist_dismiss(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss banner when progress ≥ 80% (or 100% complete)."""
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.dismiss(db, claims["tenant_id"])
    await db.commit()
    return env(data, "Onboarding checklist dismissed")


@api.post("/onboarding/checklist/restore")
async def onboarding_checklist_restore(
    claims=Depends(require_roles("company_admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    tenants_svc.assert_writable(claims)
    data = await onboarding_svc.restore(db, claims["tenant_id"])
    await db.commit()
    return env(data, "Onboarding checklist restored")


@api.get("/ai/status")
async def ai_status(claims=Depends(require_permission("ai", "read"))):
    """Operator-visible AI packaging status (never returns API keys)."""
    payload = ai_svc.status_payload()
    payload["security_monitor_enabled"] = ai_security_svc.monitor_enabled()
    payload["security_alert_threshold"] = ai_security_svc.alert_threshold()
    return env(payload)


@api.get("/ai/queries")
async def ai_queries(
    # omit → 50; 0/negative/>200 → **422** (was free int; service silently clamped 1–200)
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await ai_svc.list_queries(db, tenant_id=claims["tenant_id"], limit=limit)
    return env([ai_svc.serialize_query(r) for r in rows])


@api.get("/ai/security/alerts")
async def ai_security_alerts(
    # omit → 50; 0/negative/>200 → **422** (was free int; service silently clamped 1–200)
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    # omit/`null` → no floor; <0/>100 → **422** (was free int)
    min_score: Annotated[int, Query(ge=0, le=100)] | None = None,
    scan: bool = False,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List tenant-scoped AI Security Monitor alerts (BR-21.10)."""
    summary = None
    if scan:
        summary = await ai_security_svc.scan_tenant(
            db,
            tenant_id=claims["tenant_id"],
            actor_user_id=claims.get("sub"),
            notify=True,
        )
        await db.commit()
    rows = await ai_security_svc.list_alerts(
        db, tenant_id=claims["tenant_id"], limit=limit, min_score=min_score
    )
    return env(
        {
            "alerts": [ai_security_svc.serialize_alert(r) for r in rows],
            "scan": summary,
            "threshold": ai_security_svc.alert_threshold(),
            "enabled": ai_security_svc.monitor_enabled(),
        }
    )


@api.post("/ai/security/scan")
async def ai_security_scan(
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Run rule-based security detectors for the current tenant."""
    summary = await ai_security_svc.scan_tenant(
        db,
        tenant_id=claims["tenant_id"],
        actor_user_id=claims.get("sub"),
        notify=True,
    )
    await db.commit()
    return env(summary, "AI security scan completed")


@api.post("/ai/chat")
async def ai_chat(
    payload: AiChatBody,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    # Schema AiChatBody rejects unknown keys / blank message|prompt → 422.
    data = await ai_svc.handle_chat(db, claims=claims, payload=payload.model_dump())
    return env(data)


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
        company_id=claims.get("company_id"),
    )
    return env({"items": items})


@api.get("/ai/chat/history/export")
async def ai_chat_history_export(
    limit: int = 50,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Stage 148 C1 — current-user AI chat history CSV."""
    text = await ai_ops_export_svc.export_chat_history_csv(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        limit=limit,
        company_id=claims.get("company_id"),
    )
    return Response(
        content=text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="ai_chat_history_export.csv"'
        },
    )

@api.get("/ai/insights")
async def insights(claims=Depends(require_permission("ai", "read")), db: AsyncSession = Depends(get_db)):
    from app.dashboard import build_dashboard

    dash = await build_dashboard(db, claims["tenant_id"])
    data = await ai_svc.handle_insights(db, claims=claims, dash=dash)
    return env(data)


@api.post("/ai/insights/digest")
async def send_insight_digest(
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Email the current user a tenant-scoped preview of the weekly digest."""
    user_id = claims.get("sub") or claims.get("user_id")
    data = await ai_digest_svc.send_tenant_digest(
        db,
        tenant_id=claims["tenant_id"],
        actor_user_id=user_id,
        recipient_user_ids=[user_id] if user_id else [],
    )
    await db.commit()
    return env(data, f"Insight digest emailed to {data['sent']} recipient(s)")


@api.get("/ai/inventory/predictions")
async def ai_inventory_predictions(
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.3 rule-based demand / reorder / dead-stock intelligence."""
    data = await ai_inventory_svc.inventory_predictions(
        db, tenant_id=claims["tenant_id"], actor_user_id=claims.get("sub")
    )
    return env(data)


@api.get("/ai/inventory/low-stock-prediction")
async def ai_low_stock_prediction(
    # omit → 14; 0/negative/>90 → **422** (was free int; service silently clamped 1–90)
    days_ahead: Annotated[int, Query(ge=1, le=90)] = 14,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.4 predictive stockout list with confidence scores."""
    data = await ai_inventory_svc.low_stock_prediction(
        db,
        tenant_id=claims["tenant_id"],
        days_ahead=days_ahead,
        actor_user_id=claims.get("sub"),
    )
    return env(data)


@api.post("/ai/inventory/low-stock-prediction/requests")
async def ai_low_stock_prediction_requests(
    payload: AiLowStockPredictionRequestsBody | None = None,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Auto-generate draft purchase requests from prediction rows (BR-21.4)."""
    # Schema AiLowStockPredictionRequestsBody rejects unknown keys /
    # bad days_ahead|min_confidence → 422. Nested AiLowStockPredictionLine
    # rejects unknown line keys / blank product_id / bad qty|confidence → 422.
    body = payload or AiLowStockPredictionRequestsBody()
    lines: list = body.lines or []
    if not lines:
        pred = await ai_inventory_svc.low_stock_prediction(
            db,
            tenant_id=claims["tenant_id"],
            days_ahead=body.days_ahead,
            actor_user_id=claims.get("sub"),
        )
        lines = pred.get("at_risk") or []
    else:
        lines = [ln.model_dump() for ln in lines]
    from app import purchase_suggestions as purchase_suggestions_svc

    result = await purchase_suggestions_svc.create_requests_from_predictions(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        at_risk_lines=lines,
        notes=body.notes,
        min_confidence=body.min_confidence,
        include_open=body.include_open,
    )
    await db.commit()
    return env(result, f"Created {result.get('created_count', 0)} draft purchase request(s)")


@api.get("/ai/sales/analysis")
async def ai_sales_analysis(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.5 rule-based sales analysis (trend, RFM, affinity, peaks)."""
    data = await ai_sales_svc.sales_analysis(
        db,
        tenant_id=claims["tenant_id"],
        from_date=from_date,
        to_date=to_date,
        actor_user_id=claims.get("sub"),
    )
    return env(data)


@api.get("/ai/expenses/analysis")
async def ai_expenses_analysis(
    from_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    to_date: Annotated[IsoDateQueryValue | None, Query()] = None,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.6 rule-based expense analysis (budget, unusual, optimization)."""
    data = await ai_expenses_svc.expense_analysis(
        db,
        tenant_id=claims["tenant_id"],
        from_date=from_date,
        to_date=to_date,
        actor_user_id=claims.get("sub"),
    )
    return env(data)


@api.post("/ai/customer/assist")
async def ai_customer_assist(
    payload: AiCustomerAssistBody | None = None,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.9 rule-based customer assistant (churn, best, promos, balance)."""
    # Schema AiCustomerAssistBody rejects unknown keys → 422.
    body = payload or AiCustomerAssistBody()
    data = await ai_customer_svc.customer_assist(
        db,
        tenant_id=claims["tenant_id"],
        actor_user_id=claims.get("sub"),
        customer_id=body.customer_id,
        query=body.query or body.message,
    )
    return env(data)


@api.post("/ai/documents/analyze")
async def ai_documents_analyze(
    file: UploadFile = File(...),
    # None default (not "auto"): empty Form "" must 422, not silently become auto.
    document_type: Annotated[AiDocumentTypeValue | None, Form()] = None,
    # omit/`null` → no expected amount; nan/inf/out-of-range → **422** (was free float)
    expected_amount: Annotated[FiniteMoneyValue | None, Form()] = None,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.8 rule-based document OCR + party/PO match + discrepancy flags."""
    data = await ai_documents_svc.analyze_upload(
        db,
        tenant_id=claims["tenant_id"],
        actor_user_id=claims.get("sub"),
        upload=file,
        document_type=document_type or "auto",
        expected_amount=expected_amount,
    )
    return env(data, "Document analyzed — review before applying")


@api.post("/ai/documents/create-expense")
async def ai_documents_create_expense(
    payload: AiDocumentExpenseCreate,
    claims=Depends(require_permission("expenses", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft/pending expense from reviewed OCR fields (BR-21.8 Save as Expense)."""
    data = await ai_documents_svc.create_expense_from_extract(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        amount=payload.amount,
        payee=payload.payee,
        description=payload.description,
        reference=payload.reference,
        category_id=payload.category_id,
        category=payload.category,
        payment_method=payload.payment_method,
        expense_date=payload.expense_date,
        store_id=payload.store_id,
        branch_id=payload.branch_id,
        department_id=payload.department_id,
    )
    await db.commit()
    return env(data, "Draft expense created from document extract")


@api.post("/ai/documents/create-purchase-invoice")
async def ai_documents_create_purchase_invoice(
    payload: AiDocumentPurchaseInvoiceCreate,
    claims=Depends(require_permission("purchasing", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft purchase invoice from reviewed OCR + matched PO (BR-21.8)."""
    data = await ai_documents_svc.create_purchase_invoice_from_extract(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        purchase_order_id=payload.purchase_order_id,
        supplier_id=payload.supplier_id,
        supplier_invoice_number=payload.supplier_invoice_number,
        notes=payload.notes,
        is_reverse_charge=payload.is_reverse_charge,
        invoice_date=payload.invoice_date,
    )
    await db.commit()
    return env(data, "Draft purchase invoice created from document extract")


@api.post("/ai/reports/generate")
async def ai_reports_generate(
    payload: AiReportsGenerateBody,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    """BR-21.7 constrained NL / structured report generation (JSON preview)."""
    # Schema AiReportsGenerateBody rejects unknown keys / bad format|type /
    # missing prompt|template_id|report_type → 422.
    data = await ai_reports_svc.generate_report(
        db,
        tenant_id=claims["tenant_id"],
        actor_user_id=claims.get("sub"),
        prompt=payload.prompt,
        format=payload.format,
        template_id=payload.template_id,
        report_type=payload.report_type,
        period=payload.period,
        filters=payload.filters or payload.params,
    )
    return env(data, "Report generated")


@api.post("/ai/reports/export")
async def ai_reports_export(
    payload: AiReportsExportBody,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Export a generated AI report as csv/pdf/xlsx."""
    # Schema AiReportsExportBody rejects unknown keys / bad format|type /
    # missing prompt|template_id|report_type → 422.
    content, media, filename, _meta = await ai_reports_svc.export_from_intent(
        db,
        tenant_id=claims["tenant_id"],
        actor_user_id=claims.get("sub"),
        prompt=payload.prompt,
        format=payload.format,
        template_id=payload.template_id,
        report_type=payload.report_type,
        period=payload.period,
        params=payload.params or payload.filters,
    )
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/ai/reports/templates")
async def ai_report_templates_list(
    # omit → 50; 0/negative/>200 → **422** (was free int; service silently clamped 1–200)
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    claims=Depends(require_permission("ai", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await ai_reports_svc.list_templates(
        db, tenant_id=claims["tenant_id"], limit=limit
    )
    return env([ai_reports_svc.serialize_template(r) for r in rows])


@api.post("/ai/reports/templates")
async def ai_report_templates_create(
    payload: AiReportTemplateCreateBody,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    # Schema AiReportTemplateCreateBody rejects unknown keys / blank name|prompt /
    # bad format → 422.
    row = await ai_reports_svc.create_template(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        name=payload.name,
        prompt=payload.prompt,
        format=payload.format,
    )
    await db.commit()
    return env(ai_reports_svc.serialize_template(row), "Report template saved")


@api.delete("/ai/reports/templates/{template_id}")
async def ai_report_templates_delete(
    template_id: UuidIdValue,
    claims=Depends(require_permission("ai", "write")),
    db: AsyncSession = Depends(get_db),
):
    await ai_reports_svc.delete_template(
        db, tenant_id=claims["tenant_id"], template_id=template_id
    )
    await db.commit()
    return env({"id": template_id}, "Report template deleted")


# --- Hotel module ---


@api.get("/hotel/summary")
async def hotel_summary(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await hotel_svc.summary(db, tenant_id=claims["tenant_id"]))


@api.get("/hotel/availability")
async def hotel_availability(
    check_in_date: IsoDateQueryValue,
    check_out_date: IsoDateQueryValue,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await hotel_svc.availability(
        db,
        tenant_id=claims["tenant_id"],
        check_in_date=check_in_date,
        check_out_date=check_out_date,
    )
    return env([hotel_svc.serialize_room(r) for r in rows])


@api.get("/hotel/rooms")
async def hotel_rooms_list(
    is_active: bool | None = None,
    status: Annotated[HotelRoomStatusValue | None, Query()] = None,
    housekeeping_status: Annotated[HotelHousekeepingStatusValue | None, Query()] = None,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await hotel_svc.list_rooms(
        db,
        tenant_id=claims["tenant_id"],
        is_active=is_active,
        status=status,
        housekeeping_status=housekeeping_status,
    )
    return env([hotel_svc.serialize_room(r) for r in rows])


@api.post("/hotel/rooms")
async def hotel_rooms_create(
    payload: HotelRoomCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await hotel_svc.create_room(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        room_type=payload.room_type,
        floor=payload.floor,
        bed_type=payload.bed_type,
        max_occupancy=payload.max_occupancy,
        rate_amount=float(payload.rate_amount or 0),
        weekend_rate=float(payload.weekend_rate) if payload.weekend_rate is not None else None,
        extra_person_charge=float(payload.extra_person_charge or 0),
        amenities=payload.amenities,
        description=payload.description,
        status=payload.status,
        notes=payload.notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="room_created",
        entity="hotel_room",
        entity_id=row.id,
        details={"code": row.code},
    )
    await db.commit()
    return env(hotel_svc.serialize_room(row), "Room created")


@api.patch("/hotel/rooms/{room_id}")
async def hotel_rooms_update(
    room_id: UuidIdValue,
    payload: HotelRoomUpdate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    row = await hotel_svc.update_room(db, tenant_id=claims["tenant_id"], room_id=room_id, **data)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="room_updated",
        entity="hotel_room",
        entity_id=row.id,
        details={"code": row.code, "status": row.status},
    )
    await db.commit()
    return env(hotel_svc.serialize_room(row), "Room updated")


@api.get("/hotel/guests")
async def hotel_guests_list(
    is_active: bool | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await hotel_svc.list_guests(
        db, tenant_id=claims["tenant_id"], is_active=is_active, q=q
    )
    return env([hotel_svc.serialize_guest(r) for r in rows])


@api.post("/hotel/guests")
async def hotel_guests_create(
    payload: HotelGuestCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await hotel_svc.create_guest(
        db,
        tenant_id=claims["tenant_id"],
        full_name=payload.full_name,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
        address=payload.address,
        nationality=payload.nationality,
        id_type=payload.id_type,
        id_document=payload.id_document,
        emergency_contact=payload.emergency_contact,
        company_name=payload.company_name,
        preferences=payload.preferences,
        notes=payload.notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="guest_created",
        entity="hotel_guest",
        entity_id=row.id,
        details={"full_name": row.full_name},
    )
    await db.commit()
    return env(hotel_svc.serialize_guest(row), "Guest created")


@api.patch("/hotel/guests/{guest_id}")
async def hotel_guests_update(
    guest_id: UuidIdValue,
    payload: HotelGuestUpdate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    row = await hotel_svc.update_guest(
        db, tenant_id=claims["tenant_id"], guest_id=guest_id, **data
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="guest_updated",
        entity="hotel_guest",
        entity_id=row.id,
        details={"full_name": row.full_name},
    )
    await db.commit()
    return env(hotel_svc.serialize_guest(row), "Guest updated")


@api.get("/hotel/reservations")
async def hotel_reservations_list(
    status: Annotated[HotelReservationStatusValue | None, Query()] = None,
    list_kind: Annotated[HotelListKindValue | None, Query()] = None,
    on_date: IsoDateQueryValue | None = None,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await hotel_svc.list_reservations(
        db,
        tenant_id=claims["tenant_id"],
        status=status,
        list_kind=list_kind,
        on_date=on_date,
    )
    return env(
        [
            hotel_svc.serialize_reservation(r, room=room, guest=guest)
            for r, room, guest in rows
        ]
    )


@api.post("/hotel/reservations")
async def hotel_reservations_create(
    payload: HotelReservationCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    # Hold lock through commit so overlapping concurrent bookings serialize.
    async with hotel_svc.room_booking_lock(claims["tenant_id"], payload.room_id):
        row, room, guest = await hotel_svc.create_reservation(
            db,
            tenant_id=claims["tenant_id"],
            room_id=payload.room_id,
            guest_id=payload.guest_id,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date,
            adults=payload.adults,
            children=payload.children,
            nightly_rate=float(payload.nightly_rate) if payload.nightly_rate is not None else None,
            booking_source=payload.booking_source,
            special_requests=payload.special_requests,
            deposit_amount=float(payload.deposit_amount or 0),
            deposit_method=payload.deposit_method,
            notes=payload.notes,
            created_by=claims["sub"],
            walk_in=payload.walk_in,
        )
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="hotel",
            action="reservation_created",
            entity="hotel_reservation",
            entity_id=row.id,
            details={"reservation_number": row.reservation_number, "room_id": row.room_id},
        )
        await db.commit()
    return env(
        hotel_svc.serialize_reservation(row, room=room, guest=guest),
        "Reservation created",
    )


@api.post("/hotel/reservations/{reservation_id}/check-in")
async def hotel_reservation_check_in(
    reservation_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room, guest, folio = await hotel_svc.check_in(
        db,
        tenant_id=claims["tenant_id"],
        reservation_id=reservation_id,
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="checked_in",
        entity="hotel_reservation",
        entity_id=row.id,
        details={"reservation_number": row.reservation_number, "folio_id": folio.id},
    )
    await db.commit()
    return env(
        hotel_svc.serialize_reservation(
            row, room=room, guest=guest, folio_id=folio.id
        ),
        "Guest checked in",
    )


@api.post("/hotel/reservations/{reservation_id}/check-out")
async def hotel_reservation_check_out(
    reservation_id: UuidIdValue,
    payload: HotelCheckoutBody | None = None,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    allow = bool(payload.allow_balance) if payload else False
    row, room, guest, folio = await hotel_svc.check_out(
        db,
        tenant_id=claims["tenant_id"],
        reservation_id=reservation_id,
        allow_balance=allow,
        user_id=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="checked_out",
        entity="hotel_reservation",
        entity_id=row.id,
        details={
            "reservation_number": row.reservation_number,
            "room_id": row.room_id,
            "sales_invoice_id": getattr(folio, "sales_invoice_id", None) if folio else None,
        },
    )
    await db.commit()
    return env(
        hotel_svc.serialize_reservation(
            row, room=room, guest=guest, folio_id=folio.id if folio else None
        ),
        "Guest checked out",
    )


@api.post("/hotel/reservations/{reservation_id}/cancel")
async def hotel_reservation_cancel(
    reservation_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room, guest = await hotel_svc.cancel_reservation(
        db, tenant_id=claims["tenant_id"], reservation_id=reservation_id
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="reservation_cancelled",
        entity="hotel_reservation",
        entity_id=row.id,
        details={"reservation_number": row.reservation_number},
    )
    await db.commit()
    return env(hotel_svc.serialize_reservation(row, room=room, guest=guest), "Reservation cancelled")


@api.post("/hotel/reservations/{reservation_id}/no-show")
async def hotel_reservation_no_show(
    reservation_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room, guest = await hotel_svc.mark_no_show(
        db, tenant_id=claims["tenant_id"], reservation_id=reservation_id
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="reservation_no_show",
        entity="hotel_reservation",
        entity_id=row.id,
        details={"reservation_number": row.reservation_number},
    )
    await db.commit()
    return env(hotel_svc.serialize_reservation(row, room=room, guest=guest), "Marked no-show")


@api.post("/hotel/reservations/{reservation_id}/extend")
async def hotel_reservation_extend(
    reservation_id: UuidIdValue,
    payload: HotelExtendStay,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room, guest = await hotel_svc.extend_stay(
        db,
        tenant_id=claims["tenant_id"],
        reservation_id=reservation_id,
        new_check_out_date=payload.new_check_out_date,
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="stay_extended",
        entity="hotel_reservation",
        entity_id=row.id,
        details={"new_check_out_date": row.check_out_date.isoformat()},
    )
    await db.commit()
    return env(hotel_svc.serialize_reservation(row, room=room, guest=guest), "Stay extended")


@api.post("/hotel/reservations/{reservation_id}/move")
async def hotel_reservation_move(
    reservation_id: UuidIdValue,
    payload: HotelMoveRoom,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    async with hotel_svc.room_booking_lock(claims["tenant_id"], payload.new_room_id):
        row, room, guest = await hotel_svc.move_room(
            db,
            tenant_id=claims["tenant_id"],
            reservation_id=reservation_id,
            new_room_id=payload.new_room_id,
        )
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="hotel",
            action="room_moved",
            entity="hotel_reservation",
            entity_id=row.id,
            details={"new_room_id": row.room_id},
        )
        await db.commit()
    return env(hotel_svc.serialize_reservation(row, room=room, guest=guest), "Guest moved")


@api.get("/hotel/reservations/{reservation_id}/folio")
async def hotel_reservation_folio(
    reservation_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    folio = await hotel_svc.get_folio_for_reservation(
        db, tenant_id=claims["tenant_id"], reservation_id=reservation_id
    )
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found")
    folio, charges, payments = await hotel_svc.get_folio_detail(
        db, tenant_id=claims["tenant_id"], folio_id=folio.id
    )
    return env(hotel_svc.serialize_folio(folio, charges=charges, payments=payments))


@api.get("/hotel/folios/{folio_id}")
async def hotel_folio_get(
    folio_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    folio, charges, payments = await hotel_svc.get_folio_detail(
        db, tenant_id=claims["tenant_id"], folio_id=folio_id
    )
    return env(hotel_svc.serialize_folio(folio, charges=charges, payments=payments))


@api.post("/hotel/folios/{folio_id}/charges")
async def hotel_folio_add_charge(
    folio_id: UuidIdValue,
    payload: HotelFolioChargeCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await hotel_svc.add_folio_charge(
        db,
        tenant_id=claims["tenant_id"],
        folio_id=folio_id,
        charge_type=payload.charge_type,
        description=payload.description,
        quantity=payload.quantity,
        unit_amount=float(payload.unit_amount or 0),
        tax_amount=float(payload.tax_amount or 0),
        discount_amount=float(payload.discount_amount or 0),
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="folio_charge_added",
        entity="hotel_folio_charge",
        entity_id=row.id,
        details={"folio_id": folio_id, "line_total": float(row.line_total or 0)},
    )
    await db.commit()
    folio, charges, payments = await hotel_svc.get_folio_detail(
        db, tenant_id=claims["tenant_id"], folio_id=folio_id
    )
    return env(hotel_svc.serialize_folio(folio, charges=charges, payments=payments), "Charge posted")


@api.post("/hotel/folios/{folio_id}/charges/{charge_id}/void")
async def hotel_folio_void_charge(
    folio_id: UuidIdValue,
    charge_id: UuidIdValue,
    payload: HotelFolioChargeVoid,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await hotel_svc.void_folio_charge(
        db,
        tenant_id=claims["tenant_id"],
        charge_id=charge_id,
        void_reason=payload.void_reason,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="folio_charge_voided",
        entity="hotel_folio_charge",
        entity_id=row.id,
        details={"folio_id": folio_id, "void_reason": payload.void_reason},
    )
    await db.commit()
    folio, charges, payments = await hotel_svc.get_folio_detail(
        db, tenant_id=claims["tenant_id"], folio_id=folio_id
    )
    return env(hotel_svc.serialize_folio(folio, charges=charges, payments=payments), "Charge voided")


@api.post("/hotel/folios/{folio_id}/payments")
async def hotel_folio_add_payment(
    folio_id: UuidIdValue,
    payload: HotelFolioPaymentCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await hotel_svc.record_folio_payment(
        db,
        tenant_id=claims["tenant_id"],
        folio_id=folio_id,
        method=payload.method,
        amount=float(payload.amount),
        reference=payload.reference,
        notes=payload.notes,
        recorded_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="folio_payment_recorded",
        entity="hotel_folio_payment",
        entity_id=row.id,
        details={"folio_id": folio_id, "amount": float(row.amount or 0), "method": row.method},
    )
    await db.commit()
    folio, charges, payments = await hotel_svc.get_folio_detail(
        db, tenant_id=claims["tenant_id"], folio_id=folio_id
    )
    return env(
        hotel_svc.serialize_folio(folio, charges=charges, payments=payments),
        "Payment information recorded",
    )


@api.get("/hotel/housekeeping")
async def hotel_housekeeping_list(
    status: Annotated[str | None, Query(max_length=20)] = None,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await hotel_svc.list_housekeeping(db, tenant_id=claims["tenant_id"], status=status)
    return env(
        [
            hotel_svc.serialize_hk_task(t, room_code=room.code if room else None)
            for t, room in rows
        ]
    )


@api.post("/hotel/housekeeping")
async def hotel_housekeeping_create(
    payload: HotelHousekeepingCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room = await hotel_svc.create_housekeeping_task(
        db,
        tenant_id=claims["tenant_id"],
        room_id=payload.room_id,
        task_type=payload.task_type,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        notes=payload.notes,
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="housekeeping_task_created",
        entity="hotel_housekeeping_task",
        entity_id=row.id,
        details={"room_id": room.id},
    )
    await db.commit()
    return env(
        hotel_svc.serialize_hk_task(row, room_code=room.code),
        "Housekeeping task created",
    )


@api.post("/hotel/housekeeping/{task_id}/complete")
async def hotel_housekeeping_complete(
    task_id: UuidIdValue,
    payload: HotelHousekeepingComplete | None = None,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    mark = bool(payload.mark_inspected) if payload else False
    row, room = await hotel_svc.complete_housekeeping_task(
        db,
        tenant_id=claims["tenant_id"],
        task_id=task_id,
        mark_inspected=mark,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="housekeeping_task_completed",
        entity="hotel_housekeeping_task",
        entity_id=row.id,
        details={"room_id": room.id, "housekeeping_status": room.housekeeping_status},
    )
    await db.commit()
    return env(
        hotel_svc.serialize_hk_task(row, room_code=room.code),
        "Housekeeping task completed",
    )


@api.get("/hotel/maintenance")
async def hotel_maintenance_list(
    status: Annotated[str | None, Query(max_length=20)] = None,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await hotel_svc.list_maintenance(db, tenant_id=claims["tenant_id"], status=status)
    return env(
        [
            hotel_svc.serialize_maint(t, room_code=room.code if room else None)
            for t, room in rows
        ]
    )


@api.post("/hotel/maintenance")
async def hotel_maintenance_create(
    payload: HotelMaintenanceCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room = await hotel_svc.create_maintenance_ticket(
        db,
        tenant_id=claims["tenant_id"],
        room_id=payload.room_id,
        title=payload.title,
        priority=payload.priority,
        block_room=payload.block_room,
        assigned_to=payload.assigned_to,
        notes=payload.notes,
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="maintenance_ticket_created",
        entity="hotel_maintenance_ticket",
        entity_id=row.id,
        details={"room_id": room.id, "block_room": row.block_room},
    )
    await db.commit()
    return env(
        hotel_svc.serialize_maint(row, room_code=room.code),
        "Maintenance ticket created",
    )


@api.post("/hotel/maintenance/{ticket_id}/complete")
async def hotel_maintenance_complete(
    ticket_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, room = await hotel_svc.complete_maintenance_ticket(
        db, tenant_id=claims["tenant_id"], ticket_id=ticket_id
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="maintenance_ticket_completed",
        entity="hotel_maintenance_ticket",
        entity_id=row.id,
        details={"room_id": room.id, "room_status": room.status},
    )
    await db.commit()
    return env(
        hotel_svc.serialize_maint(row, room_code=room.code),
        "Maintenance ticket completed",
    )


@api.get("/fmcg/summary")
async def fmcg_summary(
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await fmcg_svc.summary(db, tenant_id=claims["tenant_id"]))


@api.get("/fmcg/expiring")
async def fmcg_expiring(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await fmcg_svc.list_near_expiry(db, tenant_id=claims["tenant_id"], within_days=days))


@api.get("/fmcg/routes/performance")
async def fmcg_routes_performance(
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(await fmcg_svc.route_performance(db, tenant_id=claims["tenant_id"]))


@api.get("/fmcg/schemes")
async def fmcg_schemes_list(
    is_active: bool | None = None,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await fmcg_svc.list_schemes(
        db, tenant_id=claims["tenant_id"], is_active=is_active
    )
    return env([fmcg_svc.serialize_scheme(r) for r in rows])


@api.post("/fmcg/schemes")
async def fmcg_schemes_create(
    payload: FmcgTradeSchemeCreate,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await fmcg_svc.create_scheme(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        scheme_type=payload.scheme_type,
        value=float(payload.value or 0),
        buy_qty=payload.buy_qty,
        get_qty=payload.get_qty,
        product_id=payload.product_id,
        category_id=payload.category_id,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        notes=payload.notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="scheme_created",
        entity="fmcg_trade_scheme",
        entity_id=row.id,
        details={"code": row.code, "scheme_type": row.scheme_type},
    )
    await db.commit()
    return env(fmcg_svc.serialize_scheme(row), "Trade scheme created")


@api.patch("/fmcg/schemes/{scheme_id}")
async def fmcg_schemes_set_active(
    scheme_id: UuidIdValue,
    payload: FmcgTradeSchemeActiveUpdate,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await fmcg_svc.set_scheme_active(
        db,
        tenant_id=claims["tenant_id"],
        scheme_id=scheme_id,
        is_active=payload.is_active,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="scheme_activated" if row.is_active else "scheme_deactivated",
        entity="fmcg_trade_scheme",
        entity_id=row.id,
        details={"code": row.code, "is_active": row.is_active},
    )
    await db.commit()
    return env(
        fmcg_svc.serialize_scheme(row),
        "Trade scheme activated" if row.is_active else "Trade scheme deactivated",
    )


@api.post("/fmcg/schemes/preview")
async def fmcg_schemes_preview(
    payload: FmcgSchemePreview,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await fmcg_svc.preview_active_schemes(
        db,
        tenant_id=claims["tenant_id"],
        line_qty=payload.line_qty,
        line_amount=float(payload.line_amount or 0),
        product_id=payload.product_id,
    )
    return env(rows)


@api.get("/fmcg/routes")
async def fmcg_routes_list(
    is_active: bool | None = None,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await fmcg_svc.list_routes(
        db, tenant_id=claims["tenant_id"], is_active=is_active
    )
    return env([fmcg_svc.serialize_route(route, stop_count=count) for route, count in rows])


@api.post("/fmcg/routes")
async def fmcg_routes_create(
    payload: FmcgRouteCreate,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await fmcg_svc.create_route(
        db,
        tenant_id=claims["tenant_id"],
        code=payload.code,
        name=payload.name,
        driver_name=payload.driver_name,
        vehicle=payload.vehicle,
        notes=payload.notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="route_created",
        entity="fmcg_route",
        entity_id=row.id,
        details={"code": row.code},
    )
    await db.commit()
    return env(fmcg_svc.serialize_route(row, stop_count=0), "Route created")


@api.get("/fmcg/routes/{route_id}/stops")
async def fmcg_route_stops_list(
    route_id: UuidIdValue,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await fmcg_svc.list_stops(
        db, tenant_id=claims["tenant_id"], route_id=route_id
    )
    return env(
        [fmcg_svc.serialize_stop(stop, customer_name=name) for stop, name in rows]
    )


@api.post("/fmcg/routes/{route_id}/stops")
async def fmcg_route_stops_create(
    route_id: UuidIdValue,
    payload: FmcgRouteStopCreate,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, customer_name = await fmcg_svc.add_stop(
        db,
        tenant_id=claims["tenant_id"],
        route_id=route_id,
        customer_id=payload.customer_id,
        sequence=payload.sequence,
        visit_day=payload.visit_day,
        notes=payload.notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="route_stop_added",
        entity="fmcg_route_stop",
        entity_id=row.id,
        details={"route_id": route_id, "customer_id": row.customer_id},
    )
    await db.commit()
    return env(
        fmcg_svc.serialize_stop(row, customer_name=customer_name),
        "Route stop added",
    )


@api.patch("/fmcg/stops/{stop_id}/delivery")
async def fmcg_stop_delivery_update(
    stop_id: UuidIdValue,
    payload: FmcgRouteStopDeliveryUpdate,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, customer_name = await fmcg_svc.update_stop_delivery(
        db,
        tenant_id=claims["tenant_id"],
        stop_id=stop_id,
        delivery_status=payload.delivery_status,
        fail_reason=payload.fail_reason,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="stop_delivery_updated",
        entity="fmcg_route_stop",
        entity_id=row.id,
        details={"delivery_status": row.delivery_status},
    )
    await db.commit()
    return env(
        fmcg_svc.serialize_stop(row, customer_name=customer_name),
        "Delivery status updated",
    )



@api.get("/hotel/settings")
async def hotel_settings_get(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await hotel_svc.get_or_create_settings(db, tenant_id=claims["tenant_id"])
    await db.commit()
    return env(hotel_svc.serialize_settings(row))


@api.patch("/hotel/settings")
async def hotel_settings_update(
    payload: HotelSettingsUpdate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await hotel_svc.update_settings(
        db, tenant_id=claims["tenant_id"], **payload.model_dump(exclude_unset=True)
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="settings_updated",
        entity="hotel_settings",
        entity_id=row.id,
        details={},
    )
    await db.commit()
    return env(hotel_svc.serialize_settings(row), "Hotel settings updated")


@api.post("/hotel/reservation-groups")
async def hotel_group_create(
    payload: HotelGroupReservationCreate,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    group, created = await hotel_svc.create_group_reservation(
        db,
        tenant_id=claims["tenant_id"],
        guest_id=payload.guest_id,
        room_ids=list(payload.room_ids),
        check_in_date=payload.check_in_date,
        check_out_date=payload.check_out_date,
        adults=payload.adults,
        children=payload.children,
        booking_source=payload.booking_source,
        name=payload.name,
        notes=payload.notes,
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="hotel",
        action="group_reservation_created",
        entity="hotel_reservation_group",
        entity_id=group.id,
        details={"group_number": group.group_number, "rooms": len(created)},
    )
    await db.commit()
    reservations = [
        hotel_svc.serialize_reservation(r, room=room, guest=guest)
        for r, room, guest in created
    ]
    return env(hotel_svc.serialize_group(group, reservations=reservations), "Group reservation created")


@api.get("/hotel/calendar")
async def hotel_calendar(
    start_date: IsoDateQueryValue,
    end_date: IsoDateQueryValue,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await hotel_svc.calendar(
            db,
            tenant_id=claims["tenant_id"],
            start_date=start_date,
            end_date=end_date,
        )
    )


@api.get("/hotel/reports")
async def hotel_reports(
    start_date: IsoDateQueryValue | None = None,
    end_date: IsoDateQueryValue | None = None,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return env(
        await hotel_svc.reports(
            db,
            tenant_id=claims["tenant_id"],
            start_date=start_date,
            end_date=end_date,
        )
    )


@api.get("/hotel/reservations/{reservation_id}/confirmation")
async def hotel_reservation_confirmation(
    reservation_id: UuidIdValue,
    format: Annotated[str, Query()] = "json",
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    data = await hotel_svc.reservation_confirmation(
        db, tenant_id=claims["tenant_id"], reservation_id=reservation_id
    )
    fmt = (format or "json").strip().lower()
    if fmt == "text":
        return PlainTextResponse(data["text"], media_type="text/plain; charset=utf-8")
    return env(data)


@api.get("/fmcg/dispatches")
async def fmcg_dispatches_list(
    route_id: UuidIdValue | None = None,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await fmcg_svc.list_dispatches(
        db, tenant_id=claims["tenant_id"], route_id=route_id
    )
    return env(
        [fmcg_svc.serialize_dispatch(d, route_code=code) for d, code in rows]
    )


@api.post("/fmcg/dispatches")
async def fmcg_dispatches_create(
    payload: FmcgDispatchCreate,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await fmcg_svc.create_dispatch(
        db,
        tenant_id=claims["tenant_id"],
        route_id=payload.route_id,
        dispatch_date=payload.dispatch_date,
        notes=payload.notes,
        created_by=claims["sub"],
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="dispatch_created",
        entity="fmcg_dispatch",
        entity_id=row.id,
        details={"dispatch_number": row.dispatch_number},
    )
    await db.commit()
    return env(fmcg_svc.serialize_dispatch(row), "Dispatch created")


@api.post("/fmcg/dispatches/{dispatch_id}/close")
async def fmcg_dispatches_close(
    dispatch_id: UuidIdValue,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await fmcg_svc.close_dispatch(
        db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="dispatch_closed",
        entity="fmcg_dispatch",
        entity_id=row.id,
        details={"dispatch_number": row.dispatch_number},
    )
    await db.commit()
    return env(fmcg_svc.serialize_dispatch(row), "Dispatch closed")


@api.get("/fmcg/assignments")
async def fmcg_assignments_list(
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await fmcg_svc.list_assignments(db, tenant_id=claims["tenant_id"])
    return env(
        [
            fmcg_svc.serialize_assignment(a, customer_name=cn, route_code=rc)
            for a, cn, rc in rows
        ]
    )


@api.post("/fmcg/assignments")
async def fmcg_assignments_upsert(
    payload: FmcgCustomerAssignmentUpsert,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    row, cn, rc = await fmcg_svc.upsert_customer_assignment(
        db,
        tenant_id=claims["tenant_id"],
        customer_id=payload.customer_id,
        route_id=payload.route_id,
        salesperson_name=payload.salesperson_name,
        notes=payload.notes,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="fmcg",
        action="customer_assigned",
        entity="fmcg_customer_assignment",
        entity_id=row.id,
        details={"customer_id": row.customer_id, "route_id": row.route_id},
    )
    await db.commit()
    return env(
        fmcg_svc.serialize_assignment(row, customer_name=cn, route_code=rc),
        "Customer assignment saved",
    )

