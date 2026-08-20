from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    AfterValidator,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.pos import coerce_payment_method_value
from app.rbac import SYSTEM_MODULES
from app.tenants import (
    coerce_date_format_value,
    coerce_decimal_separator_value,
    coerce_industry_value,
    coerce_tax_filing_period_value,
    coerce_thousand_separator_value,
    coerce_time_format_value,
)
from app.tax_filings import coerce_tax_filing_jurisdiction_value
from app.expenses import coerce_expense_payment_method_value
from app.print_branding import coerce_invoice_template_value, coerce_receipt_paper_value
from app.fx import coerce_currency_code_value

PosTenderMethod = Annotated[
    Literal["cash", "card", "wallet", "credit", "other"],
    BeforeValidator(coerce_payment_method_value),
]
PosSalePaymentMethod = Annotated[
    Literal["cash", "card", "wallet", "credit", "other", "split"],
    BeforeValidator(coerce_payment_method_value),
]
IndustryValue = Annotated[
    Literal[
        "retail",
        "pharmacy",
        "restaurant",
        "bakery",
        "wholesale",
        "manufacturing",
        "mart",
    ],
    BeforeValidator(coerce_industry_value),
]
TaxFilingPeriodValue = Annotated[
    Literal["monthly", "quarterly"],
    BeforeValidator(coerce_tax_filing_period_value),
]
# Keep aligned with app.tax_filings.SUPPORTED (Company profile + Tax filing Query/export).
TaxFilingJurisdictionValue = Annotated[
    Literal["GH"],
    BeforeValidator(coerce_tax_filing_jurisdiction_value),
]
# Keep aligned with app.fx.normalize_currency (Credit FX rates — 3-letter ISO).
CurrencyCodeValue = Annotated[
    str,
    BeforeValidator(coerce_currency_code_value),
    Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"),
]


def coerce_fiscal_year_start_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for pattern 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_fiscal_year_start_value(value: str) -> str:
    """AfterValidator: MM-DD with real calendar day (BR-10 / company profile)."""
    if not re.fullmatch(r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", value):
        raise ValueError("fiscal_year_start must be MM-DD")
    mm, dd = int(value[0:2]), int(value[3:5])
    # Prefer leap year so 02-29 is allowed; other invalid days still fail.
    year = 2024 if mm == 2 and dd == 29 else 2023
    try:
        date(year, mm, dd)
    except ValueError as exc:
        raise ValueError("fiscal_year_start must be a valid calendar MM-DD") from exc
    return value


# Keep aligned with app.accounting.parse_fiscal_mmdd (Company fiscal year start).
FiscalYearStartValue = Annotated[
    str,
    BeforeValidator(coerce_fiscal_year_start_value),
    AfterValidator(validate_fiscal_year_start_value),
]


def coerce_timezone_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_timezone_value(value: str) -> str:
    """AfterValidator: IANA timezone key via zoneinfo (Company profile)."""
    if not value:
        raise ValueError("timezone is required")
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(value)
    except Exception as exc:  # ZoneInfoNotFoundError / ValueError
        raise ValueError("timezone must be a valid IANA timezone") from exc
    return value


# Keep aligned with tenants.update_profile defense-in-depth ZoneInfo check.
TimezoneValue = Annotated[
    str,
    BeforeValidator(coerce_timezone_value),
    AfterValidator(validate_timezone_value),
]
DateFormatValue = Annotated[
    Literal["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"],
    BeforeValidator(coerce_date_format_value),
]
DecimalSeparatorValue = Annotated[
    Literal[".", ","],
    BeforeValidator(coerce_decimal_separator_value),
]
ThousandSeparatorValue = Annotated[
    Literal[",", ".", " ", ""],
    BeforeValidator(coerce_thousand_separator_value),
]
TimeFormatValue = Annotated[
    Literal["12h", "24h"],
    BeforeValidator(coerce_time_format_value),
]
InvoiceTemplateValue = Annotated[
    Literal["a4", "thermal"],
    BeforeValidator(coerce_invoice_template_value),
]
ReceiptPaperValue = Annotated[
    Literal["58mm", "80mm"],
    BeforeValidator(coerce_receipt_paper_value),
]
# Live print/receipt query params (BR-20.4 / BR-8) — same coerce as branding Literals.
InvoicePrintFormatValue = Annotated[
    Literal["pdf", "text", "json"],
    BeforeValidator(coerce_invoice_template_value),
]
ReceiptPrintFormatValue = Annotated[
    Literal["json", "text", "pdf"],
    BeforeValidator(coerce_invoice_template_value),
]
ReceiptChannelValue = Annotated[
    Literal["email", "sms"],
    BeforeValidator(coerce_invoice_template_value),
]
ExpensePaymentMethod = Annotated[
    Literal["cash", "bank_transfer", "card", "cheque"],
    BeforeValidator(coerce_expense_payment_method_value),
]
# Shared settlement allow-list for AR/AP (same as expenses).
SettlementPaymentMethod = ExpensePaymentMethod


def coerce_sales_return_settlement_method_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


SalesReturnSettlementMethod = Annotated[
    Literal["adjust", "refund"],
    BeforeValidator(coerce_sales_return_settlement_method_value),
]


def coerce_record_scope_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


RecordScopeValue = Annotated[
    Literal["own", "department", "branch", "all"],
    BeforeValidator(coerce_record_scope_value),
]


def coerce_package_code_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


PackageCodeValue = Annotated[
    Literal["trial", "starter", "professional", "enterprise"],
    BeforeValidator(coerce_package_code_value),
]

# Keep aligned with app.barcodes.SYMBOLOGIES (Inventory barcode select).
BarcodeSymbologyValue = Annotated[
    Literal["code128", "ean13", "upca"],
    BeforeValidator(coerce_package_code_value),
]

# Keep aligned with app.ai_documents.VALID_DOC_TYPES (AI Analyze document select).
AiDocumentTypeValue = Annotated[
    Literal["receipt", "invoice", "purchase_order", "auto"],
    BeforeValidator(coerce_package_code_value),
]

# Keep aligned with app.notifications.VALID_CATEGORIES / DEFAULT_PREFERENCES.
NotificationCategoryValue = Annotated[
    Literal[
        "low_stock",
        "expense_approval",
        "shift_variance",
        "credit_limit",
        "purchase_received",
        "payment_due",
        "quotation_expiry",
        "recurring_expense_due",
        "new_order",
        "transfer",
        "billing",
        "security",
        "system",
    ],
    BeforeValidator(coerce_package_code_value),
]
NotificationStatusValue = Annotated[
    Literal["unread", "read"],
    BeforeValidator(coerce_package_code_value),
]


# Must stay aligned with app.packages.PACKAGEABLE_MODULES (excludes platform).
PackageableModuleValue = Annotated[
    Literal[
        "dashboard",
        "company",
        "inventory",
        "sales",
        "pos",
        "purchasing",
        "expenses",
        "accounting",
        "credit",
        "tax",
        "stores",
        "reports",
        "notifications",
        "audit",
        "backup",
        "ai",
        "users",
        "security",
        "customers",
        "suppliers",
    ],
    BeforeValidator(coerce_package_code_value),
]


def coerce_platform_role_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


PlatformRoleValue = Annotated[
    Literal[
        "super_admin",
        "platform_owner",
        "platform_admin",
        "platform_support",
        "platform_finance",
    ],
    BeforeValidator(coerce_platform_role_value),
]

# System roles that may be cloned into a tenant custom role (excludes super_admin).
CustomRoleBaseRoleValue = Annotated[
    Literal[
        "platform_owner",
        "platform_admin",
        "platform_support",
        "platform_finance",
        "company_admin",
        "store_manager",
        "sales_officer",
        "inventory_officer",
        "accountant",
        "cashier",
    ],
    BeforeValidator(coerce_platform_role_value),
]
# Keep aligned with app.custom_roles.ALLOWED_ACTIONS / ApiKeyCreate actions.
ApiKeyPermissionAction = Literal["read", "write", "approve", "*"]

# Non-platform system roles for revoke fallback (excludes platform_* / super_admin).
AppFallbackRoleValue = Annotated[
    Literal[
        "company_admin",
        "store_manager",
        "sales_officer",
        "inventory_officer",
        "accountant",
        "cashier",
    ],
    BeforeValidator(coerce_platform_role_value),
]
# Keep aligned with app.rbac.VALID_ROLES / SYSTEM_ROLES (approval matrix roles[]).
SystemRoleValue = Annotated[
    Literal[
        "super_admin",
        "platform_owner",
        "platform_admin",
        "platform_support",
        "platform_finance",
        "company_admin",
        "store_manager",
        "sales_officer",
        "inventory_officer",
        "accountant",
        "cashier",
    ],
    BeforeValidator(coerce_platform_role_value),
]


def coerce_role_key_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for pattern 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def validate_role_key_value(value: str) -> str:
    """AfterValidator: shape only (custom_roles.ROLE_KEY_RE); unknown role stays service 400."""
    from app.custom_roles import ROLE_KEY_RE

    if not ROLE_KEY_RE.match(value):
        raise ValueError(
            "Role key must be lowercase letters/numbers/underscore, start with a letter (2–49 chars)"
        )
    return value


# Keep aligned with custom_roles.ROLE_KEY_RE (user assign + custom role key shape).
RoleKeyValue = Annotated[
    str,
    BeforeValidator(coerce_role_key_value),
    AfterValidator(validate_role_key_value),
]


def _require_credit_override_reason(model: BaseModel) -> BaseModel:
    """OpenAPI honesty (BR-11.1): reason required when override_credit_limit is true."""
    if bool(getattr(model, "override_credit_limit", False)):
        reason = (getattr(model, "override_reason", None) or "").strip()
        if not reason:
            raise ValueError(
                "override_reason is required when override_credit_limit is true"
            )
    return model


class ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Login(BaseModel):
    email: EmailStr
    password: str
    tenant_id: str
    totp_code: str | None = None


class TwoFactorConfirm(BaseModel):
    code: str


class TwoFactorVerify(BaseModel):
    challenge_token: str
    code: str


class TwoFactorDisable(BaseModel):
    password: str
    code: str


class WebAuthnRegisterVerify(BaseModel):
    credential: dict
    name: str | None = None


class WebAuthnLoginOptions(BaseModel):
    challenge_token: str


class WebAuthnLoginVerify(BaseModel):
    challenge_token: str
    credential: dict


class EmailTestRequest(BaseModel):
    to: EmailStr | None = None


class EmailSettingsUpdate(BaseModel):
    """PATCH /settings/email (BR-20.3).

    Unknown keys → **422** (`extra=forbid`). Optional `from_email` ∈ `EmailStr`;
    omit/`null` → no change; blank/`not-an-email` → **422** (was free `str`;
    blank/garbage were accepted into tenant SMTP config). Optional `host` ∈
    `SmtpHostValue`; omit/`null` → no change; blank/`http://…`/`not a host` → **422**
    (was free `str`; blank/garbage were accepted into tenant SMTP host). Optional
    `from_name` ∈ `SmtpFromNameValue`; omit/`null` → no change; blank/`!!!`/
    `http://…` → **422** (was free `str`; blank/garbage were accepted into
    tenant SMTP From display name). Optional `username` ∈ `SmtpUsernameValue`;
    omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    blank/garbage were accepted into tenant SMTP username; email-shaped logins OK).
    """

    model_config = ConfigDict(extra="forbid")

    host: SmtpHostValue | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: SmtpUsernameValue | None = None
    password: str | None = None
    clear_password: bool = False
    from_email: EmailStr | None = None
    from_name: SmtpFromNameValue | None = None
    use_tls: bool | None = None
    use_ssl: bool | None = None


class SmsTestRequest(BaseModel):
    """POST /settings/sms/test — optional override recipient.

    Optional `to` ∈ `E164PhoneValue`; omit/`null` → profile phone; blank/invalid → **422**
    (was free `str`; blank/garbage were accepted until send failed).
    """

    model_config = ConfigDict(extra="forbid")

    to: E164PhoneValue | None = None


class SmsSettingsUpdate(BaseModel):
    """PATCH /settings/sms (BR-15.2).

    Unknown keys → **422** (`extra=forbid`). Optional `from_number` ∈ `E164PhoneValue`
    (`+` + 8–15 digits); omit/`null` → no change; blank/`not-a-phone`/`123` → **422**
    (was free `str`; blank/garbage were accepted into tenant Twilio config). Optional
    `account_sid` ∈ `TwilioAccountSidValue` (strip; alphanumeric 1–64); omit/`null` →
    no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage were
    accepted into tenant Twilio SID). Not strict `AC`+32hex (fixtures use short SIDs).
    """

    model_config = ConfigDict(extra="forbid")

    account_sid: TwilioAccountSidValue | None = None
    auth_token: str | None = None
    clear_auth_token: bool = False
    from_number: E164PhoneValue | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank silently cleared phone; garbage was late **400** via normalize_phone).
    phone: E164PhoneValue | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TenantCreate(BaseModel):
    # Required trading name ∈ CompanyNameValue; blank/`!!!`/`http://…`/`X` → **422**
    # (was free `str` with no create-path length/content check).
    company_name: CompanyNameValue
    slug: str
    # BR-1.2 — schema Literal (+ case coerce via BeforeValidator); omit → retail;
    # blank/invalid → 422 (no silent retail from garbage).
    industry: IndustryValue = "retail"
    # BR-2.6 — same CurrencyCodeValue as FX rates; omit → GHS; blank/non-ISO → 422
    currency: CurrencyCodeValue = "GHS"
    admin_email: EmailStr
    admin_password: str


class TenantProfileUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…`/`X` → **422** (was free `str`;
    # blank/`X` late service **400**; garbage could persist). Required trading name.
    company_name: CompanyNameValue | None = None
    # omit = no change; blank/invalid → 422 (same IndustryValue Literal)
    industry: IndustryValue | None = None
    # omit = no change; blank/non-ISO → 422 (was free str; length-only late **400**)
    currency: CurrencyCodeValue | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank silently cleared company phone; garbage could persist).
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    # omit/`null` → no change; blank/`ftp://`/`not-a-url`/plain-http remote → **422**
    # (was free `str`; blank silently cleared; garbage like `www.x` could persist).
    # Same absolute http(s) honesty as Webhook/Bank feed URLs (`WebhookUrlValue`).
    website: WebhookUrlValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared HQ/billing/shipping; garbage could persist).
    address: AddressValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…`/`X` → **422** (was free `str`;
    # blank silently cleared; garbage could persist; len<2 or >200 was late **400**).
    legal_name: LegalNameValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared; garbage could persist; length>80 was late **400**).
    registration_number: RegistrationNumberValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared; garbage could persist; length>150 was late **400**).
    contact_person: ContactPersonValue | None = None
    # Same AddressValue honesty as HQ `address`.
    billing_address: AddressValue | None = None
    shipping_address: AddressValue | None = None
    # omit = no change; blank/non-IANA → 422 (was free str; blank late **400**; garbage could persist)
    timezone: TimezoneValue | None = None
    # omit = no change; blank/invalid MM-DD → 422 (was free str; length-only late **400**)
    fiscal_year_start: FiscalYearStartValue | None = None
    # Keep aligned with tax_filings.SUPPORTED / TaxFilingJurisdictionValue (Company select).
    # omit = no change; blank/unsupported → 422 (was free str; length-only late **400**).
    tax_jurisdiction: TaxFilingJurisdictionValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared TIN; garbage could persist). Max 40 (DB column).
    tax_registration_number: TaxRegistrationNumberValue | None = None
    # BR-20.2 / BR-12 — schema Literals; omit = no change; blank/invalid → 422
    tax_filing_period: TaxFilingPeriodValue | None = None
    date_format: DateFormatValue | None = None
    decimal_separator: DecimalSeparatorValue | None = None
    # "" / "none" = no thousand separator (valid)
    thousand_separator: ThousandSeparatorValue | None = None
    time_format: TimeFormatValue | None = None
    inactivity_timeout_minutes: int | None = Field(default=None, ge=5, le=480)


class TenantSuspendRequest(BaseModel):
    """Tenant suspend — typed reason required (honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class TenantSubscriptionAssign(BaseModel):
    # BR-1.x / platform — schema Literal (+ strip/lower); blank/invalid → 422
    # (was free str; service still defense-in-depth vs VALID_PACKAGE_CODES)
    package_code: PackageCodeValue
    term_value: int = Field(..., ge=1, le=120)
    # BR-1.x / platform — schema Literal; omit → months; blank/invalid → 422
    term_unit: Literal["months", "years"] = "months"
    # Optional start ∈ IsoDateQueryValue; omit/`null` → now; blank/invalid → **422**
    # (was free `datetime`; OpenAPI date-time; padded dates inconsistent).
    # API `reports.parse_date` remains defense-in-depth.
    start_at: IsoDateQueryValue | None = None
    activate: bool = True
    # Packageable modules Literal list; omit/null OK; blank/unknown/platform item → 422
    enabled_modules: list[PackageableModuleValue] | None = None
    # Platform store entitlement override; omit = no change; null clears to package default
    max_stores_override: int | None = Field(default=None, ge=0)
    clear_max_stores_override: bool = False


class TenantModulesUpdate(BaseModel):
    # Same Literal list as subscription assign; omit when reset_to_package
    enabled_modules: list[PackageableModuleValue] | None = None
    reset_to_package: bool = False


class TenantStoreLimitUpdate(BaseModel):
    """Company (== Tenant) store allocation within subscription entitlement."""

    # null = use full subscription entitlement
    store_limit: int | None = Field(default=None, ge=0)


class TenantMaxStoresOverrideUpdate(BaseModel):
    """Platform-owner per-tenant store entitlement override."""

    max_stores_override: int | None = Field(default=None, ge=0)
    clear: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    # Required display name ∈ UserFullNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; empty/whitespace/`!!!`/URL could persist).
    full_name: UserFullNameValue
    password: str
    # omit → cashier; blank/malformed key → 422 (was free str; blank late **400**)
    role: RoleKeyValue = "cashier"
    # omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/`garbage` could persist on create).
    phone: E164PhoneValue | None = None
    branch_id: str | None = None
    department_id: str | None = None
    # BR-3.3 — omit = role default; blank/invalid → 422 (no silent all from "")
    record_scope: RecordScopeValue | None = None


class UserUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # empty/whitespace/`!!!`/URL could persist).
    full_name: UserFullNameValue | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank silently cleared; garbage could persist).
    phone: E164PhoneValue | None = None
    # omit = no change; blank/malformed key → 422 (was free str; blank late **400**)
    role: RoleKeyValue | None = None
    is_active: bool | None = None
    password: str | None = None
    # Record visibility: own | department | branch | all (omit = no change; blank → 422)
    record_scope: RecordScopeValue | None = None
    branch_id: str | None = None
    department_id: str | None = None
    clear_branch: bool = False
    clear_department: bool = False


class PlatformGrantAccess(BaseModel):
    """Grant an existing app user access to the software-owner dashboard."""

    user_id: str
    # Platform roles Literal (+ strip/lower); omit → platform_support; blank/invalid → 422
    # (was free str; "" used to silently coerce to platform_support in service)
    role: PlatformRoleValue = "platform_support"


class PlatformStaffCreate(BaseModel):
    """Create a platform staff user on the software-owner workspace (BR-platform).

    Unknown keys → **422** (`extra=forbid`). `email` ∈ `EmailStr`; blank /
    `not-an-email` / too-short garbage → **422** (was free `str` with
    `min_length=3`; `"abc"` was accepted).
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    # Required display name ∈ PlatformStaffFullNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str` min_length=1; whitespace/`!!!`/URL could persist).
    full_name: PlatformStaffFullNameValue
    password: str = Field(min_length=1)
    # Same Literal as grant; omit → platform_support; blank/invalid → 422
    # (was free dict; API `role or "platform_support"` silently coerced "")
    role: PlatformRoleValue = "platform_support"
    # omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on platform staff create).
    phone: E164PhoneValue | None = None


class PlatformStaffUpdate(BaseModel):
    """Patch platform staff — omit = no change; blank role → 422."""

    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`
    # min_length=1; whitespace/`!!!`/URL could persist).
    full_name: PlatformStaffFullNameValue | None = None
    role: PlatformRoleValue | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on platform staff PATCH).
    phone: E164PhoneValue | None = None
    is_active: bool | None = None


class PlatformRevokeAccess(BaseModel):
    """Revoke software-owner dashboard access; keep the account as an app user."""

    # Non-platform system roles Literal (+ strip/lower); omit → company_admin;
    # blank/invalid/platform → 422 (was free str; "" silently coerced to company_admin)
    fallback_role: AppFallbackRoleValue = "company_admin"


class AccountCreate(BaseModel):
    # Required COA identity ∈ AccountCodeValue; blank/`!!!`/`a b`/`http://…` → **422**
    # (was free `str`; blank late service **400**; garbage could persist).
    code: AccountCodeValue
    # Required COA label ∈ AccountNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank late service **400**; garbage could persist).
    name: AccountNameValue
    # BR-10.3 / COA — schema Literal; omit → asset; blank/invalid → 422
    account_type: Literal["asset", "liability", "equity", "income", "expense"] = "asset"
    # omit/null = non-liquid; blank/invalid → 422 (no silent None from "")
    liquid_kind: Literal["cash", "bank"] | None = None
    # omit/`null` → no name; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silent→null then late service **400** when liquid_kind=bank).
    bank_name: BankNameValue | None = None
    # omit/`null` → no number; blank/`not-an-account`/`http://…` → **422**
    # (was free `str`; blank silent→null; garbage could persist on liquid bank COA).
    account_number: BankAccountNumberValue | None = None
    # omit/`null` → no branch; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silent→null; garbage could persist).
    bank_branch: BankBranchValue | None = None


class AccountUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank late service **400**; garbage could persist on COA display name).
    name: AccountNameValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silent→null; garbage could persist; clearing bank_name on a bank
    # account still fails service required-name **400**).
    bank_name: BankNameValue | None = None
    # omit/`null` → no change; blank/`not-an-account`/`http://…` → **422**
    # (was free `str`; blank silent→null; garbage could persist).
    account_number: BankAccountNumberValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silent→null; garbage could persist).
    bank_branch: BankBranchValue | None = None
    is_active: bool | None = None


class OpeningBalanceLine(BaseModel):
    account_id: str | None = None
    account_code: str | None = None
    amount: float = Field(gt=0)


class OpeningBalanceCreate(BaseModel):
    lines: list[OpeningBalanceLine] = Field(min_length=1)
    # omit/`null` → auto COA-OPEN-YYYYMMDD; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank silently auto-labeled / garbage could persist on journal reference).
    reference: OpeningBalanceReferenceValue | None = None
    # omit/`null` → default journal description; blank/`!!!`/`http://…` → **422** (was
    # free `str`; blank fell through to default / garbage could persist on description).
    notes: OpeningBalanceNotesValue | None = None


class CashTransferCreate(BaseModel):
    # BR-10.3 — schema Literal; omit defaults to transfer; blank/invalid → 422
    kind: Literal["transfer", "deposit", "withdrawal"] = "transfer"
    from_account_id: str | None = None
    to_account_id: str | None = None
    amount: float = Field(gt=0)
    # omit/`null` → auto XFER-YYYY-NNNN; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank silently auto-numbered / garbage could persist).
    reference: CashTransferReferenceValue | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on CashTransfer.notes Text).
    notes: CashTransferNotesValue | None = None


class BranchCreate(BaseModel):
    code: str
    # Required branch label ∈ BranchNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on multi-store branch create).
    name: BranchNameValue
    # omit/`null` → no address; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on create). Same AddressValue as Company/Store.
    address: AddressValue | None = None
    # omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on create).
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    manager_id: str | None = None


class BranchUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on branch display name).
    name: BranchNameValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared; garbage could persist). Same AddressValue as Company/Store.
    address: AddressValue | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank silently cleared; garbage could persist).
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    manager_id: str | None = None
    clear_manager: bool = False
    is_active: bool | None = None


class DepartmentCreate(BaseModel):
    code: str
    # Required department label ∈ DepartmentNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on multi-store department create).
    name: DepartmentNameValue
    branch_id: str | None = None
    head_user_id: str | None = None


class DepartmentUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on department display name).
    name: DepartmentNameValue | None = None
    branch_id: str | None = None
    clear_branch: bool = False
    head_user_id: str | None = None
    clear_head: bool = False
    is_active: bool | None = None


class CustomRoleCreate(BaseModel):
    """POST /roles — typed custom role create (BR-3.2).

    Unknown top-level keys → **422** (`extra=forbid`). `permissions` map modules ∈
    ASSIGNABLE_MODULES with actions ∈ read|write|approve|*; empty map / unknown
    module|action / `*:*` → **422** (was late service **400**). Omit `permissions`
    when cloning via `base_role`.
    """

    model_config = ConfigDict(extra="forbid")

    # Shape via RoleKeyValue → 422 on blank/malformed; collision/super_/system stay service **400**
    key: RoleKeyValue
    # Required display label ∈ CustomRoleLabelValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on custom role create).
    label: CustomRoleLabelValue
    permissions: dict[str, list[ApiKeyPermissionAction]] | None = None
    # Clone-from system role; omit/null OK when permissions set; blank/unknown/super_admin → 422
    base_role: CustomRoleBaseRoleValue | None = None
    # BR-3.3 — omit = base_role/own default; blank/invalid → 422
    record_scope: RecordScopeValue | None = None

    @field_validator("permissions", mode="before")
    @classmethod
    def _normalize_permissions_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        out: dict[str, list[object]] = {}
        for module, actions in value.items():
            mod = str(module).strip().lower() if module is not None else module
            if isinstance(actions, (list, tuple)):
                out[mod] = [
                    a.strip().lower() if isinstance(a, str) else a for a in actions
                ]
            else:
                out[mod] = actions  # type: ignore[assignment]
        return out

    @model_validator(mode="after")
    def _permissions_modules(self) -> CustomRoleCreate:
        if self.permissions is None:
            return self
        from app.custom_roles import ASSIGNABLE_MODULES

        if not self.permissions:
            raise ValueError("permissions must include at least one module")
        if self.permissions.get("*") == ["*"] or "*" in (self.permissions.get("*") or []):
            raise ValueError("Custom roles cannot grant wildcard *:*")
        for module, actions in self.permissions.items():
            if module not in ASSIGNABLE_MODULES:
                raise ValueError(f"Unknown or disallowed module '{module}'")
            if not actions:
                raise ValueError(f"Module '{module}' actions must be a non-empty list")
        return self


class CustomRoleUpdate(BaseModel):
    """PATCH /roles/{role} — typed custom role update (BR-3.2).

    Unknown top-level keys → **422** (`extra=forbid`). Same `permissions` honesty as
    create when the map is sent (omit = no change).
    """

    model_config = ConfigDict(extra="forbid")

    label: CustomRoleLabelValue | None = None
    permissions: dict[str, list[ApiKeyPermissionAction]] | None = None
    record_scope: RecordScopeValue | None = None
    is_active: bool | None = None

    @field_validator("permissions", mode="before")
    @classmethod
    def _normalize_permissions_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        out: dict[str, list[object]] = {}
        for module, actions in value.items():
            mod = str(module).strip().lower() if module is not None else module
            if isinstance(actions, (list, tuple)):
                out[mod] = [
                    a.strip().lower() if isinstance(a, str) else a for a in actions
                ]
            else:
                out[mod] = actions  # type: ignore[assignment]
        return out

    @model_validator(mode="after")
    def _permissions_modules(self) -> CustomRoleUpdate:
        if self.permissions is None:
            return self
        from app.custom_roles import ASSIGNABLE_MODULES

        if not self.permissions:
            raise ValueError("permissions must include at least one module")
        if self.permissions.get("*") == ["*"] or "*" in (self.permissions.get("*") or []):
            raise ValueError("Custom roles cannot grant wildcard *:*")
        for module, actions in self.permissions.items():
            if module not in ASSIGNABLE_MODULES:
                raise ValueError(f"Unknown or disallowed module '{module}'")
            if not actions:
                raise ValueError(f"Module '{module}' actions must be a non-empty list")
        return self


class ProductCreate(BaseModel):
    # Required catalog label ∈ ProductNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on product create).
    name: ProductNameValue
    sku: str | None = None  # omit/blank → auto-allocate unique SKU (BR-5.1)
    # omit/`null` → no barcode; blank/`!!!!`/`http://…`/`ab` → **422** (was free
    # `str`; blank silently cleared; garbage late service **400** via normalize_barcode).
    barcode: ProductBarcodeValue | None = None
    # omit/`null` → no description; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank silently cleared / garbage could persist on Product.description Text).
    description: ProductDescriptionValue | None = None
    category: str = "General"
    category_id: str | None = None
    brand_id: str | None = None
    unit_id: str | None = None
    cost_price: float = 0
    selling_price: float = 0
    weight: float | None = Field(default=None, ge=0)
    length: float | None = Field(default=None, ge=0)
    width: float | None = Field(default=None, ge=0)
    height: float | None = Field(default=None, ge=0)
    stock_qty: float = 0
    reorder_level: float = 0
    tax_rate_id: str | None = None
    tax_exempt: bool = False
    # BR-12.1 / BR-5.1 — schema Literal; omit → standard; blank/invalid → 422
    tax_supply_class: Literal["standard", "zero_rated", "exempt"] = "standard"
    tracks_batches: bool = False


class ProductUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank late service **400**; garbage could persist on product display name).
    name: ProductNameValue | None = None
    sku: str | None = None
    # omit/`null` → no change; blank/`!!!!`/`http://…`/`ab` → **422** (was free
    # `str`; blank silently cleared; garbage late service **400** via normalize_barcode).
    barcode: ProductBarcodeValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared / garbage could persist on Product.description Text).
    description: ProductDescriptionValue | None = None
    category: str | None = None
    category_id: str | None = None
    brand_id: str | None = None
    unit_id: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None
    weight: float | None = Field(default=None, ge=0)
    length: float | None = Field(default=None, ge=0)
    width: float | None = Field(default=None, ge=0)
    height: float | None = Field(default=None, ge=0)
    reorder_level: float | None = None
    tax_rate_id: str | None = None
    tax_exempt: bool | None = None
    # BR-12.1 — omit = no change; blank/invalid → 422 (no silent standard)
    tax_supply_class: Literal["standard", "zero_rated", "exempt"] | None = None
    tracks_batches: bool | None = None
    is_active: bool | None = None


class StockCountCreate(BaseModel):
    warehouse_id: str
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on StockCount.notes Text).
    notes: StockCountNotesValue | None = None
    product_ids: list[str] | None = None


class StockCountItemUpdate(BaseModel):
    product_id: str
    counted_qty: float
    # omit/`null` → no line notes (or clear when sent null); blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank silently dropped via strip-to-None / garbage could persist).
    notes: StockCountItemNotesValue | None = None


class StockCountItemsUpdate(BaseModel):
    items: list[StockCountItemUpdate]


class StockCountCancel(BaseModel):
    """Draft stock count cancel — typed reason required (BR-5.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class ProductCategoryCreate(BaseModel):
    code: str
    # Required category label ∈ CategoryNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on catalog category create).
    name: CategoryNameValue
    parent_id: str | None = None
    tax_rate_id: str | None = None


class ProductCategoryUpdate(BaseModel):
    code: str | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on category display name).
    name: CategoryNameValue | None = None
    parent_id: str | None = None
    tax_rate_id: str | None = None
    is_active: bool | None = None


class BrandCreate(BaseModel):
    code: str
    # Required brand label ∈ BrandNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on catalog brand create).
    name: BrandNameValue
    # omit/`null` → no description; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank silently cleared / garbage could persist on Brand.description Text).
    description: BrandDescriptionValue | None = None


class BrandUpdate(BaseModel):
    code: str | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on brand display name).
    name: BrandNameValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared / garbage could persist on Brand.description Text).
    description: BrandDescriptionValue | None = None
    is_active: bool | None = None


class UnitOfMeasureCreate(BaseModel):
    code: str
    # Required UoM label ∈ UnitNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on catalog unit create).
    name: UnitNameValue
    base_unit_id: str | None = None
    conversion_ratio: float | None = 1


class UnitOfMeasureUpdate(BaseModel):
    code: str | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on unit display name).
    name: UnitNameValue | None = None
    is_active: bool | None = None
    base_unit_id: str | None = None
    conversion_ratio: float | None = None
    clear_base: bool = False


class UnitConvertPreview(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    from_unit_id: str | None = None


class ProductVariantCreate(BaseModel):
    # Required variant label ∈ VariantNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on product variant create).
    name: VariantNameValue
    sku: str | None = None  # omit/blank → auto-allocate unique SKU (BR-5.1)
    # omit/`null` → no barcode; blank/`!!!!`/`http://…`/`ab` → **422** (was free
    # `str`; blank silently cleared; garbage late service **400** via normalize_barcode).
    barcode: ProductBarcodeValue | None = None
    size: str | None = None
    color: str | None = None
    flavor: str | None = None
    dosage: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None


class ProductVariantUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on variant display name).
    name: VariantNameValue | None = None
    sku: str | None = None
    # omit/`null` → no change; blank/`!!!!`/`http://…`/`ab` → **422** (was free
    # `str`; blank silently cleared; garbage late service **400** via normalize_barcode).
    barcode: ProductBarcodeValue | None = None
    size: str | None = None
    color: str | None = None
    flavor: str | None = None
    dosage: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None
    is_active: bool | None = None


class ProductImagePrimaryUpdate(BaseModel):
    is_primary: bool = True


class PartyCreate(BaseModel):
    # Required party label ∈ PartyNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on customer/supplier).
    name: PartyNameValue
    code: str | None = None
    # BR-6.1 / BR-7.1 — OpenAPI union Literal; kind-specific allow-list still enforced
    # in _normalize_party_profile. Omit → registered; blank/invalid → 422.
    profile_type: Literal[
        "walk_in", "registered", "trade", "manufacturer", "service", "other"
    ] = "registered"
    category: str | None = None
    status: Literal["active", "inactive"] = "active"
    email: EmailStr | None = None
    # omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on customer/supplier create).
    phone: E164PhoneValue | None = None
    # omit/`null` → no address; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on customer/supplier create). Same AddressValue
    # as Company/Store/Branch/Warehouse.
    address: AddressValue | None = None
    latitude: float | None = None
    longitude: float | None = None
    credit_limit: float = 0
    payment_terms_days: int = Field(default=30, ge=0, le=3650)
    customer_group_id: str | None = None


class PartyUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on customer/supplier PATCH).
    name: PartyNameValue | None = None
    code: str | None = None
    # omit = no change; blank/invalid → 422 (no silent registered)
    profile_type: (
        Literal["walk_in", "registered", "trade", "manufacturer", "service", "other"] | None
    ) = None
    category: str | None = None
    status: Literal["active", "inactive"] | None = None
    email: EmailStr | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on customer/supplier PATCH).
    phone: E164PhoneValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on customer/supplier PATCH). Same AddressValue
    # as Company/Store/Branch/Warehouse.
    address: AddressValue | None = None
    latitude: float | None = None
    longitude: float | None = None
    credit_limit: float | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    customer_group_id: str | None = None


class PartyContactCreate(BaseModel):
    # Required contact label ∈ PartyContactNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on customer/supplier contact create).
    name: PartyContactNameValue
    # omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on customer/supplier contact create).
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    # omit/`null` → no designation; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently None / garbage could persist on contact create).
    designation: PartyContactDesignationValue | None = None
    is_primary: bool = False


class PartyContactUpdate(BaseModel):
    name: PartyContactNameValue | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on customer/supplier contact PATCH).
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared / garbage could persist on contact PATCH).
    designation: PartyContactDesignationValue | None = None
    is_primary: bool | None = None


class CustomerGroupCreate(BaseModel):
    # Required group label ∈ CustomerGroupNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on customer group create).
    name: CustomerGroupNameValue
    code: str | None = None
    discount_percent: float = 0


class CustomerGroupUpdate(BaseModel):
    name: CustomerGroupNameValue | None = None
    discount_percent: float | None = None
    is_active: bool | None = None


class LineItem(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None  # entered UoM; stock converted at checkout
    variant_id: str | None = None
    unit_price: float | None = None
    discount: float = Field(default=0, ge=0)


class TransactionCreate(BaseModel):
    party_id: str | None = None
    subtotal: float = 0
    tax: float = 0
    total: float = 0
    # BR-8.1 / legacy sale — only completed create path; blank/invalid → 422 (no garbage persist)
    status: Literal["completed"] = "completed"
    payload: dict = Field(default_factory=dict)
    items: list[LineItem] = Field(default_factory=list)
    override_credit_limit: bool = False
    override_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_override_reason_when_flagged(self):
        return _require_credit_override_reason(self)


class CreditLimitOverrideBody(BaseModel):
    """Optional body for posting sales that may exceed credit limit (BR-11.1)."""

    override_credit_limit: bool = False
    override_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_override_reason_when_flagged(self):
        return _require_credit_override_reason(self)


class StockAdjust(BaseModel):
    quantity: float
    # Coded reason (BR-5.2); OpenAPI Literal → omit/blank/invalid → 422
    reason: Literal["damage", "theft", "expiry", "found", "lost"]
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on StockMovement.notes Text).
    notes: StockAdjustNotesValue | None = None
    warehouse_id: str | None = None


class StockMove(BaseModel):
    """Manual stock-in — optional batch dates ∈ IsoDateQueryValue (BR-5.2).

    Optional `manufacturing_date` / `expiry_date`; omit/`null` → no batch dates;
    blank/invalid → **422** (was free `datetime`; OpenAPI date-time; padded dates
    inconsistent). API `reports.parse_date` remains defense-in-depth.
    """

    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None  # entered UoM; converted to product.unit_id for stock
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on StockMovement.notes Text).
    notes: StockInNotesValue | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_id: str | None = None
    batch_number: str | None = None
    manufacturing_date: IsoDateQueryValue | None = None
    expiry_date: IsoDateQueryValue | None = None
    # Optional on stock-in; stock-out uses StockOut with required Literal
    reference_type: str | None = None
    reference_id: str | None = None


class StockOut(BaseModel):
    """Manual stock-out (BR-5.2) — coded reference_type required at schema."""

    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on StockMovement.notes Text).
    notes: StockOutNotesValue | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_id: str | None = None
    # OpenAPI Literal → omit/blank/invalid → 422
    reference_type: Literal["sale", "transfer", "adjustment", "damage", "internal", "other"]
    reference_id: str | None = None


class OpeningStockLine(BaseModel):
    """Opening-stock line — optional batch dates ∈ IsoDateQueryValue (BR-5.2).

    Optional `manufacturing_date` / `expiry_date`; omit/`null` → no batch dates;
    blank/invalid → **422** (was free `datetime`; OpenAPI date-time; padded dates
    inconsistent). API `reports.parse_date` remains defense-in-depth.
    """

    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_number: str | None = None
    manufacturing_date: IsoDateQueryValue | None = None
    expiry_date: IsoDateQueryValue | None = None
    unit_cost: float | None = Field(default=None, ge=0)  # defaults to product.cost_price
    # omit/`null` → no line notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could merge onto StockMovement.notes). Same `OpeningStockNotesValue`
    # as header notes.
    notes: OpeningStockNotesValue | None = None


class OpeningStockCreate(BaseModel):
    lines: list[OpeningStockLine] = Field(min_length=1)
    post_journal: bool = True
    # omit/`null` → auto OS-YYYY-NNNN; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank silently auto-numbered / garbage could persist on journal ref).
    reference: OpeningStockReferenceValue | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on movement notes).
    notes: OpeningStockNotesValue | None = None


class ExpenseCreate(BaseModel):
    category: str | None = None
    category_id: str | None = None
    # omit/`null` → empty narrative; blank/`!!!`/`http://…` → **422** (was free
    # `str` default `""`; blank/garbage could persist).
    description: ExpenseDescriptionValue | None = None
    amount: float = Field(gt=0)
    # BR-9.2 — schema Literal (+ aliases via BeforeValidator); omit → cash;
    # blank/invalid → 422 (no silent cash from garbage).
    payment_method: ExpensePaymentMethod = "cash"
    liquid_account_id: str | None = None
    # omit/`null` → auto EXP-YYYY-NNNN; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank silently auto-numbered / garbage could persist).
    reference: ExpenseReferenceValue | None = None
    # omit/`null` → no payee; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on expense create).
    payee: ExpensePayeeValue | None = None
    store_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    # omit/`null` → service default (today); blank/`not-a-date`/`01/02/2024` → **422**
    # (was free `datetime`; OpenAPI date-time; padded dates inconsistent). Same
    # IsoDateQueryValue as AI draft expense_date / payment cheque_date.
    expense_date: IsoDateQueryValue | None = None


class AiChatBody(BaseModel):
    """POST /ai/chat — typed chat body (BR-21.1).

    Unknown keys → **422** (`extra=forbid`). Blank/omit `message` (and `prompt`
    alias) → **422** (blank was late service **400**). Optional `context` /
    `conversation_id` accepted for documented clients (unused by mock path).
    Service `parse_chat_message` / injection checks remain defense-in-depth.
    """

    model_config = ConfigDict(extra="forbid")

    message: str | None = None
    prompt: str | None = None
    context: str | None = None
    conversation_id: str | None = None

    @field_validator("message", "prompt", "context", "conversation_id", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value

    @model_validator(mode="after")
    def _require_message_or_prompt(self) -> AiChatBody:
        if not (self.message or self.prompt):
            raise ValueError("message is required")
        return self


class AiCustomerAssistBody(BaseModel):
    """POST /ai/customer/assist — typed customer assistant body (BR-21.9).

    Unknown keys → **422** (`extra=forbid`). Omit/`{}` still allowed (overview).
    Blank `customer_id` / `query` / `message` coerce to omit. `message` is an
    accepted alias for `query` (historical free-dict clients).
    """

    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    query: str | None = None
    message: str | None = None

    @field_validator("customer_id", "query", "message", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value


class AiDocumentExpenseCreate(BaseModel):
    """Explicit Create draft expense from reviewed OCR fields (BR-21.8).

    Unknown keys → **422** (`extra=forbid`). Optional `expense_date` ∈
    `IsoDateQueryValue`; omit → service default (today); blank/invalid → **422**
    (blank was silent default; invalid was late service **400** via
    `_parse_expense_date`).
    """

    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0)
    # omit/`null` → no payee; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on AI draft expense).
    payee: ExpensePayeeValue | None = None
    # omit/`null` → no description; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank/garbage could persist on AI draft expense).
    description: ExpenseDescriptionValue | None = None
    # omit/`null` → auto / service default; blank/`!!!`/`http://…` → **422** (was
    # free `str`; blank/garbage could persist on AI draft expense).
    reference: ExpenseReferenceValue | None = None
    category_id: str | None = None
    category: str | None = None
    payment_method: ExpensePaymentMethod = "cash"
    expense_date: IsoDateQueryValue | None = None
    store_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None


class AiDocumentPurchaseInvoiceCreate(BaseModel):
    """Explicit Create draft purchase invoice from reviewed OCR + matched PO (BR-21.8).

    Unknown keys → **422** (`extra=forbid`). Optional `invoice_date` ∈
    `IsoDateQueryValue`; omit → service default; blank/invalid → **422**
    (blank was silent default; invalid was late service **400** via
    `_parse_invoice_date`).
    """

    model_config = ConfigDict(extra="forbid")

    purchase_order_id: str
    supplier_id: str | None = None
    supplier_invoice_number: str | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`).
    notes: PurchaseInvoiceNotesValue | None = None
    is_reverse_charge: bool = False
    invoice_date: IsoDateQueryValue | None = None


class ExpenseUpdate(BaseModel):
    category: str | None = None
    category_id: str | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on expense PATCH).
    description: ExpenseDescriptionValue | None = None
    amount: float | None = Field(default=None, gt=0)
    # omit = no change; blank/invalid → 422
    payment_method: ExpensePaymentMethod | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared / garbage could persist on expense PATCH).
    reference: ExpenseReferenceValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on expense PATCH). Use recurring `clear_payee`
    # pattern is N/A here — send a valid label to change.
    payee: ExpensePayeeValue | None = None
    # omit/`null` → no change; blank/`not-a-date`/`01/02/2024` → **422** (was free
    # `datetime`; OpenAPI date-time; padded dates inconsistent). Same
    # IsoDateQueryValue as create / AI draft / payment cheque_date.
    expense_date: IsoDateQueryValue | None = None
    store_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    clear_store: bool = False
    clear_branch: bool = False
    clear_department: bool = False


class ExpenseCategoryCreate(BaseModel):
    code: str
    # Required category label ∈ ExpenseCategoryNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on expense category create).
    name: ExpenseCategoryNameValue
    budget_amount: float = Field(default=0, ge=0)
    account_id: str | None = None


class ExpenseCategoryUpdate(BaseModel):
    name: ExpenseCategoryNameValue | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
    account_id: str | None = None
    clear_account: bool = False


class ExpenseDecision(BaseModel):
    """Approve path — optional typed comment (BR-9.3).

    Optional `comment` ∈ ExpenseApproveCommentValue; omit/`null` → no typed comment
    (service may still set a level-awaiting system note); blank/`!!!`/`http://…` →
    **422** (was free `str`; blank/garbage could persist on `approval_comment`).
    """

    # omit/`null` → no typed comment; blank/`!!!`/`http://…` → **422**
    comment: ExpenseApproveCommentValue | None = None


class ExpenseReject(BaseModel):
    """Expense reject — typed reason required (BR-9.3 honesty).

    `reason` ∈ ExpenseRejectReasonValue (strip; 1–500; ≥1 letter/digit; no
    `://`/`@`); omit/blank/`!!!`/`http://…` → **422** (was free `str` with
    `min_length=1` only — whitespace still reached service **400**; punctuation-
    only / URL-like garbage could persist on `Expense.rejection_reason`).
    """

    reason: ExpenseRejectReasonValue


class RecurringExpenseCreate(BaseModel):
    category: str | None = None
    category_id: str | None = None
    # omit/`null` → empty narrative; blank/`!!!`/`http://…` → **422** (was free
    # `str` default `""`; blank/garbage could persist on recurring create).
    description: ExpenseDescriptionValue | None = None
    amount: float = Field(gt=0)
    # BR-9.5 — schema Literal; omit defaults to monthly; blank/invalid → 422
    frequency: Literal["daily", "weekly", "monthly", "yearly"] = "monthly"
    # BR-9.2 / BR-9.5 — same ExpensePaymentMethod Literal; omit → bank_transfer
    payment_method: ExpensePaymentMethod = "bank_transfer"
    # omit/`null` → no payee; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on recurring create).
    payee: ExpensePayeeValue | None = None
    branch_id: str | None = None
    department_id: str | None = None


class RecurringExpenseUpdate(BaseModel):
    is_active: bool | None = None
    amount: float | None = Field(default=None, gt=0)
    # omit/`null` → no change (unless `clear_payee`); blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on recurring PATCH).
    payee: ExpensePayeeValue | None = None
    clear_payee: bool = False
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on recurring PATCH).
    description: ExpenseDescriptionValue | None = None
    payment_method: ExpensePaymentMethod | None = None
    frequency: Literal["daily", "weekly", "monthly", "yearly"] | None = None
    category_id: str | None = None
    category: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    clear_branch: bool = False
    clear_department: bool = False


class RecurringSkipNext(BaseModel):
    """Skip next recurring occurrence — typed reason required (BR-9.5 honesty).

    `reason` ∈ RecurringSkipReasonValue (strip; 1–500; ≥1 letter/digit; no
    `://`/`@`); omit/blank/`!!!`/`http://…` → **422** (was free `str` with
    `min_length=1` only — whitespace still reached service **400**; punctuation-
    only / URL-like garbage could persist on audit `recurring_expense_skipped`).
    """

    reason: RecurringSkipReasonValue


class ApprovalLevelUpdate(BaseModel):
    """One expense approval matrix level (BR-9.3).

    Unknown keys → **422** (`extra=forbid`). `roles[]` ∈ system roles
    (`SystemRoleValue` / `rbac.VALID_ROLES`); blank/unknown role → **422**
    (was late service **400**). Optional `label` ∈ ApprovalLevelLabelValue;
    omit/`null` → no label; blank/`!!!`/`http://…` → **422** (was free `str`;
    blank/garbage could persist in tenant expense approval matrix JSON).
    """

    model_config = ConfigDict(extra="forbid")

    min_amount: float = Field(gt=0)
    roles: list[SystemRoleValue] = Field(min_length=1)
    # omit/`null` → no label; blank/`!!!`/`http://…` → **422** (was free `str`).
    label: ApprovalLevelLabelValue | None = None
    step: int | None = None


class ExpenseThresholdUpdate(BaseModel):
    """PATCH /expenses/settings — thresholds + approval matrix (BR-9.3).

    Unknown keys → **422**. When `levels` is sent, each level uses
    `ApprovalLevelUpdate` honesty.
    """

    model_config = ConfigDict(extra="forbid")

    expense_approval_threshold: float | None = Field(default=None, gt=0)
    expense_l2_threshold: float | None = Field(default=None, gt=0)
    levels: list[ApprovalLevelUpdate] | None = None
    expense_numbering: DocumentNumberingFields | None = None


# Keep aligned with app.stores._TIME_RE / WEEKDAYS (Multi-Store operating hours).
_STORE_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class StoreDayHours(BaseModel):
    """One weekday entry for store operating_hours (BR-2.3).

    Unknown keys → **422** (`extra=forbid`). When not `closed`, `open`/`close`
    must be HH:MM (24h) with open before close → **422** (was late service **400**).
    """

    model_config = ConfigDict(extra="forbid")

    open: str | None = None
    close: str | None = None
    closed: bool | None = None

    @field_validator("open", "close", mode="before")
    @classmethod
    def _strip_hhmm(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _require_times_when_open(self) -> StoreDayHours:
        if self.closed:
            return self
        open_t = self.open or ""
        close_t = self.close or ""
        # Keep aligned with app.stores._TIME_RE
        if not _STORE_HHMM_RE.fullmatch(open_t) or not _STORE_HHMM_RE.fullmatch(close_t):
            raise ValueError("open/close required as HH:MM (24h) when not closed")
        if open_t >= close_t:
            raise ValueError("open must be before close")
        return self


class StoreOperatingHours(BaseModel):
    """Weekly operating_hours map (BR-2.3).

    Unknown day keys → **422** (`extra=forbid`). Keys ∈ mon…sun only.
    """

    model_config = ConfigDict(extra="forbid")

    mon: StoreDayHours | None = None
    tue: StoreDayHours | None = None
    wed: StoreDayHours | None = None
    thu: StoreDayHours | None = None
    fri: StoreDayHours | None = None
    sat: StoreDayHours | None = None
    sun: StoreDayHours | None = None


class StoreCreate(BaseModel):
    # Required store label ∈ StoreNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on multi-store create).
    name: StoreNameValue
    code: str
    # omit/`null` → no address; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/`garbage` could persist on create). Same AddressValue as Company.
    address: AddressValue | None = None
    # omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank/garbage could persist on create).
    phone: E164PhoneValue | None = None
    manager_id: str | None = None
    branch_id: str | None = None
    operating_hours: StoreOperatingHours | None = None


class StoreUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on store display name).
    name: StoreNameValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared; garbage could persist). Same AddressValue as Company.
    address: AddressValue | None = None
    # omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`;
    # blank silently cleared; garbage could persist).
    phone: E164PhoneValue | None = None
    manager_id: str | None = None
    clear_manager: bool = False
    branch_id: str | None = None
    clear_branch: bool = False
    is_active: bool | None = None
    operating_hours: StoreOperatingHours | None = None


class StoreDrawerSettingsUpdate(BaseModel):
    # BR-8.1 — schema Literal; omit = no change; blank/invalid → 422 (no silent none)
    drawer_mode: Literal["none", "mock", "network", "browser_bridge"] | None = None
    # omit/`null` → no change / clear; blank/`http://…`/`not a host` → **422**
    # (was free `str`; blank silent→null; garbage could persist). Same hostname
    # honesty as Company SMTP (`SmtpHostValue`). Network mode still requires host
    # at service (**400**) when unset.
    drawer_host: SmtpHostValue | None = None
    drawer_port: int | None = Field(default=None, ge=1, le=65535)
    drawer_open_on_cash: bool | None = None


class PosDrawerOpen(BaseModel):
    """Manual drawer open — cashier must supply a specific reason (not blank / not 'manual')."""

    reason: str = Field(min_length=1, max_length=200)


class StoreReorderPolicyUpdate(BaseModel):
    product_id: str
    reorder_level: float = Field(ge=0)
    reorder_qty: float = Field(default=0, ge=0)


class WarehouseReorderPolicyUpdate(BaseModel):
    warehouse_id: str
    product_id: str
    reorder_level: float = Field(ge=0)
    reorder_qty: float = Field(default=0, ge=0)


class InventoryFefoSettingsUpdate(BaseModel):
    fefo_strict_warehouse: bool | None = None
    stock_transfer_numbering: DocumentNumberingFields | None = None
    stock_count_numbering: DocumentNumberingFields | None = None
    opening_stock_numbering: DocumentNumberingFields | None = None


class WarehouseCreate(BaseModel):
    # Required warehouse label ∈ WarehouseNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on multi-store warehouse create).
    name: WarehouseNameValue
    code: str
    store_id: str | None = None
    # BR-2.4 — schema Literal; omit defaults to retail; blank/invalid → 422
    warehouse_type: Literal["retail", "bulk", "cold_storage", "other"] = "retail"
    manager_id: str | None = None
    # omit/`null` → no address; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on create). Same AddressValue as Company/Store/Branch.
    address: AddressValue | None = None
    capacity: float | None = Field(default=None, ge=0)


class WarehouseUpdate(BaseModel):
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on warehouse display name).
    name: WarehouseNameValue | None = None
    store_id: str | None = None
    clear_store: bool = False
    warehouse_type: Literal["retail", "bulk", "cold_storage", "other"] | None = None
    manager_id: str | None = None
    clear_manager: bool = False
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared; garbage could persist). Same AddressValue as Company/Store/Branch.
    address: AddressValue | None = None
    capacity: float | None = Field(default=None, ge=0)
    clear_capacity: bool = False
    is_active: bool | None = None


class StockTransferItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)


class StockTransferCreate(BaseModel):
    from_store_id: str | None = None
    to_store_id: str | None = None
    from_warehouse_id: str | None = None
    to_warehouse_id: str | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on StockTransfer.notes Text).
    notes: StockTransferNotesValue | None = None
    submit: bool = False
    items: list[StockTransferItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def require_store_or_warehouse_pair(self):
        has_wh = bool(self.from_warehouse_id and self.to_warehouse_id)
        has_st = bool(self.from_store_id and self.to_store_id)
        if not has_wh and not has_st:
            raise ValueError(
                "Provide from_store_id/to_store_id or from_warehouse_id/to_warehouse_id"
            )
        return self


class StockTransferReject(BaseModel):
    """Stock / store transfer reject or cancel — typed reason required (BR-5.2/5.4 / BR-13.2)."""

    reason: str = Field(min_length=1, max_length=500)


def coerce_tax_component_basis_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


TaxComponentBasisValue = Annotated[
    Literal["net", "compound"],
    BeforeValidator(coerce_tax_component_basis_value),
]


class TaxComponent(BaseModel):
    """Compound tax leg (BR-12.1) — unknown keys → 422; blank/invalid basis → 422."""

    model_config = ConfigDict(extra="forbid")

    rate: float = Field(ge=0)
    # omit → net; blank/invalid → 422 (was free dict; blank silently net; bad late **400**)
    basis: TaxComponentBasisValue = "net"
    code: str | None = None
    name: str | None = None


class TaxCreate(BaseModel):
    # Required tax rate label ∈ TaxRateNameValue; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on tax rate create).
    name: TaxRateNameValue
    rate: float = Field(ge=0)
    # BR-12.1 — schema Literal; omit defaults; blank/invalid → 422
    tax_type: Literal["vat", "gst", "sales_tax", "custom"] = "vat"
    pricing_mode: Literal["exclusive", "inclusive"] = "exclusive"
    components: list[TaxComponent] | None = None
    is_reverse_charge: bool = False
    is_default: bool = False
    is_active: bool = True


class TaxUpdate(BaseModel):
    name: TaxRateNameValue | None = None
    rate: float | None = Field(default=None, ge=0)
    # BR-12.1 — omit = no change; blank/invalid → 422
    tax_type: Literal["vat", "gst", "sales_tax", "custom"] | None = None
    pricing_mode: Literal["exclusive", "inclusive"] | None = None
    components: list[TaxComponent] | None = None
    is_reverse_charge: bool | None = None
    is_active: bool | None = None


class TaxCalculateRequest(BaseModel):
    amount: float = Field(gt=0)
    rate: float | None = None
    tax_rate_id: str | None = None
    # BR-12.1 — omit → exclusive at calc; blank/invalid → 422
    pricing_mode: Literal["exclusive", "inclusive"] | None = None
    components: list[TaxComponent] | None = None
    is_reverse_charge: bool | None = None


class PasswordResetRequest(BaseModel):
    email: EmailStr
    tenant_id: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class EmailVerifyConfirm(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
    tenant_id: str


class PurchaseOrderItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None  # entered UoM; GRN converts to product stock unit
    unit_price: float = Field(ge=0)
    # Omit to auto-resolve product → category → tenant default (BR-12.2); explicit 0 allowed
    tax_rate: float | None = Field(default=None, ge=0)
    discount: float = Field(default=0, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    warehouse_id: str | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on PurchaseOrder.notes Text).
    notes: PurchaseOrderNotesValue | None = None
    # omit/`null` → no ship-to; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silent→null; garbage could persist). Same AddressValue as Party/Store.
    delivery_address: AddressValue | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class PurchaseOrderAmend(BaseModel):
    """PO amend (BR-6.3). Optional `to` ∈ EmailStr when notifying supplier; blank/invalid → 422.

    Optional `due_date` ∈ `IsoDateQueryValue`; omit/`null` → no change;
    blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time;
    padded dates inconsistent). `clear_due_date=True` clears. API `reports.parse_date`
    remains defense-in-depth.
    """

    items: list[PurchaseOrderItemCreate] | None = None
    # omit/`null` → no change / clear when null sent; blank/`!!!`/`http://…` → **422**
    # (was free `str`; blank/garbage could persist on PurchaseOrder.notes).
    notes: PurchaseOrderNotesValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared ship-to; garbage could persist). Same AddressValue.
    delivery_address: AddressValue | None = None
    due_date: IsoDateQueryValue | None = None
    clear_due_date: bool = False
    # Required typed reason (BR-6.3 honesty); no silent amend
    reason: str = Field(min_length=1, max_length=500)
    notify_supplier: bool = False
    to: EmailStr | None = None


class PurchaseOrderCancel(BaseModel):
    """PO cancel — typed reason required (BR-6.3 honesty)."""

    reason: str = Field(min_length=1, max_length=500)

class PurchaseRequestItemCreate(BaseModel):
    """Purchase request line — optional notes ∈ PurchaseRequestNotesValue (BR-6.2).

    Optional `notes`; omit/`null` → no line notes; blank/`!!!`/`http://…` → **422**
    (was free `str`; blank/garbage could persist on `PurchaseRequestItem.notes`).
    """

    product_id: str
    quantity: float = Field(gt=0)
    variant_id: str | None = None
    # omit/`null` → no line notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on PurchaseRequestItem.notes Text).
    notes: PurchaseRequestNotesValue | None = None


class PurchaseRequestCreate(BaseModel):
    """Create purchase request — optional required_date ∈ IsoDateQueryValue (BR-6.2).

    Optional `required_date`; omit/`null` → no needed-by date; blank/invalid → **422**
    (was free `datetime`; OpenAPI date-time; padded dates inconsistent). API
    `reports.parse_date` remains defense-in-depth.
    Optional `notes` ∈ PurchaseRequestNotesValue; omit/`null` → no notes; blank/`!!!`/
    `http://…` → **422** (was free `str`; blank/garbage could persist on PREQ).
    """

    preferred_supplier_id: str | None = None
    warehouse_id: str | None = None
    required_date: IsoDateQueryValue | None = None
    department: str | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on PurchaseRequest.notes Text).
    notes: PurchaseRequestNotesValue | None = None
    items: list[PurchaseRequestItemCreate] = Field(min_length=1)


class PurchaseRequestReject(BaseModel):
    """Purchase request reject — typed reason required (BR-6.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class PurchaseRequestConvert(BaseModel):
    supplier_id: str | None = None


class PurchaseApprovalLevelUpdate(BaseModel):
    """One PR approval matrix level (role chain; BR-6.x).

    Unknown keys → **422** (`extra=forbid`). Same `roles[]` honesty as expense
    matrix (`SystemRoleValue`); blank/unknown → **422** (was late **400**).
    Optional `label` ∈ ApprovalLevelLabelValue; omit/`null` → no label;
    blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could
    persist in tenant PR approval matrix JSON).
    """

    model_config = ConfigDict(extra="forbid")

    roles: list[SystemRoleValue] = Field(min_length=1)
    # omit/`null` → no label; blank/`!!!`/`http://…` → **422** (was free `str`).
    label: ApprovalLevelLabelValue | None = None
    step: int | None = None


class PurchaseApprovalSettingsUpdate(BaseModel):
    """PATCH /purchasing/requests/settings — PR approval matrix.

    Unknown keys → **422**. `levels` required non-empty.
    """

    model_config = ConfigDict(extra="forbid")

    levels: list[PurchaseApprovalLevelUpdate] = Field(min_length=1)


class LowStockSuggestionLine(BaseModel):
    """One low-stock suggestion line for draft PR creation (BR-6.2).

    Optional `notes` ∈ PurchaseRequestNotesValue; omit/`null` → no line notes;
    blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist).
    """

    product_id: str
    quantity: float | None = Field(default=None, gt=0)
    warehouse_id: str | None = None
    preferred_supplier_id: str | None = None
    # omit/`null` → no line notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on PurchaseRequestItem.notes).
    notes: PurchaseRequestNotesValue | None = None


class LowStockSuggestionsCreate(BaseModel):
    """POST /purchasing/requests/from-low-stock (BR-6.2).

    Optional header `notes` ∈ PurchaseRequestNotesValue; omit/`null` → service
    default; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage
    could persist on draft PREQ notes).
    """

    lines: list[LowStockSuggestionLine] = Field(min_length=1)
    # omit/`null` → service default note; blank/`!!!`/`http://…` → **422** (was
    # free `str`; blank/garbage could persist on PurchaseRequest.notes).
    notes: PurchaseRequestNotesValue | None = None
    department: str | None = None
    include_open: bool = False


class AiLowStockPredictionLine(BaseModel):
    """One at-risk prediction row for draft PR creation (BR-21.4).

    Unknown keys → **422** (`extra=forbid`). Required non-blank `product_id`.
    Optional confidence 0–1 and order qty ≥0. Aligns with fields read by
    `create_requests_from_predictions` (not the full GET prediction shape).
    Optional `risk_reason` ∈ AiPredictionRiskReasonValue; omit/`null` → service
    defaults line note to `at_risk`; blank/`!!!`/`http://…` → **422** (was free
    `str` stripped to null; garbage could land in draft PR line notes).
    """

    model_config = ConfigDict(extra="forbid")

    product_id: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    suggested_order_qty: float | None = Field(default=None, ge=0)
    recommended_order_qty: float | None = Field(default=None, ge=0)
    warehouse_id: str | None = None
    preferred_supplier_id: str | None = None
    # omit/`null` → no line notes; blank/`!!!`/`http://…` → **422** (was free `str`
    # stripped to null; blank/garbage could persist onto draft PR line notes).
    notes: PurchaseRequestNotesValue | None = None
    # omit/`null` → service uses `at_risk` in generated line notes; blank/`!!!`/
    # `http://…` → **422** (was free `str`; blank silently dropped / garbage could
    # embed into PurchaseRequestItem.notes via create_requests_from_predictions).
    risk_reason: AiPredictionRiskReasonValue | None = None

    @field_validator(
        "product_id",
        "warehouse_id",
        "preferred_supplier_id",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value

    @field_validator("product_id")
    @classmethod
    def _require_product_id(cls, value: str | None) -> str:
        if not value:
            raise ValueError("product_id is required")
        return value


class AiLowStockPredictionRequestsBody(BaseModel):
    """POST /ai/inventory/low-stock-prediction/requests (BR-21.4).

    Unknown keys → **422** (`extra=forbid`). `days_ahead` ∈ 1–365 (omit → 14;
    blank/non-int → **422** — was `int(... or 14)` which silently defaulted
    blanks and could **500** on garbage). `min_confidence` ∈ 0–1 (omit → 0;
    garbage → **422**). Nested `lines` are `AiLowStockPredictionLine`
    (`extra=forbid`; blank `product_id` / unknown line keys / bad qty|confidence
    → **422** — was free `list[dict]`). Omit/`null`/`[]` `lines` re-runs
    prediction. Service `create_requests_from_predictions` remains defense-in-depth.
    """

    model_config = ConfigDict(extra="forbid")

    lines: list[AiLowStockPredictionLine] | None = None
    days_ahead: int = Field(default=14, ge=1, le=365)
    min_confidence: float = Field(default=0, ge=0, le=1)
    # omit/`null` → no header notes; blank/`!!!`/`http://…` → **422** (was free
    # `str` stripped to null; blank/garbage could persist on draft PREQ notes).
    notes: PurchaseRequestNotesValue | None = None
    include_open: bool = False


class GrnItemCreate(BaseModel):
    """GRN line — optional batch dates ∈ IsoDateQueryValue (BR-6.4).

    Optional `manufacturing_date` / `expiry_date`; omit/`null` → no batch dates;
    blank/invalid → **422** (was free `datetime`; OpenAPI date-time; padded dates
    inconsistent). API `reports.parse_date` remains defense-in-depth.
    """

    po_item_id: str
    received_qty: float = Field(gt=0)
    accepted_qty: float | None = None
    rejected_qty: float = Field(default=0, ge=0)
    rejection_reason: str | None = None
    # Optional lot for accepted stock (BR-6.4); required when product.tracks_batches
    batch_number: str | None = None
    manufacturing_date: IsoDateQueryValue | None = None
    expiry_date: IsoDateQueryValue | None = None

    @model_validator(mode="after")
    def require_reason_when_rejected(self):
        """OpenAPI honesty (BR-6.4): reason required when any qty is rejected."""
        received = float(self.received_qty or 0)
        rejected = float(self.rejected_qty or 0)
        accepted = self.accepted_qty
        if rejected <= 1e-9 and accepted is not None and float(accepted) < received - 1e-9:
            rejected = round(received - float(accepted), 6)
        if rejected > 1e-9 and not (self.rejection_reason or "").strip():
            raise ValueError("rejection_reason is required when rejected_qty > 0")
        return self


class GrnCreate(BaseModel):
    purchase_order_id: str
    warehouse_id: str | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on GoodsReceipt.notes Text).
    notes: GrnNotesValue | None = None
    items: list[GrnItemCreate] = Field(min_length=1)


class PurchaseReturnItemCreate(BaseModel):
    goods_receipt_item_id: str
    quantity: float = Field(gt=0)


class PurchaseReturnCreate(BaseModel):
    goods_receipt_id: str
    # Required coded reason (BR-6.6); OpenAPI Literal → omit/blank/invalid → 422
    reason: Literal["damaged", "wrong_item", "expiry", "quality", "other"]
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on PurchaseReturn.notes Text).
    notes: PurchaseReturnNotesValue | None = None
    items: list[PurchaseReturnItemCreate] = Field(min_length=1)


class PurchaseReturnCancel(BaseModel):
    """Draft purchase return cancel — typed reason required (BR-6.6 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class PurchaseInvoiceItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_price: float | None = None
    # Omit to auto-resolve product → category → tenant default (BR-12.2); explicit 0 allowed
    tax_rate: float | None = Field(default=None, ge=0)
    discount: float = Field(default=0, ge=0)


class PurchaseInvoiceCreate(BaseModel):
    supplier_id: str | None = None
    goods_receipt_id: str | None = None
    purchase_order_id: str | None = None
    supplier_invoice_number: str | None = None
    discount_amount: float = Field(default=0, ge=0)
    attachment_url: str | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on PurchaseInvoice.notes Text).
    notes: PurchaseInvoiceNotesValue | None = None
    # Buyer self-assesses VAT (excluded from AP); posts Dr Input Tax / Cr Tax Payable on approve.
    is_reverse_charge: bool = False
    # omit/null → tenant base via resolve_rate; blank/non-ISO → 422 (was free str; blank silently base)
    currency: CurrencyCodeValue | None = None
    exchange_rate: float | None = Field(default=None, gt=0)
    items: list[PurchaseInvoiceItemCreate] | None = None


class PurchaseInvoiceUpdate(BaseModel):
    """PATCH draft purchase invoice — optional OCR/manual date fields.

    Optional `invoice_date` / `due_date` ∈ `IsoDateQueryValue`; omit/`null` → no
    change; blank/invalid → **422** (was free `datetime`; OpenAPI date-time;
    padded dates inconsistent). API `reports.parse_date` remains defense-in-depth.
    Optional `notes` ∈ PurchaseInvoiceNotesValue; omit/`null` → no change; blank/
    `!!!`/`http://…` → **422** (was free `str`; blank silently cleared / garbage
    could persist).
    """

    supplier_invoice_number: str | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared / garbage could persist on draft PATCH).
    notes: PurchaseInvoiceNotesValue | None = None
    invoice_date: IsoDateQueryValue | None = None
    due_date: IsoDateQueryValue | None = None


class PurchaseInvoiceCancel(BaseModel):
    """Purchase invoice cancel — typed reason required (BR-6.5 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class SalesInvoiceItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None  # entered UoM; post/reserve convert to stock unit
    unit_price: float | None = None
    tax_rate: float | None = None
    discount: float = Field(default=0, ge=0)
    variant_id: str | None = None


class SalesInvoiceCreate(BaseModel):
    customer_id: str
    discount_amount: float = Field(default=0, ge=0)
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on SalesInvoice.notes Text).
    notes: SalesDocumentNotesValue | None = None
    store_id: str | None = None
    # omit/null → tenant base via resolve_rate; blank/non-ISO → 422 (was free str; blank silently base)
    currency: CurrencyCodeValue | None = None
    exchange_rate: float | None = Field(default=None, gt=0)
    is_reverse_charge: bool = False
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesQuotationCreate(BaseModel):
    customer_id: str
    discount_amount: float = Field(default=0, ge=0)
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on SalesQuotation.notes Text).
    notes: SalesDocumentNotesValue | None = None
    valid_days: int = Field(default=14, ge=1, le=365)
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesQuotationReject(BaseModel):
    """Quotation reject — typed reason required (BR-7.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class SalesOrderCreate(BaseModel):
    customer_id: str
    quotation_id: str | None = None
    store_id: str | None = None
    # omit/`null` → no promised date; blank/`not-a-date`/`01/02/2024` → **422**
    # (was free `datetime`; OpenAPI date-time; padded dates inconsistent).
    delivery_date: IsoDateQueryValue | None = None
    # omit/`null` → no ship-to; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silent→null; garbage could persist). Same AddressValue as PO.
    delivery_address: AddressValue | None = None
    discount_amount: float = Field(default=0, ge=0)
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on SalesOrder.notes Text).
    notes: SalesDocumentNotesValue | None = None
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesOrderConfirm(BaseModel):
    store_id: str | None = None
    # omit/`null` → no change; blank/`not-a-date`/`01/02/2024` → **422**
    # (was free `datetime`; OpenAPI date-time; padded dates inconsistent).
    delivery_date: IsoDateQueryValue | None = None
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silent→null; garbage could persist). Same AddressValue as PO.
    delivery_address: AddressValue | None = None


class SalesOrderCancel(BaseModel):
    """Sales order cancel — typed reason required (BR-7.3 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class SalesInvoiceCancel(BaseModel):
    """Draft sales invoice cancel — typed reason required (BR-7.4 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class SalesReturnItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    # Required coded condition (BR-7.5); OpenAPI Literal → omit/blank/invalid → 422
    condition: Literal["sellable", "discard"]
    variant_id: str | None = None


class SalesReturnCreate(BaseModel):
    sales_invoice_id: str
    # Required coded reason (BR-7.5); OpenAPI Literal → omit/blank/invalid → 422
    reason: Literal["damaged", "wrong_item", "defective", "customer_change", "other"]
    restock: bool = True
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on SalesReturn.notes Text).
    notes: SalesReturnNotesValue | None = None
    items: list[SalesReturnItemCreate] = Field(min_length=1)


class SalesReturnCancel(BaseModel):
    """Draft sales return cancel — typed reason required (BR-7.5 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class SalesReturnPost(BaseModel):
    # BR-7.5 — omit OK (service defaults adjust when no excess AR); blank/invalid → 422.
    # When return exceeds open AR, service still requires adjust|refund (400 SETTLEMENT_REQUIRED).
    settlement_method: SalesReturnSettlementMethod | None = None
    # BR-7.5 / BR-11 — same settlement Literal as AR payments; omit → cash; blank/invalid → 422
    payment_method: SettlementPaymentMethod = "cash"
    liquid_account_id: str | None = None


class CustomerPaymentCreate(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    sales_invoice_id: str | None = None
    # BR-11.1 — schema Literal (+ aliases); omit → cash; blank/invalid → 422
    payment_method: SettlementPaymentMethod = "cash"
    # omit/`null` → no reference; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on CustomerPayment.reference String(100)).
    reference: PaymentReferenceValue | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on CustomerPayment.notes Text).
    notes: PaymentNotesValue | None = None
    # omit/`null` → service falls back to reference/payment_number; blank/`!!!`/
    # `http://…` → **422** (was free `str`; blank/garbage could persist on cheque).
    cheque_number: ChequeNumberValue | None = None
    # omit/`null` → no bank on cheque; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank/garbage could persist on cheque payment bank_name).
    bank_name: BankNameValue | None = None
    # omit/`null` → no cheque date; blank/`not-a-date`/`01/02/2024` → **422**
    # (was free `datetime`; OpenAPI date-time; padded dates rejected; Credit UI
    # never set → always null). API parses via reports.parse_date.
    cheque_date: IsoDateQueryValue | None = None
    apply_early_discount: bool | None = None
    liquid_account_id: str | None = None
    # omit/null → invoice/base via resolve_rate; blank/non-ISO → 422 (was free str; blank silently base)
    currency: CurrencyCodeValue | None = None
    exchange_rate: float | None = Field(default=None, gt=0)


class EarlyPaySettingsUpdate(BaseModel):
    early_pay_discount_pct: float = Field(ge=0, le=100)
    early_pay_discount_days: int = Field(ge=0, le=365)


def coerce_document_prefix_value(value: object) -> object:
    """Pydantic BeforeValidator: strip + upper; blank stays blank for pattern 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().upper()


def validate_document_prefix_value(value: str) -> str:
    """AfterValidator: align with doc_numbers._PREFIX_RE / normalize_prefix."""
    from app.doc_numbers import _PREFIX_RE

    if not value or not _PREFIX_RE.match(value):
        raise ValueError(
            "Document prefix must be 1–20 chars: letters, digits, underscore, or hyphen"
        )
    return value


# Shared by DocumentNumberingFields + legacy SalesInvoiceNumberingUpdate / SalesSettingsUpdate.prefix.
DocumentPrefixValue = Annotated[
    str,
    BeforeValidator(coerce_document_prefix_value),
    AfterValidator(validate_document_prefix_value),
]


class SalesInvoiceNumberingUpdate(BaseModel):
    """Legacy flat body for invoice-only PATCH /sales/settings."""

    prefix: DocumentPrefixValue
    next_number: int = Field(default=1, ge=1, le=999999)


class DocumentNumberingFields(BaseModel):
    """Nested numbering PATCH — prefix ∈ DocumentPrefixValue (BR-20.4).

    Blank/`!!!`/`JE!`/`a b` → **422** (was free `str` min_length=1; service
    `normalize_prefix` late **400**). Strip + upper at schema boundary.
    """

    prefix: DocumentPrefixValue
    next_number: int = Field(default=1, ge=1, le=999999)


class SalesSettingsUpdate(BaseModel):
    invoice_numbering: DocumentNumberingFields | None = None
    quotation_numbering: DocumentNumberingFields | None = None
    sales_order_numbering: DocumentNumberingFields | None = None
    sales_return_numbering: DocumentNumberingFields | None = None
    credit_note_numbering: DocumentNumberingFields | None = None
    payment_receipt_numbering: DocumentNumberingFields | None = None
    # Legacy flat fields (invoice only)
    prefix: DocumentPrefixValue | None = None
    next_number: int | None = Field(default=None, ge=1, le=999999)


class PurchasingNumberingUpdate(BaseModel):
    purchase_order_numbering: DocumentNumberingFields | None = None
    grn_numbering: DocumentNumberingFields | None = None
    purchase_invoice_numbering: DocumentNumberingFields | None = None
    purchase_request_numbering: DocumentNumberingFields | None = None
    purchase_return_numbering: DocumentNumberingFields | None = None
    debit_note_numbering: DocumentNumberingFields | None = None
    supplier_payment_numbering: DocumentNumberingFields | None = None


class AccountingSettingsUpdate(BaseModel):
    journal_numbering: DocumentNumberingFields | None = None
    cash_transfer_numbering: DocumentNumberingFields | None = None


class PosSettingsUpdate(BaseModel):
    pos_sale_numbering: DocumentNumberingFields | None = None
    pos_session_numbering: DocumentNumberingFields | None = None


class PrintBrandingUpdate(BaseModel):
    header_text: str | None = Field(default=None, max_length=200)
    footer_text: str | None = Field(default=None, max_length=300)
    # BR-20.4 — schema Literals; omit = no change; blank/invalid → 422
    # (read path still coerces stored garbage to a4/80mm defaults)
    default_invoice_template: InvoiceTemplateValue | None = None
    default_receipt_paper: ReceiptPaperValue | None = None


class BackupSettingsUpdate(BaseModel):
    """Logical backup schedule settings (BR-16)."""

    enabled: bool | None = None
    # Schema Literal; omit = no change; blank/invalid → 422 (was free dict str → service 400)
    frequency: Annotated[
        Literal["daily", "weekly"],
        BeforeValidator(coerce_package_code_value),
    ] | None = None
    retention_count: int | None = Field(default=None, ge=1, le=365)
    hour_utc: int | None = Field(default=None, ge=0, le=23)


class BackupCreateBody(BaseModel):
    """POST /backup — typed create body (BR-16).

    Optional `notes` ∈ BackupNotesValue; omit/`null` → no notes; blank/`!!!`/
    `http://…` → **422** (was free `str` max_length=500; blank/garbage could
    persist on BackupJob.notes).
    """

    model_config = ConfigDict(extra="forbid")

    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`
    # max_length=500; blank/garbage could persist on BackupJob.notes).
    notes: BackupNotesValue | None = None


class BackupVerifyBody(BaseModel):
    """POST /backup/{id}/verify — typed sample limit (BR-16).

    Unknown keys → **422**. `sample_limit` outside 1–500 → **422** (was silent clamp).
    """

    model_config = ConfigDict(extra="forbid")

    sample_limit: int = Field(default=100, ge=1, le=500)


class BackupRestoreBody(BaseModel):
    """POST /backup/{id}/restore — typed dry-run / apply guard (BR-16).

    Unknown keys → **422**. Destructive apply requires `confirm_text="RESTORE"`
    (schema **422**; was late route **400** via free `dict`).
    """

    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True
    confirm: bool = False
    confirm_text: Literal["RESTORE"] | None = None

    @model_validator(mode="after")
    def _require_restore_confirm_text(self) -> BackupRestoreBody:
        if self.confirm and not self.dry_run and self.confirm_text != "RESTORE":
            raise ValueError(
                'Destructive restore requires confirm=true, dry_run=false, and confirm_text="RESTORE"'
            )
        return self


ScheduleFrequencyValue = Annotated[
    Literal["daily", "weekly"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.jobs.JOB_HANDLERS keys (Jobs console Run sync / Enqueue).
JobNameValue = Annotated[
    Literal[
        "scan_low_stock",
        "scan_payment_due",
        "scan_quotation_expiry",
        "scan_recurring_expense_due",
        "generate_recurring_expenses",
        "run_due_backups",
        "scan_trial_lifecycle",
        "run_due_report_emails",
        "refresh_fx_rates",
        "sync_bank_feeds",
        "archive_cold_audit_logs",
        "retry_due_webhooks",
        "scan_ai_security_alerts",
        "send_weekly_ai_insight_digest",
    ],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.onboarding.VALID_STEP_IDS / STEP_DEFS (Getting started Skip).
OnboardingStepIdValue = Annotated[
    Literal[
        "setup_company",
        "add_products",
        "create_supplier",
        "stock_ready",
        "first_sale",
    ],
    BeforeValidator(coerce_package_code_value),
]
ReportExportFormatValue = Annotated[
    Literal["csv", "pdf", "xlsx"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.reports.balance_sheet compare modes (Reports BS select).
BalanceSheetCompareValue = Annotated[
    Literal["prior_period", "prior_year"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with GET /credit/aging kind (Credit Receivables/Payables toggle).
CreditAgingKindValue = Annotated[
    Literal["receivable", "payable"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.reports.SUPPORTED_VALUATION_METHODS (Reports Inventory valuation).
InventoryValuationMethodValue = Annotated[
    Literal["standard"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.cheques.DIRECTIONS / STATUSES (Accounting Cheques filters).
ChequeDirectionValue = Annotated[
    Literal["received", "issued"],
    BeforeValidator(coerce_package_code_value),
]
ChequeStatusValue = Annotated[
    Literal["pending", "deposited", "cleared", "bounced", "cancelled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with api._PARTY_STATUSES / PartyCreate.status (Sales/Purchasing manage filters).
PartyStatusValue = Annotated[
    Literal["active", "inactive"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.stock_counts.COUNT_STATUSES (Reports Inventory count variances).
StockCountReportStatusValue = Annotated[
    Literal["draft", "completed", "cancelled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.reports.TRANSFER_REPORT_STATUSES (Reports Inventory transfers).
TransferReportStatusValue = Annotated[
    Literal["draft", "requested", "in_transit", "received", "cancelled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.reports.PENDING_PO_STATUSES (Reports Purchases pending orders).
PendingPoReportStatusValue = Annotated[
    Literal["draft", "sent", "partially_received"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.purchasing.PO_MANAGE_STATUSES (Purchasing Orders manage list).
PurchaseOrderStatusValue = Annotated[
    Literal["draft", "sent", "partially_received", "received", "cancelled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.purchasing.PI_MANAGE_STATUSES (Purchasing Invoices manage list).
PurchaseInvoiceStatusValue = Annotated[
    Literal["draft", "unpaid", "partial", "paid", "overdue", "cancelled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.sales.SI_MANAGE_STATUSES (Sales Invoices manage list).
SalesInvoiceStatusValue = Annotated[
    Literal["draft", "posted", "sent", "partial", "paid", "overdue", "cancelled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.purchase_requests.PR_MANAGE_STATUSES (Purchasing Requests manage list).
PurchaseRequestStatusValue = Annotated[
    Literal["draft", "pending", "approved", "rejected", "converted"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.sales_docs.QT_MANAGE_STATUSES (Sales Quotations manage list).
SalesQuotationStatusValue = Annotated[
    Literal["draft", "sent", "accepted", "rejected", "expired", "converted"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.sales_docs.SO_MANAGE_STATUSES (Sales Orders manage list).
SalesOrderStatusValue = Annotated[
    Literal[
        "draft",
        "confirmed",
        "processing",
        "shipped",
        "delivered",
        "invoiced",
        "cancelled",
    ],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.reports.RETURN_REPORT_STATUSES (Reports sales/purchase returns).
ReturnReportStatusValue = Annotated[
    Literal["draft", "posted", "cancelled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.tenants.VALID_STATUSES (Platform tenants list filter).
TenantStatusFilterValue = Annotated[
    Literal["trial", "active", "grace", "suspended"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.api_keys.list_keys status filter (Integrations API keys).
ApiKeyStatusFilterValue = Annotated[
    Literal["active", "revoked", "expired"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with expense.status (Expenses list manage filter).
ExpenseStatusFilterValue = Annotated[
    Literal["pending", "approved", "rejected"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with JournalEntry.status (Accounting Ledger Recent journals filter).
JournalStatusFilterValue = Annotated[
    Literal["posted", "unposted"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with CashTransfer.kind / CashTransferCreate.kind (Cash & Bank movements filter).
CashTransferKindFilterValue = Annotated[
    Literal["transfer", "deposit", "withdrawal"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with PosSession.status (POS Recent shifts filter). Runtime open|closed only.
PosSessionStatusFilterValue = Annotated[
    Literal["open", "closed"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with BankStatement.status (Accounting Reconcile statements filter).
BankStatementStatusFilterValue = Annotated[
    Literal["draft", "in_progress", "reconciled"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with BackupJob.status (Backup jobs list filter).
BackupJobStatusFilterValue = Annotated[
    Literal["pending", "completed", "failed", "restoring"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.webhooks STATUS_* (Integrations delivery history filter).
WebhookDeliveryStatusFilterValue = Annotated[
    Literal["pending", "pending_retry", "delivered", "failed"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.audit.AUDIT_MODULES (Audit Logs module filter).
AuditModuleValue = Annotated[
    Literal[
        "accounting",
        "ai",
        "audit",
        "auth",
        "backup",
        "company",
        "credit",
        "dashboard",
        "expenses",
        "inventory",
        "notifications",
        "onboarding",
        "platform_staff",
        "pos",
        "purchasing",
        "reports",
        "sales",
        "security",
        "settings",
        "stores",
        "system",
        "tax",
        "tenants",
        "users",
        "webhooks",
    ],
    BeforeValidator(coerce_package_code_value),
]


def coerce_audit_action_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for shape 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def validate_audit_action_value(value: str) -> str:
    """AfterValidator: snake_case action shape; digit-start OK for 2fa_* (not RoleKeyValue)."""
    import re

    # Allow digit start so recorded actions like 2fa_failed / 2fa_enabled stay filterable.
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]{1,62}", value or ""):
        raise ValueError(
            "action must be lowercase letters/numbers/underscore, 2–63 chars "
            "(may start with a digit)"
        )
    return value


# Shape-only Audit Logs action Query (not a closed Literal — ~120 growing writers).
AuditActionValue = Annotated[
    str,
    BeforeValidator(coerce_audit_action_value),
    AfterValidator(validate_audit_action_value),
]


def coerce_iso_date_query_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for date 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_iso_date_query_value(value: str) -> str:
    """AfterValidator: YYYY-MM-DD (or ISO datetime); blank/invalid → 422."""
    if not value:
        raise ValueError("date must be YYYY-MM-DD")
    try:
        if len(value) == 10:
            datetime.strptime(value, "%Y-%m-%d")
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    return value


# Keep aligned with app.reports.parse_date (Audit + inventory movement + P&L + cash-flow + BS/TB as_of + reports/export + tax report + expenses report + sales products/customers + purchases summary/suppliers + purchases pending/returns + sales returns/salesperson + sales by-store/by-department + inventory transfers/stock-counts + customer/supplier history + AI sales/expenses analysis + sales daily + bank statement dates + AI document draft expense_date/invoice_date + payment cheque_date + purchase invoice PATCH invoice_date/due_date + expense expense_date + GRN line manufacturing_date/expiry_date + stock-in/opening-stock manufacturing_date/expiry_date + SO delivery_date + PO amend due_date + PR required_date + API key expires_at + subscription start_at + report date Query filters).
IsoDateQueryValue = Annotated[
    str,
    BeforeValidator(coerce_iso_date_query_value),
    AfterValidator(validate_iso_date_query_value),
]


def coerce_e164_phone_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for phone 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_e164_phone_value(value: str) -> str:
    """AfterValidator: E.164 (+ and 8–15 digits); blank/invalid → 422."""
    if not value:
        raise ValueError("phone must be E.164 (+ and 8–15 digits)")
    cleaned = re.sub(r"[^\d+]", "", value)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if not cleaned.startswith("+"):
        raise ValueError("phone must be E.164 (+ and 8–15 digits)")
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError("phone must be E.164 (+ and 8–15 digits)")
    return "+" + digits


# Twilio From / SMS test override — require E.164 with leading +.
E164PhoneValue = Annotated[
    str,
    BeforeValidator(coerce_e164_phone_value),
    AfterValidator(validate_e164_phone_value),
]


def coerce_twilio_account_sid_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for account_sid 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_twilio_account_sid_value(value: str) -> str:
    """AfterValidator: alphanumeric Twilio SID; blank/URL/punctuation → 422.

    Loose (not AC+32hex) so short fixtures like ACtip73 remain valid.
    """
    if not value:
        raise ValueError("account_sid must be alphanumeric (1–64 chars)")
    if len(value) > 64:
        raise ValueError("account_sid must be alphanumeric (1–64 chars)")
    if "://" in value or any(ch.isspace() for ch in value):
        raise ValueError("account_sid must be alphanumeric (1–64 chars)")
    if not re.fullmatch(r"[A-Za-z0-9]+", value):
        raise ValueError("account_sid must be alphanumeric (1–64 chars)")
    return value


# Twilio Account SID — alphanumeric 1–64 (fixtures may be short; not strict AC+32hex).
TwilioAccountSidValue = Annotated[
    str,
    BeforeValidator(coerce_twilio_account_sid_value),
    AfterValidator(validate_twilio_account_sid_value),
]


def coerce_smtp_host_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for host 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_smtp_host_value(value: str) -> str:
    """AfterValidator: DNS hostname / IPv4 / localhost; blank/URL/garbage → 422."""
    if not value:
        raise ValueError("host must be a hostname (e.g. smtp.example.com or 127.0.0.1)")
    if len(value) > 253:
        raise ValueError("host must be a hostname (e.g. smtp.example.com or 127.0.0.1)")
    lowered = value.lower()
    if "://" in lowered or "@" in lowered or any(ch.isspace() for ch in value):
        raise ValueError("host must be a hostname (e.g. smtp.example.com or 127.0.0.1)")
    # localhost, dotted IPv4, or DNS labels (letters/digits/hyphen, dots between).
    if not re.fullmatch(
        r"(?:localhost|(?:\d{1,3}\.){3}\d{1,3}|(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)",
        lowered,
    ):
        raise ValueError("host must be a hostname (e.g. smtp.example.com or 127.0.0.1)")
    return lowered


# Company SMTP host — hostname/IPv4/localhost (no URL scheme / email / spaces).
SmtpHostValue = Annotated[
    str,
    BeforeValidator(coerce_smtp_host_value),
    AfterValidator(validate_smtp_host_value),
]


def coerce_bank_account_number_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for account_number 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_bank_account_number_value(value: str) -> str:
    """AfterValidator: alphanumeric (+ spaces/hyphens); blank/URL/garbage → 422."""
    if not value:
        raise ValueError(
            "account_number must be alphanumeric (optional spaces/hyphens)"
        )
    if len(value) > 64:
        raise ValueError(
            "account_number must be alphanumeric (optional spaces/hyphens)"
        )
    if "://" in value or "@" in value:
        raise ValueError(
            "account_number must be alphanumeric (optional spaces/hyphens)"
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,63}", value):
        raise ValueError(
            "account_number must be alphanumeric (optional spaces/hyphens)"
        )
    return value


# Liquid bank COA account_number — digits/letters with optional spaces/hyphens.
BankAccountNumberValue = Annotated[
    str,
    BeforeValidator(coerce_bank_account_number_value),
    AfterValidator(validate_bank_account_number_value),
]


def validate_tax_registration_number_value(value: str) -> str:
    """AfterValidator: TIN/VAT id; blank/URL/garbage → 422 (max 40 for DB)."""
    if not value:
        raise ValueError(
            "tax_registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    if len(value) > 40:
        raise ValueError(
            "tax_registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    if "://" in value or "@" in value:
        raise ValueError(
            "tax_registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,39}", value):
        raise ValueError(
            "tax_registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    return value


# Company TIN / VAT registration number — alphanumeric + optional spaces/hyphens (max 40).
TaxRegistrationNumberValue = Annotated[
    str,
    BeforeValidator(coerce_bank_account_number_value),
    AfterValidator(validate_tax_registration_number_value),
]


def validate_registration_number_value(value: str) -> str:
    """AfterValidator: company registration id; blank/URL/garbage → 422 (max 80)."""
    if not value:
        raise ValueError(
            "registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    if len(value) > 80:
        raise ValueError(
            "registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    if "://" in value or "@" in value:
        raise ValueError(
            "registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,79}", value):
        raise ValueError(
            "registration_number must be alphanumeric (optional spaces/hyphens)"
        )
    return value


# Company registration number — alphanumeric + optional spaces/hyphens (max 80).
RegistrationNumberValue = Annotated[
    str,
    BeforeValidator(coerce_bank_account_number_value),
    AfterValidator(validate_registration_number_value),
]


def coerce_bank_name_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for bank_name 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_bank_name_value(value: str) -> str:
    """AfterValidator: non-empty bank label; blank/URL/punctuation-only → 422."""
    if not value:
        raise ValueError("bank_name must be a non-empty bank name")
    if len(value) > 120:
        raise ValueError("bank_name must be a non-empty bank name")
    if "://" in value or "@" in value:
        raise ValueError("bank_name must be a non-empty bank name")
    # Require at least one letter or digit (reject "!!!", "---", "...")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("bank_name must be a non-empty bank name")
    return value


# Liquid bank COA bank_name — human label (max 120; no URL/email).
BankNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_bank_name_value),
]


def validate_account_name_value(value: str) -> str:
    """AfterValidator: COA display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("account name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("account name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("account name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("account name must be a non-empty label (1–150 chars)")
    return value


# Chart-of-accounts display name — matches Account.name String(150).
AccountNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_account_name_value),
]


def validate_party_name_value(value: str) -> str:
    """AfterValidator: customer/supplier display name; blank/URL/garbage → 422 (1–180)."""
    if not value:
        raise ValueError("party name must be a non-empty label (1–180 chars)")
    if len(value) > 180:
        raise ValueError("party name must be a non-empty label (1–180 chars)")
    if "://" in value or "@" in value:
        raise ValueError("party name must be a non-empty label (1–180 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("party name must be a non-empty label (1–180 chars)")
    return value


# Party (customer/supplier) display name — matches Party.name String(180).
PartyNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_party_name_value),
]


def validate_product_name_value(value: str) -> str:
    """AfterValidator: product display name; blank/URL/garbage → 422 (1–200)."""
    if not value:
        raise ValueError("product name must be a non-empty label (1–200 chars)")
    if len(value) > 200:
        raise ValueError("product name must be a non-empty label (1–200 chars)")
    if "://" in value or "@" in value:
        raise ValueError("product name must be a non-empty label (1–200 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("product name must be a non-empty label (1–200 chars)")
    return value


# Catalog product display name — matches Product.name String(200).
ProductNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_product_name_value),
]


# Keep aligned with app.barcodes.BARCODE_PATTERN / normalize_barcode (Code 128 family).
_PRODUCT_BARCODE_RE = re.compile(r"^[A-Za-z0-9\-._]{4,48}$")


def validate_product_barcode_value(value: str) -> str:
    """AfterValidator: product/variant barcode; blank/pattern fail → 422 (4–48)."""
    if not value:
        raise ValueError("product barcode must be 4–48 characters (letters, numbers, - . _)")
    code = value.upper()
    if not _PRODUCT_BARCODE_RE.match(code):
        raise ValueError("product barcode must be 4–48 characters (letters, numbers, - . _)")
    return code


# Product / variant barcode — String(100) column; API pattern 4–48 like normalize_barcode.
ProductBarcodeValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_product_barcode_value),
]


def validate_product_description_value(value: str) -> str:
    """AfterValidator: product catalog narrative; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("product description must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("product description must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("product description must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("product description must be a non-empty narrative (1–500 chars)")
    return value


# Product description — Product.description Text; keep ≤500 at API boundary.
ProductDescriptionValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_product_description_value),
]


def validate_brand_description_value(value: str) -> str:
    """AfterValidator: brand catalog narrative; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("brand description must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("brand description must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("brand description must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("brand description must be a non-empty narrative (1–500 chars)")
    return value


# Brand description — Brand.description Text; keep ≤500 at API boundary.
BrandDescriptionValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_brand_description_value),
]


def validate_stock_transfer_notes_value(value: str) -> str:
    """AfterValidator: stock transfer notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("stock transfer notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("stock transfer notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("stock transfer notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("stock transfer notes must be a non-empty narrative (1–500 chars)")
    return value


# Stock transfer notes — StockTransfer.notes Text; keep ≤500 at API boundary.
StockTransferNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_stock_transfer_notes_value),
]


def validate_stock_adjust_notes_value(value: str) -> str:
    """AfterValidator: stock adjustment notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("stock adjustment notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("stock adjustment notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("stock adjustment notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("stock adjustment notes must be a non-empty narrative (1–500 chars)")
    return value


# Stock adjustment notes — StockMovement.notes Text; keep ≤500 at API boundary.
StockAdjustNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_stock_adjust_notes_value),
]


def validate_stock_out_notes_value(value: str) -> str:
    """AfterValidator: stock-out notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("stock-out notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("stock-out notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("stock-out notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("stock-out notes must be a non-empty narrative (1–500 chars)")
    return value


# Stock-out notes — StockMovement.notes Text; keep ≤500 at API boundary.
StockOutNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_stock_out_notes_value),
]


def validate_stock_in_notes_value(value: str) -> str:
    """AfterValidator: stock-in notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("stock-in notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("stock-in notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("stock-in notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("stock-in notes must be a non-empty narrative (1–500 chars)")
    return value


# Stock-in notes — StockMovement.notes Text; keep ≤500 at API boundary.
StockInNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_stock_in_notes_value),
]


def validate_store_name_value(value: str) -> str:
    """AfterValidator: store display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("store name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("store name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("store name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("store name must be a non-empty label (1–150 chars)")
    return value


# Multi-store display name — matches Store.name String(150).
StoreNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_store_name_value),
]


def validate_warehouse_name_value(value: str) -> str:
    """AfterValidator: warehouse display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("warehouse name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("warehouse name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("warehouse name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("warehouse name must be a non-empty label (1–150 chars)")
    return value


# Warehouse display name — matches Warehouse.name String(150).
WarehouseNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_warehouse_name_value),
]


def validate_branch_name_value(value: str) -> str:
    """AfterValidator: branch display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("branch name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("branch name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("branch name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("branch name must be a non-empty label (1–150 chars)")
    return value


# Branch display name — matches Branch.name String(150).
BranchNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_branch_name_value),
]


def validate_brand_name_value(value: str) -> str:
    """AfterValidator: brand display name; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("brand name must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("brand name must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("brand name must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("brand name must be a non-empty label (1–120 chars)")
    return value


# Catalog brand display name — matches Brand.name String(120).
BrandNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_brand_name_value),
]


def validate_category_name_value(value: str) -> str:
    """AfterValidator: product category display name; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("category name must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("category name must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("category name must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("category name must be a non-empty label (1–120 chars)")
    return value


# Catalog product-category display name — matches ProductCategory.name String(120).
CategoryNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_category_name_value),
]


def validate_unit_name_value(value: str) -> str:
    """AfterValidator: unit-of-measure display name; blank/URL/garbage → 422 (1–80)."""
    if not value:
        raise ValueError("unit name must be a non-empty label (1–80 chars)")
    if len(value) > 80:
        raise ValueError("unit name must be a non-empty label (1–80 chars)")
    if "://" in value or "@" in value:
        raise ValueError("unit name must be a non-empty label (1–80 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("unit name must be a non-empty label (1–80 chars)")
    return value


# Catalog unit-of-measure display name — matches UnitOfMeasure.name String(80).
UnitNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_unit_name_value),
]


def validate_department_name_value(value: str) -> str:
    """AfterValidator: department display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("department name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("department name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("department name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("department name must be a non-empty label (1–150 chars)")
    return value


# Department display name — matches Department.name String(150).
DepartmentNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_department_name_value),
]


def validate_variant_name_value(value: str) -> str:
    """AfterValidator: product variant display name; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("variant name must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("variant name must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("variant name must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("variant name must be a non-empty label (1–120 chars)")
    return value


# Product variant display name — matches ProductVariant.name String(120).
VariantNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_variant_name_value),
]


def validate_customer_group_name_value(value: str) -> str:
    """AfterValidator: customer group display name; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("customer group name must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("customer group name must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("customer group name must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("customer group name must be a non-empty label (1–120 chars)")
    return value


# Customer group display name — matches CustomerGroup.name String(120).
CustomerGroupNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_customer_group_name_value),
]


def validate_tax_rate_name_value(value: str) -> str:
    """AfterValidator: tax rate display name; blank/URL/garbage → 422 (1–80)."""
    if not value:
        raise ValueError("tax rate name must be a non-empty label (1–80 chars)")
    if len(value) > 80:
        raise ValueError("tax rate name must be a non-empty label (1–80 chars)")
    if "://" in value or "@" in value:
        raise ValueError("tax rate name must be a non-empty label (1–80 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("tax rate name must be a non-empty label (1–80 chars)")
    return value


# Tax rate display name — matches TaxRate.name String(80).
TaxRateNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_tax_rate_name_value),
]


def validate_expense_category_name_value(value: str) -> str:
    """AfterValidator: expense category display name; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("expense category name must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("expense category name must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("expense category name must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("expense category name must be a non-empty label (1–120 chars)")
    return value


# Expense category display name — matches ExpenseCategory.name String(120).
ExpenseCategoryNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_expense_category_name_value),
]


def validate_party_contact_name_value(value: str) -> str:
    """AfterValidator: party contact display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("party contact name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("party contact name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("party contact name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("party contact name must be a non-empty label (1–150 chars)")
    return value


# Party contact display name — matches PartyContact.name String(150).
PartyContactNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_party_contact_name_value),
]


def validate_platform_staff_full_name_value(value: str) -> str:
    """AfterValidator: platform staff display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("platform staff full name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("platform staff full name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("platform staff full name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("platform staff full name must be a non-empty label (1–150 chars)")
    return value


# Platform staff full name — matches User.full_name String(150).
PlatformStaffFullNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_platform_staff_full_name_value),
]


def validate_user_full_name_value(value: str) -> str:
    """AfterValidator: tenant user display name; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("user full name must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("user full name must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("user full name must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("user full name must be a non-empty label (1–150 chars)")
    return value


# Tenant user full name — matches User.full_name String(150).
UserFullNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_user_full_name_value),
]


def validate_party_contact_designation_value(value: str) -> str:
    """AfterValidator: party contact designation; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("party contact designation must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("party contact designation must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("party contact designation must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("party contact designation must be a non-empty label (1–120 chars)")
    return value


# Party contact designation — matches PartyContact.designation String(120).
PartyContactDesignationValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_party_contact_designation_value),
]


def validate_custom_role_label_value(value: str) -> str:
    """AfterValidator: custom role display label; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("custom role label must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("custom role label must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("custom role label must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("custom role label must be a non-empty label (1–120 chars)")
    return value


# Custom role display label — matches CustomRole.label String(120).
CustomRoleLabelValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_custom_role_label_value),
]


def validate_approval_level_label_value(value: str) -> str:
    """AfterValidator: approval matrix level label; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("approval level label must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("approval level label must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("approval level label must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("approval level label must be a non-empty label (1–120 chars)")
    return value


# Expense / PR approval matrix level label — stored in tenant settings JSON.
ApprovalLevelLabelValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_approval_level_label_value),
]


def validate_bank_connection_display_name_value(value: str) -> str:
    """AfterValidator: bank connection display name; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("bank connection display name must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("bank connection display name must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("bank connection display name must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("bank connection display name must be a non-empty label (1–120 chars)")
    return value


# Bank connection display name — matches BankConnection.display_name String(120).
BankConnectionDisplayNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_bank_connection_display_name_value),
]


def validate_pos_customer_name_value(value: str) -> str:
    """AfterValidator: POS walk-in customer name; blank/URL/garbage → 422 (1–180)."""
    if not value:
        raise ValueError("POS customer name must be a non-empty label (1–180 chars)")
    if len(value) > 180:
        raise ValueError("POS customer name must be a non-empty label (1–180 chars)")
    if "://" in value or "@" in value:
        raise ValueError("POS customer name must be a non-empty label (1–180 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("POS customer name must be a non-empty label (1–180 chars)")
    return value


# POS walk-in receipt name — matches PosSaleCreate.customer_name max 180.
PosCustomerNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_pos_customer_name_value),
]


def validate_pos_session_close_notes_value(value: str) -> str:
    """AfterValidator: POS shift close notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("POS shift close notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("POS shift close notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("POS shift close notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("POS shift close notes must be a non-empty narrative (1–500 chars)")
    return value


# POS session close notes — PosSession.notes Text; keep ≤500 at API boundary.
PosSessionCloseNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_pos_session_close_notes_value),
]


def validate_api_key_name_value(value: str) -> str:
    """AfterValidator: API key display name; blank/URL/garbage/short → 422 (2–120)."""
    if not value or len(value) < 2 or len(value) > 120:
        raise ValueError("API key name must be a non-empty label (2–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("API key name must be a non-empty label (2–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("API key name must be a non-empty label (2–120 chars)")
    return value


# API key display name — matches ApiKeyCreate.name (2–120).
ApiKeyNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_api_key_name_value),
]


def validate_ai_report_template_name_value(value: str) -> str:
    """AfterValidator: AI report template name; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError("AI report template name must be a non-empty label (1–120 chars)")
    if len(value) > 120:
        raise ValueError("AI report template name must be a non-empty label (1–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("AI report template name must be a non-empty label (1–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("AI report template name must be a non-empty label (1–120 chars)")
    return value


# AI report template display name — matches AiReportTemplate.name String(120).
AiReportTemplateNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_ai_report_template_name_value),
]


def validate_account_code_value(value: str) -> str:
    """AfterValidator: COA code; blank/garbage → 422 (1–30; alnum/_/-)."""
    if not value:
        raise ValueError(
            "account code must be 1–30 chars: letters, digits, underscore, or hyphen"
        )
    if len(value) > 30 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,29}", value):
        raise ValueError(
            "account code must be 1–30 chars: letters, digits, underscore, or hyphen"
        )
    return value


# Chart-of-accounts code — matches Account.code String(30); no forced upper.
AccountCodeValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_account_code_value),
]


def validate_smtp_from_name_value(value: str) -> str:
    """AfterValidator: non-empty From display name; blank/URL/punctuation-only → 422."""
    if not value:
        raise ValueError("from_name must be a non-empty display name")
    if len(value) > 120:
        raise ValueError("from_name must be a non-empty display name")
    if "://" in value or "@" in value:
        raise ValueError("from_name must be a non-empty display name")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("from_name must be a non-empty display name")
    return value


# Company SMTP From display name — human label (max 120; no URL/email).
SmtpFromNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_smtp_from_name_value),
]


def validate_contact_person_value(value: str) -> str:
    """AfterValidator: non-empty person name; blank/URL/punctuation-only → 422 (max 150)."""
    if not value:
        raise ValueError("contact_person must be a non-empty person name")
    if len(value) > 150:
        raise ValueError("contact_person must be a non-empty person name")
    if "://" in value or "@" in value:
        raise ValueError("contact_person must be a non-empty person name")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("contact_person must be a non-empty person name")
    return value


# Company primary contact person — human label (max 150; no URL/email).
ContactPersonValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_contact_person_value),
]


def validate_legal_name_value(value: str) -> str:
    """AfterValidator: legal entity name; blank/URL/short/garbage → 422 (2–200)."""
    if not value:
        raise ValueError("legal_name must be a non-empty legal name (2–200 chars)")
    if len(value) < 2 or len(value) > 200:
        raise ValueError("legal_name must be a non-empty legal name (2–200 chars)")
    if "://" in value or "@" in value:
        raise ValueError("legal_name must be a non-empty legal name (2–200 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("legal_name must be a non-empty legal name (2–200 chars)")
    return value


# Company legal name — human label (2–200; no URL/email).
LegalNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_legal_name_value),
]


def validate_company_name_value(value: str) -> str:
    """AfterValidator: trading name; blank/URL/short/garbage → 422 (2–200)."""
    if not value:
        raise ValueError("company_name must be a non-empty trading name (2–200 chars)")
    if len(value) < 2 or len(value) > 200:
        raise ValueError("company_name must be a non-empty trading name (2–200 chars)")
    if "://" in value or "@" in value:
        raise ValueError("company_name must be a non-empty trading name (2–200 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("company_name must be a non-empty trading name (2–200 chars)")
    return value


# Company trading name — required identity label (2–200; no URL/email).
CompanyNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_company_name_value),
]


def validate_address_value(value: str) -> str:
    """AfterValidator: non-empty postal/physical address; blank/URL/garbage → 422 (max 500)."""
    if not value:
        raise ValueError("address must be a non-empty postal address")
    if len(value) > 500:
        raise ValueError("address must be a non-empty postal address")
    if "://" in value or "@" in value:
        raise ValueError("address must be a non-empty postal address")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("address must be a non-empty postal address")
    return value


# Company HQ / billing / shipping address — postal label (max 500; no URL/email).
AddressValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_address_value),
]


def validate_smtp_username_value(value: str) -> str:
    """AfterValidator: non-empty SMTP login; blank/URL/punctuation-only → 422.

    Email-shaped usernames (`ops@smtp.example.com`) are allowed; URLs are not.
    """
    if not value:
        raise ValueError("username must be a non-empty SMTP login")
    if len(value) > 200:
        raise ValueError("username must be a non-empty SMTP login")
    if "://" in value:
        raise ValueError("username must be a non-empty SMTP login")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("username must be a non-empty SMTP login")
    return value


# Company SMTP username — plain login or email-shaped (max 200; no URL scheme).
SmtpUsernameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_smtp_username_value),
]


def validate_bank_branch_value(value: str) -> str:
    """AfterValidator: non-empty branch label; blank/URL/punctuation-only → 422."""
    if not value:
        raise ValueError("bank_branch must be a non-empty branch name")
    if len(value) > 120:
        raise ValueError("bank_branch must be a non-empty branch name")
    if "://" in value or "@" in value:
        raise ValueError("bank_branch must be a non-empty branch name")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("bank_branch must be a non-empty branch name")
    return value


# Liquid bank COA bank_branch — human label (max 120; no URL/email).
BankBranchValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_bank_branch_value),
]


def coerce_cheque_number_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for cheque_number 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_cheque_number_value(value: str) -> str:
    """AfterValidator: cheque ref (max 50); blank/URL/garbage → 422."""
    if not value:
        raise ValueError(
            "cheque_number must be alphanumeric (optional spaces/hyphens)"
        )
    if len(value) > 50:
        raise ValueError(
            "cheque_number must be alphanumeric (optional spaces/hyphens)"
        )
    if "://" in value or "@" in value:
        raise ValueError(
            "cheque_number must be alphanumeric (optional spaces/hyphens)"
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,49}", value):
        raise ValueError(
            "cheque_number must be alphanumeric (optional spaces/hyphens)"
        )
    return value


# Customer/supplier payment cheque_number — short cheque ref (max 50).
ChequeNumberValue = Annotated[
    str,
    BeforeValidator(coerce_cheque_number_value),
    AfterValidator(validate_cheque_number_value),
]


class ApiKeyCreate(BaseModel):
    """POST /api-keys — typed create body (BR-18.1).

    Unknown top-level keys → **422** (`extra=forbid`). Name ∈ `ApiKeyNameValue`
    (strip; 2–120; ≥1 letter/digit; no `://`/`@`); omit/too short/`!!!`/URL → **422**
    (was free `str` min_length=2; punctuation/URL could persist). Invalid `expires_at`,
    unknown permission module/action → **422** (was late **400** via free `dict`).
    Omit/null/`{}` `permissions` → service default read map.

    Optional `expires_at` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime);
    omit/`null` → no expiry; blank/`not-a-date`/`01/02/2024` → **422** (was free
    `datetime`; OpenAPI date-time; padded dates inconsistent). API
    `reports.parse_datetime` keeps clock time (defense-in-depth).
    """

    model_config = ConfigDict(extra="forbid")

    # Required key label ∈ ApiKeyNameValue; blank/`!!!`/`http://…`/`x` → **422**
    # (was free `str` min_length=2; punctuation/URL could persist).
    name: ApiKeyNameValue
    permissions: dict[str, list[ApiKeyPermissionAction]] | None = None
    expires_at: IsoDateQueryValue | None = None

    @field_validator("permissions", mode="before")
    @classmethod
    def _normalize_permissions_input(cls, value: object) -> object:
        # Preserve historical create_key behavior: falsy/empty map → defaults.
        if value == {} or value is False:
            return None
        if not isinstance(value, dict):
            return value
        out: dict[str, list[object]] = {}
        for module, actions in value.items():
            mod = str(module).strip().lower() if module is not None else module
            if isinstance(actions, (list, tuple)):
                out[mod] = [
                    a.strip().lower() if isinstance(a, str) else a for a in actions
                ]
            else:
                out[mod] = actions  # type: ignore[assignment]
        return out

    @model_validator(mode="after")
    def _permissions_modules(self) -> ApiKeyCreate:
        if self.permissions is None:
            return self
        if not self.permissions:
            raise ValueError("permissions must include at least one module")
        for module, actions in self.permissions.items():
            if module not in SYSTEM_MODULES:
                raise ValueError(f"Invalid permission module: {module}")
            if not actions:
                raise ValueError(f"Invalid actions for module: {module}")
        return self


# Keep aligned with app.sales_docs.RETURN_REASONS (Reports sales returns reason filter).
SalesReturnReportReasonValue = Annotated[
    Literal["damaged", "wrong_item", "defective", "customer_change", "other"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.purchasing.PURCHASE_RETURN_REASONS (Reports purchase returns reason).
PurchaseReturnReportReasonValue = Annotated[
    Literal["damaged", "wrong_item", "expiry", "quality", "other"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.inventory.MOVEMENT_TYPES (Inventory/Reports movements filter).
MovementTypeValue = Annotated[
    Literal[
        "stock_in",
        "stock_out",
        "opening_stock",
        "adjustment",
        "transfer_out",
        "transfer_in",
        "transfer_cancel",
    ],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.inventory.STOCK_ADJUSTMENT_REASONS (Inventory Movements reason filter).
StockAdjustReasonValue = Annotated[
    Literal["damage", "theft", "expiry", "found", "lost"],
    BeforeValidator(coerce_package_code_value),
]
# Keep aligned with app.report_export.EXPORTABLE (+ Reports Email schedules select)
ReportTypeValue = Annotated[
    Literal[
        "summary",
        "sales_daily",
        "sales_monthly",
        "sales_products",
        "sales_salesperson",
        "sales_customers",
        "sales_returns",
        "sales_by_store",
        "sales_by_department",
        "inventory_balance",
        "inventory_valuation",
        "inventory_movements",
        "inventory_low_stock",
        "inventory_expiry",
        "inventory_transfers",
        "inventory_stock_counts",
        "purchases_summary",
        "purchases_suppliers",
        "purchases_pending_orders",
        "purchases_returns",
        "expenses_summary",
        "expenses_budget_vs_actual",
        "cash_flow",
        "trial_balance",
        "profit_loss",
        "balance_sheet",
        "tax",
        "tax_filing",
        "tax_filing_gh",
    ],
    BeforeValidator(coerce_package_code_value),
]


class AiReportsGenerateBody(BaseModel):
    """POST /ai/reports/generate — typed report generator body (BR-21.7).

    Unknown keys → **422** (`extra=forbid`). Must provide `prompt`, `template_id`,
    or `report_type` (schema **422**; was late service **422**). Invalid
    `format` / `report_type` → **422** (format garbage was silently remapped to
    csv; unknown report_type was late **400**). `params` is an alias for
    `filters`. Service `generate_report` / `parse_prompt` remain defense-in-depth.
    """

    model_config = ConfigDict(extra="forbid")

    prompt: str | None = None
    format: ReportExportFormatValue | None = None
    template_id: str | None = None
    report_type: ReportTypeValue | None = None
    period: str | None = None
    filters: dict[str, Any] | None = None
    params: dict[str, Any] | None = None

    @field_validator("prompt", "template_id", "period", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value

    @model_validator(mode="after")
    def _require_prompt_template_or_type(self) -> AiReportsGenerateBody:
        if not (self.prompt or self.template_id or self.report_type):
            raise ValueError("Provide prompt, template_id, or report_type")
        return self


class AiReportsExportBody(BaseModel):
    """POST /ai/reports/export — typed export body (BR-21.7).

    Unknown keys → **422** (`extra=forbid`). Must provide `prompt`, `template_id`,
    or `report_type`. `format` ∈ csv|pdf|xlsx (omit → **csv**; blank/invalid →
    **422** — was free `dict` with `or "csv"`). Invalid `report_type` → **422**.
    Service `export_from_intent` remains defense-in-depth.
    """

    model_config = ConfigDict(extra="forbid")

    prompt: str | None = None
    format: ReportExportFormatValue = "csv"
    template_id: str | None = None
    report_type: ReportTypeValue | None = None
    filters: dict[str, Any] | None = None
    params: dict[str, Any] | None = None

    @field_validator("prompt", "template_id", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value

    @model_validator(mode="after")
    def _require_prompt_template_or_type(self) -> AiReportsExportBody:
        if not (self.prompt or self.template_id or self.report_type):
            raise ValueError("Provide prompt, template_id, or report_type")
        return self


class AiReportTemplateCreateBody(BaseModel):
    """POST /ai/reports/templates — typed template create body (BR-21.7).

    Unknown keys → **422** (`extra=forbid`). `name` ∈ `AiReportTemplateNameValue`
    (strip; 1–120; ≥1 letter/digit; no `://`/`@`); blank/`!!!`/`http://…` → **422**
    (was free `str` min_length=1; punctuation/URL could persist). Blank/omit `prompt` →
    **422**. `format` ∈ csv|pdf|xlsx (omit → derived from prompt; blank/invalid →
    **422** — was late **400**). Service `create_template` / `parse_prompt` remain
    defense-in-depth.
    """

    model_config = ConfigDict(extra="forbid")

    name: AiReportTemplateNameValue
    prompt: str = Field(min_length=1)
    format: ReportExportFormatValue | None = None

    @field_validator("prompt", mode="before")
    @classmethod
    def _strip_prompt(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


def coerce_report_schedule_recipients(value: object) -> object:
    """Pydantic BeforeValidator: str/list → stripped email list; blank → ValueError.

    Comma/`;` separated strings expand to multiple addresses. Empty / whitespace-only
    → ValueError (422). Each item is then validated as EmailStr (rejects `bad`,
    `almost@`, etc.). Was free `list[str]|str` with service soft-dropping non-`@`.
    """
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
    elif isinstance(value, (list, tuple)):
        parts = [str(p).strip() for p in value if p is not None and str(p).strip()]
    else:
        return value
    if not parts:
        raise ValueError("at least one recipient email is required")
    return parts


# Create requires ≥1 EmailStr; Update omit/`null` → no change; blank/invalid → **422**.
ReportScheduleRecipientsValue = Annotated[
    list[EmailStr],
    BeforeValidator(coerce_report_schedule_recipients),
]


def validate_report_schedule_name_value(value: str) -> str:
    """AfterValidator: schedule title; blank/URL/short/garbage → 422 (2–120)."""
    if not value:
        raise ValueError("schedule name must be a non-empty label (2–120 chars)")
    if len(value) < 2 or len(value) > 120:
        raise ValueError("schedule name must be a non-empty label (2–120 chars)")
    if "://" in value or "@" in value:
        raise ValueError("schedule name must be a non-empty label (2–120 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("schedule name must be a non-empty label (2–120 chars)")
    return value


# Report schedule display name — matches ReportSchedule.name String(120).
ReportScheduleNameValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_report_schedule_name_value),
]


class ReportScheduleCreate(BaseModel):
    """Email report schedule create (BR-14).

    `name` ∈ ReportScheduleNameValue (strip; 2–120; ≥1 letter/digit; no `://`/`@`);
    blank/`!!!`/`http://…` → **422** (was free `str` min_length=2; whitespace
    late service **400**; punctuation/URL could persist). `recipients` ∈
    ReportScheduleRecipientsValue (`list[EmailStr]` or comma/`;` string); required ≥1;
    blank/`bad` → **422**.
    """

    name: ReportScheduleNameValue
    # Schema Literal; blank/unknown → 422 (was free str → service 400)
    report_type: ReportTypeValue
    format: ReportExportFormatValue = "xlsx"
    # omit → daily; blank/invalid → 422 (was free dict; "" coerced to daily in service)
    frequency: ScheduleFrequencyValue = "daily"
    weekday: int | None = Field(default=None, ge=0, le=6)
    hour_utc: int = Field(default=6, ge=0, le=23)
    recipients: ReportScheduleRecipientsValue
    enabled: bool = True


class ReportScheduleUpdate(BaseModel):
    """Email report schedule patch — omit = no change; blank frequency/format/report_type → 422.

    Optional `name` ∈ ReportScheduleNameValue; omit/`null` → no change; blank/invalid → **422**.
    Optional `recipients` ∈ ReportScheduleRecipientsValue; omit/`null` → no change;
    blank/invalid → **422** (do not clear to empty).
    """

    name: ReportScheduleNameValue | None = None
    report_type: ReportTypeValue | None = None
    format: ReportExportFormatValue | None = None
    frequency: ScheduleFrequencyValue | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    hour_utc: int | None = Field(default=None, ge=0, le=23)
    recipients: ReportScheduleRecipientsValue | None = None
    enabled: bool | None = None


def coerce_webhook_event_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


# Keep aligned with app.webhooks.VALID_EVENTS
WebhookEventValue = Annotated[
    Literal[
        "sale.created",
        "sale.paid",
        "stock.low",
        "stock.in",
        "stock.out",
        "purchase.order.created",
        "purchase.grn.received",
        "customer.created",
        "supplier.created",
        "expense.approved",
        "user.login",
        "tenant.suspended",
        "webhook.test",
    ],
    BeforeValidator(coerce_webhook_event_value),
]


def coerce_webhook_url_value(value: object) -> object:
    """Pydantic BeforeValidator: strip; blank stays blank for URL 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_webhook_url_value(value: str) -> str:
    """AfterValidator: absolute http(s) URL; http only for localhost (BR-18.6)."""
    from urllib.parse import urlparse

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute http(s) URL")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in {
        "localhost",
        "127.0.0.1",
        "testserver",
        "host.docker.internal",
    }:
        raise ValueError("Webhook URL must use HTTPS (http allowed only for localhost)")
    return value


# Keep aligned with app.webhooks.validate_url (Integrations endpoint URL).
# Also reused for BankConnectionCreate/Update.feed_url (Accounting Reconcile).
WebhookUrlValue = Annotated[
    str,
    BeforeValidator(coerce_webhook_url_value),
    AfterValidator(validate_webhook_url_value),
]


def validate_webhook_description_value(value: str) -> str:
    """AfterValidator: webhook endpoint label; blank/URL/garbage → 422 (1–255)."""
    if not value:
        raise ValueError("webhook description must be a non-empty label (1–255 chars)")
    if len(value) > 255:
        raise ValueError("webhook description must be a non-empty label (1–255 chars)")
    if "://" in value or "@" in value:
        raise ValueError("webhook description must be a non-empty label (1–255 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("webhook description must be a non-empty label (1–255 chars)")
    return value


# Webhook endpoint description — matches WebhookEndpoint.description String(255).
WebhookDescriptionValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_webhook_description_value),
]


class WebhookCreate(BaseModel):
    """Outbound webhook endpoint create."""

    # omit not allowed; blank/non-http(s)/non-localhost http → 422 (was free str; late **400**)
    url: WebhookUrlValue
    # Closed event catalog; blank/unknown item → 422; empty list → 422
    events: list[WebhookEventValue] = Field(min_length=1)
    secret: str | None = None
    # omit/`null` → no description; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently None / garbage could persist).
    description: WebhookDescriptionValue | None = None
    is_active: bool = True


class WebhookUpdate(BaseModel):
    """Outbound webhook endpoint patch — omit = no change."""

    # omit = no change; blank/non-http(s) → 422 (was free str min_length=1; late **400**)
    url: WebhookUrlValue | None = None
    events: list[WebhookEventValue] | None = Field(default=None, min_length=1)
    # omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently cleared / garbage could persist).
    description: WebhookDescriptionValue | None = None
    is_active: bool | None = None
    rotate_secret: bool = False


class ExchangeRateUpsert(BaseModel):
    """PUT /credit/exchange-rates/{currency_code} — typed FX upsert (BR-2.6).

    Unknown keys → **422** (`extra=forbid`). `currency_code` ∈ 3-letter ISO
    (strip/upper); blank/invalid → **422** (was late service **400**).
    """

    model_config = ConfigDict(extra="forbid")

    currency_code: CurrencyCodeValue
    rate_to_base: float = Field(gt=0)


class ExchangeRateRefresh(BaseModel):
    """POST /credit/exchange-rates/refresh — optional currency watch list (BR-2.6).

    Unknown keys → **422**. Each `currencies[]` item same ISO honesty as upsert.
    """

    model_config = ConfigDict(extra="forbid")

    currencies: list[CurrencyCodeValue] | None = None


class FxAutoRefreshUpdate(BaseModel):
    fx_auto_refresh: bool


class BankConnectionCreate(BaseModel):
    account_id: str
    # BR-10.3 — schema Literal; omit defaults to mock; blank/invalid → 422
    provider: Literal["mock", "http_json"] = "mock"
    # omit/`null` OK; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist)
    display_name: BankConnectionDisplayNameValue | None = None
    external_account_id: str | None = None
    # omit/null OK (mock); blank/non-http(s)/plain-http remote → 422 (was free str; garbage could persist)
    feed_url: WebhookUrlValue | None = None
    access_token: str | None = None
    auto_sync: bool = True
    auto_match_after_sync: bool = True
    sync_lookback_days: int = Field(default=30, ge=1, le=365)


class BankConnectionUpdate(BaseModel):
    # BR-10.3 — omit = no change; blank/invalid → 422 (no silent mock)
    provider: Literal["mock", "http_json"] | None = None
    # omit/`null` = no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist)
    display_name: BankConnectionDisplayNameValue | None = None
    external_account_id: str | None = None
    # omit/null = no change; blank/non-http(s)/plain-http remote → 422 (was free str; garbage could persist)
    feed_url: WebhookUrlValue | None = None
    access_token: str | None = None
    clear_credentials: bool | None = None
    auto_sync: bool | None = None
    auto_match_after_sync: bool | None = None
    sync_lookback_days: int | None = Field(default=None, ge=1, le=365)
    is_active: bool | None = None


class BankAutoClearBody(BaseModel):
    """One-shot bank↔book auto-clear confidence floor (BR-10.3 reconcile)."""

    # omit → high; blank/invalid → 422 (was free dict; ""/garbage silently coerced to high)
    min_confidence: Annotated[
        Literal["high", "medium", "low"],
        BeforeValidator(coerce_package_code_value),
    ] = "high"
    date_window_days: int = Field(default=7, ge=1, le=90)


class BankStatementLineCreate(BaseModel):
    """Nested line on `BankStatementCreateBody` (BR-10.3).

    Unknown keys → **422**. Zero / missing amount → **422** (was late service **400**).
    Optional `txn_date` ∈ `IsoDateQueryValue`; omit → service default; blank/invalid → **422**
    (blank was silent default; invalid was uncaught **500** via `_parse_dt`).
    Optional `description` ∈ `BankStatementLineDescriptionValue`; omit/`null` → no
    description; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently
    dropped via strip-to-None / garbage could persist).
    Optional `external_ref` ∈ `BankStatementLineExternalRefValue`; omit/`null` → no
    ref; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently dropped
    via strip-to-None / garbage could persist; max 120 matches column).
    """

    model_config = ConfigDict(extra="forbid")

    amount: float
    txn_date: IsoDateQueryValue | None = None
    # omit/`null` → no description; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped via strip-to-None / garbage could persist).
    description: BankStatementLineDescriptionValue | None = None
    # omit/`null` → no ref; blank/`!!!`/`http://…` → **422** (was free `str`; blank
    # silently dropped via strip-to-None / garbage could persist; max 120).
    external_ref: BankStatementLineExternalRefValue | None = None

    @field_validator("amount")
    @classmethod
    def _nonzero_amount(cls, value: float) -> float:
        if abs(float(value)) < 1e-9:
            raise ValueError("Statement line amount cannot be zero")
        return float(value)


class BankStatementCreateBody(BaseModel):
    """POST /accounting/bank-statements (BR-10.3).

    Unknown keys → **422** (`extra=forbid`). Blank/omit `account_id` → **422**
    (was free `dict` that turned omit/`""` into a late **404**). Zero line amounts
    → **422**. Optional `statement_date` ∈ `IsoDateQueryValue`; omit → today;
    blank/invalid → **422** (blank was silent today; invalid was uncaught **500**).
    Optional `notes` ∈ `BankStatementNotesValue`; omit/`null` → no notes; blank/
    `!!!`/`http://…` → **422** (was free `str`; blank silently dropped via
    strip-to-None / garbage could persist). Service `create_statement` remains
    defense-in-depth.
    """

    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1)
    statement_date: IsoDateQueryValue | None = None
    opening_balance: float = 0
    closing_balance: float = 0
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped via strip-to-None / garbage could persist).
    notes: BankStatementNotesValue | None = None
    lines: list[BankStatementLineCreate] = Field(default_factory=list)

    @field_validator("account_id", mode="before")
    @classmethod
    def _strip_account_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class BankStatementMatchBody(BaseModel):
    """POST .../bank-statements/{id}/lines/{line_id}/match (BR-10.3).

    Unknown keys → **422** (`extra=forbid`). Blank/omit `journal_line_id` → **422**
    (was free `dict` that coerced omit/`""` into a late **404**).
    """

    model_config = ConfigDict(extra="forbid")

    journal_line_id: str = Field(min_length=1)

    @field_validator("journal_line_id", mode="before")
    @classmethod
    def _strip_journal_line_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class BankClearGroupBody(BaseModel):
    """POST .../bank-statements/{id}/clear-group (BR-10.3).

    Unknown keys → **422**. Empty either id list (after stripping blanks) → **422**
    (was free `dict` with late **400**). Optional `notes` ∈ `BankClearGroupNotesValue`;
    omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    blank/garbage could persist on clearing group).
    """

    model_config = ConfigDict(extra="forbid")

    statement_line_ids: list[str] = Field(min_length=1)
    journal_line_ids: list[str] = Field(min_length=1)
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on clearing group).
    notes: BankClearGroupNotesValue | None = None

    @field_validator("statement_line_ids", "journal_line_ids", mode="before")
    @classmethod
    def _clean_id_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        cleaned: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                cleaned.append(text)
        return cleaned


class SupplierPaymentCreate(BaseModel):
    supplier_id: str
    amount: float = Field(gt=0)
    purchase_order_id: str | None = None
    purchase_invoice_id: str | None = None
    # BR-11.2 — same settlement Literal; omit → bank_transfer; blank/invalid → 422
    payment_method: SettlementPaymentMethod = "bank_transfer"
    # omit/`null` → no reference; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on SupplierPayment.reference).
    reference: PaymentReferenceValue | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on SupplierPayment.notes Text).
    notes: PaymentNotesValue | None = None
    # omit/`null` → service falls back to reference/payment_number; blank/`!!!`/
    # `http://…` → **422** (was free `str`; blank/garbage could persist on cheque).
    cheque_number: ChequeNumberValue | None = None
    # omit/`null` → no bank on cheque; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank/garbage could persist on cheque payment bank_name).
    bank_name: BankNameValue | None = None
    # omit/`null` → no cheque date; blank/`not-a-date`/`01/02/2024` → **422**
    # (was free `datetime`; OpenAPI date-time; padded dates rejected; Credit UI
    # never set → always null). API parses via reports.parse_date.
    cheque_date: IsoDateQueryValue | None = None
    apply_early_discount: bool | None = None
    liquid_account_id: str | None = None
    # omit/null → invoice/base via resolve_rate; blank/non-ISO → 422 (was free str; blank silently base)
    currency: CurrencyCodeValue | None = None
    exchange_rate: float | None = Field(default=None, gt=0)


class CreditLimitUpdate(BaseModel):
    credit_limit: float = Field(ge=0)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)


class NotificationChannelPrefs(BaseModel):
    """Per-category dashboard/email/sms toggles — unknown channels → 422."""

    model_config = ConfigDict(extra="forbid")

    dashboard: bool | None = None
    email: bool | None = None
    sms: bool | None = None


class NotificationPreferencesMap(BaseModel):
    """Preference categories aligned with app.notifications.DEFAULT_PREFERENCES."""

    model_config = ConfigDict(extra="forbid")

    low_stock: NotificationChannelPrefs | None = None
    expense_approval: NotificationChannelPrefs | None = None
    shift_variance: NotificationChannelPrefs | None = None
    credit_limit: NotificationChannelPrefs | None = None
    purchase_received: NotificationChannelPrefs | None = None
    payment_due: NotificationChannelPrefs | None = None
    quotation_expiry: NotificationChannelPrefs | None = None
    recurring_expense_due: NotificationChannelPrefs | None = None
    new_order: NotificationChannelPrefs | None = None
    transfer: NotificationChannelPrefs | None = None
    billing: NotificationChannelPrefs | None = None
    security: NotificationChannelPrefs | None = None
    system: NotificationChannelPrefs | None = None


class NotificationPreferencesUpdate(BaseModel):
    """PATCH /notifications/settings — typed preference map (BR-4.4 / BR-15.2).

    Unknown category keys or channel keys → **422** (no silent drop via merge).
    """

    preferences: NotificationPreferencesMap


class JournalLineCreate(BaseModel):
    """Nested line on `JournalCreate` (BR-10.2).

    Optional `description` ∈ `JournalLineDescriptionValue`; omit/`null` → no line
    narrative; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage
    could persist on `JournalEntryLine.description`).
    """

    account_id: str | None = None
    account_code: str | None = None
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)
    # omit/`null` → no line narrative; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank/garbage could persist on JournalEntryLine.description).
    description: JournalLineDescriptionValue | None = None


def validate_journal_description_value(value: str) -> str:
    """AfterValidator: journal narrative; blank/URL/short/garbage → 422 (2–500)."""
    if not value:
        raise ValueError("journal description must be a non-empty narrative (2–500 chars)")
    if len(value) < 2 or len(value) > 500:
        raise ValueError("journal description must be a non-empty narrative (2–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("journal description must be a non-empty narrative (2–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("journal description must be a non-empty narrative (2–500 chars)")
    return value


# Manual journal header narrative (BR-10.2) — Text column; keep ≤500 at API boundary.
JournalDescriptionValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_journal_description_value),
]


def validate_journal_line_description_value(value: str) -> str:
    """AfterValidator: journal line narrative; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("journal line description must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("journal line description must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("journal line description must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("journal line description must be a non-empty narrative (1–500 chars)")
    return value


# Manual journal line narrative — JournalEntryLine.description Text; ≤500 at API.
JournalLineDescriptionValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_journal_line_description_value),
]


def validate_journal_reference_value(value: str) -> str:
    """AfterValidator: journal reference; blank/URL/garbage → 422 (1–100)."""
    if not value:
        raise ValueError("journal reference must be a non-empty label (1–100 chars)")
    if len(value) > 100:
        raise ValueError("journal reference must be a non-empty label (1–100 chars)")
    if "://" in value or "@" in value:
        raise ValueError("journal reference must be a non-empty label (1–100 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("journal reference must be a non-empty label (1–100 chars)")
    return value


# Manual journal reference — JournalEntry.reference String(100); omit → no reference.
JournalReferenceValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_journal_reference_value),
]


def validate_bank_statement_line_description_value(value: str) -> str:
    """AfterValidator: bank statement line description; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError(
            "bank statement line description must be a non-empty narrative (1–500 chars)"
        )
    if len(value) > 500:
        raise ValueError(
            "bank statement line description must be a non-empty narrative (1–500 chars)"
        )
    if "://" in value or "@" in value:
        raise ValueError(
            "bank statement line description must be a non-empty narrative (1–500 chars)"
        )
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError(
            "bank statement line description must be a non-empty narrative (1–500 chars)"
        )
    return value


# Bank statement line narrative — keep ≤500 at API boundary.
BankStatementLineDescriptionValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_bank_statement_line_description_value),
]


def validate_bank_statement_line_external_ref_value(value: str) -> str:
    """AfterValidator: bank statement line external_ref; blank/URL/garbage → 422 (1–120)."""
    if not value:
        raise ValueError(
            "bank statement line external_ref must be a non-empty label (1–120 chars)"
        )
    if len(value) > 120:
        raise ValueError(
            "bank statement line external_ref must be a non-empty label (1–120 chars)"
        )
    if "://" in value or "@" in value:
        raise ValueError(
            "bank statement line external_ref must be a non-empty label (1–120 chars)"
        )
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError(
            "bank statement line external_ref must be a non-empty label (1–120 chars)"
        )
    return value


# Bank statement line external_ref — matches BankStatementLine.external_ref String(120).
BankStatementLineExternalRefValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_bank_statement_line_external_ref_value),
]


def validate_bank_statement_notes_value(value: str) -> str:
    """AfterValidator: bank statement header notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("bank statement notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("bank statement notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("bank statement notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("bank statement notes must be a non-empty narrative (1–500 chars)")
    return value


# Bank statement header notes — keep ≤500 at API boundary.
BankStatementNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_bank_statement_notes_value),
]


def validate_bank_clear_group_notes_value(value: str) -> str:
    """AfterValidator: bank clear-group notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("bank clear-group notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("bank clear-group notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("bank clear-group notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("bank clear-group notes must be a non-empty narrative (1–500 chars)")
    return value


# Bank clearing-group notes — keep ≤500 at API boundary.
BankClearGroupNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_bank_clear_group_notes_value),
]


def validate_expense_description_value(value: str) -> str:
    """AfterValidator: expense narrative; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("expense description must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("expense description must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("expense description must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("expense description must be a non-empty narrative (1–500 chars)")
    return value


# Expense / recurring narrative (BR-9.2 / BR-9.5) — Text column; keep ≤500 at API.
ExpenseDescriptionValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_expense_description_value),
]


def validate_expense_approve_comment_value(value: str) -> str:
    """AfterValidator: expense approve comment; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("expense approve comment must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("expense approve comment must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("expense approve comment must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("expense approve comment must be a non-empty narrative (1–500 chars)")
    return value


# Expense approve comment — Expense.approval_comment Text; keep ≤500 at API boundary.
ExpenseApproveCommentValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_expense_approve_comment_value),
]


def validate_recurring_skip_reason_value(value: str) -> str:
    """AfterValidator: recurring skip-next reason; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("recurring skip reason must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("recurring skip reason must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("recurring skip reason must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("recurring skip reason must be a non-empty narrative (1–500 chars)")
    return value


# Recurring skip-next reason — audit `recurring_expense_skipped.details.reason` (BR-9.5).
RecurringSkipReasonValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_recurring_skip_reason_value),
]


def validate_expense_reject_reason_value(value: str) -> str:
    """AfterValidator: expense reject reason; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("expense reject reason must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("expense reject reason must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("expense reject reason must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("expense reject reason must be a non-empty narrative (1–500 chars)")
    return value


# Expense reject reason — Expense.rejection_reason column (BR-9.3).
ExpenseRejectReasonValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_expense_reject_reason_value),
]


def validate_expense_payee_value(value: str) -> str:
    """AfterValidator: expense payee label; blank/URL/garbage → 422 (1–150)."""
    if not value:
        raise ValueError("expense payee must be a non-empty label (1–150 chars)")
    if len(value) > 150:
        raise ValueError("expense payee must be a non-empty label (1–150 chars)")
    if "://" in value or "@" in value:
        raise ValueError("expense payee must be a non-empty label (1–150 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("expense payee must be a non-empty label (1–150 chars)")
    return value


# Expense / recurring payee — matches Expense.payee / RecurringExpense.payee String(150).
ExpensePayeeValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_expense_payee_value),
]


def validate_expense_reference_value(value: str) -> str:
    """AfterValidator: expense vendor/doc reference; blank/URL/garbage → 422 (1–100)."""
    if not value:
        raise ValueError("expense reference must be a non-empty label (1–100 chars)")
    if len(value) > 100:
        raise ValueError("expense reference must be a non-empty label (1–100 chars)")
    if "://" in value or "@" in value:
        raise ValueError("expense reference must be a non-empty label (1–100 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("expense reference must be a non-empty label (1–100 chars)")
    return value


# Expense reference — matches Expense.reference String(100); omit → auto EXP-YYYY-NNNN.
ExpenseReferenceValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_expense_reference_value),
]


def validate_payment_reference_value(value: str) -> str:
    """AfterValidator: AR/AP payment reference; blank/URL/garbage → 422 (1–100)."""
    if not value:
        raise ValueError("payment reference must be a non-empty label (1–100 chars)")
    if len(value) > 100:
        raise ValueError("payment reference must be a non-empty label (1–100 chars)")
    if "://" in value or "@" in value:
        raise ValueError("payment reference must be a non-empty label (1–100 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("payment reference must be a non-empty label (1–100 chars)")
    return value


# Customer/supplier payment reference — String(100); omit → no reference.
PaymentReferenceValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_payment_reference_value),
]


def validate_payment_notes_value(value: str) -> str:
    """AfterValidator: AR/AP payment notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("payment notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("payment notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("payment notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("payment notes must be a non-empty narrative (1–500 chars)")
    return value


# Customer/supplier payment notes — Text column; keep ≤500 at API boundary.
PaymentNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_payment_notes_value),
]


def validate_cash_transfer_reference_value(value: str) -> str:
    """AfterValidator: cash transfer reference; blank/URL/garbage → 422 (1–80)."""
    if not value:
        raise ValueError("cash transfer reference must be a non-empty label (1–80 chars)")
    if len(value) > 80:
        raise ValueError("cash transfer reference must be a non-empty label (1–80 chars)")
    if "://" in value or "@" in value:
        raise ValueError("cash transfer reference must be a non-empty label (1–80 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("cash transfer reference must be a non-empty label (1–80 chars)")
    return value


# Cash transfer reference — matches CashTransfer.reference String(80); omit → auto XFER.
CashTransferReferenceValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_cash_transfer_reference_value),
]


def validate_opening_balance_reference_value(value: str) -> str:
    """AfterValidator: COA opening balance reference; blank/URL/garbage → 422 (1–100)."""
    if not value:
        raise ValueError("opening balance reference must be a non-empty label (1–100 chars)")
    if len(value) > 100:
        raise ValueError("opening balance reference must be a non-empty label (1–100 chars)")
    if "://" in value or "@" in value:
        raise ValueError("opening balance reference must be a non-empty label (1–100 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("opening balance reference must be a non-empty label (1–100 chars)")
    return value


# COA opening reference — JournalEntry.reference; omit → auto COA-OPEN-YYYYMMDD.
OpeningBalanceReferenceValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_opening_balance_reference_value),
]


def validate_opening_balance_notes_value(value: str) -> str:
    """AfterValidator: COA opening balance notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("opening balance notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("opening balance notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("opening balance notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("opening balance notes must be a non-empty narrative (1–500 chars)")
    return value


# COA opening notes — JournalEntry.description; omit → default "COA opening balances …".
OpeningBalanceNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_opening_balance_notes_value),
]


def validate_stock_count_notes_value(value: str) -> str:
    """AfterValidator: stock count notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("stock count notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("stock count notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("stock count notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("stock count notes must be a non-empty narrative (1–500 chars)")
    return value


# Stock count notes — StockCount.notes Text; keep ≤500 at API boundary.
StockCountNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_stock_count_notes_value),
]


def validate_sales_return_notes_value(value: str) -> str:
    """AfterValidator: sales return notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("sales return notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("sales return notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("sales return notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("sales return notes must be a non-empty narrative (1–500 chars)")
    return value


# Sales return header notes — SalesReturn.notes Text; keep ≤500 at API boundary.
SalesReturnNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_sales_return_notes_value),
]


def validate_sales_document_notes_value(value: str) -> str:
    """AfterValidator: sales invoice/quotation/order notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("sales document notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("sales document notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("sales document notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("sales document notes must be a non-empty narrative (1–500 chars)")
    return value


# Shared QT/SO/SI header notes — Text columns; keep ≤500 at API boundary.
SalesDocumentNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_sales_document_notes_value),
]


def validate_purchase_return_notes_value(value: str) -> str:
    """AfterValidator: purchase return notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("purchase return notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("purchase return notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("purchase return notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("purchase return notes must be a non-empty narrative (1–500 chars)")
    return value


# Purchase return header notes — PurchaseReturn.notes Text; keep ≤500 at API boundary.
PurchaseReturnNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_purchase_return_notes_value),
]


def validate_purchase_order_notes_value(value: str) -> str:
    """AfterValidator: purchase order notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("purchase order notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("purchase order notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("purchase order notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("purchase order notes must be a non-empty narrative (1–500 chars)")
    return value


# Purchase order notes — PurchaseOrder.notes Text; keep ≤500 at API boundary.
PurchaseOrderNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_purchase_order_notes_value),
]


def validate_purchase_request_notes_value(value: str) -> str:
    """AfterValidator: purchase request notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("purchase request notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("purchase request notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("purchase request notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("purchase request notes must be a non-empty narrative (1–500 chars)")
    return value


# Purchase request notes — PurchaseRequest.notes column; keep ≤500 at API boundary.
PurchaseRequestNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_purchase_request_notes_value),
]


def validate_ai_prediction_risk_reason_value(value: str) -> str:
    """AfterValidator: AI prediction risk_reason; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("AI prediction risk_reason must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("AI prediction risk_reason must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("AI prediction risk_reason must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("AI prediction risk_reason must be a non-empty narrative (1–500 chars)")
    return value


# AI low-stock prediction line risk_reason — embeds into draft PR line notes (BR-21.4).
AiPredictionRiskReasonValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_ai_prediction_risk_reason_value),
]


def validate_purchase_invoice_notes_value(value: str) -> str:
    """AfterValidator: purchase invoice notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("purchase invoice notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("purchase invoice notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("purchase invoice notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("purchase invoice notes must be a non-empty narrative (1–500 chars)")
    return value


# Purchase invoice notes — PurchaseInvoice.notes Text; keep ≤500 at API boundary.
PurchaseInvoiceNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_purchase_invoice_notes_value),
]


def validate_grn_notes_value(value: str) -> str:
    """AfterValidator: GRN notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("GRN notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("GRN notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("GRN notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("GRN notes must be a non-empty narrative (1–500 chars)")
    return value


# Goods receipt notes — GoodsReceipt.notes Text; keep ≤500 at API boundary.
GrnNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_grn_notes_value),
]


def validate_stock_count_item_notes_value(value: str) -> str:
    """AfterValidator: stock count line notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("stock count item notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("stock count item notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("stock count item notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("stock count item notes must be a non-empty narrative (1–500 chars)")
    return value


# Stock count line notes — StockCountItem.notes Text; keep ≤500 at API boundary.
StockCountItemNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_stock_count_item_notes_value),
]


def validate_cash_transfer_notes_value(value: str) -> str:
    """AfterValidator: cash transfer notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("cash transfer notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("cash transfer notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("cash transfer notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("cash transfer notes must be a non-empty narrative (1–500 chars)")
    return value


# Cash transfer notes — CashTransfer.notes Text; keep ≤500 at API boundary.
CashTransferNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_cash_transfer_notes_value),
]


def validate_opening_stock_reference_value(value: str) -> str:
    """AfterValidator: opening-stock reference; blank/URL/garbage → 422 (1–100)."""
    if not value:
        raise ValueError("opening stock reference must be a non-empty label (1–100 chars)")
    if len(value) > 100:
        raise ValueError("opening stock reference must be a non-empty label (1–100 chars)")
    if "://" in value or "@" in value:
        raise ValueError("opening stock reference must be a non-empty label (1–100 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("opening stock reference must be a non-empty label (1–100 chars)")
    return value


# Opening stock reference — journal/audit String(100); omit → auto OS-YYYY-NNNN.
OpeningStockReferenceValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_opening_stock_reference_value),
]


def validate_opening_stock_notes_value(value: str) -> str:
    """AfterValidator: opening-stock notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("opening stock notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("opening stock notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("opening stock notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("opening stock notes must be a non-empty narrative (1–500 chars)")
    return value


# Opening stock header notes — merged into StockMovement.notes Text; ≤500 at API.
OpeningStockNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_opening_stock_notes_value),
]


def validate_backup_notes_value(value: str) -> str:
    """AfterValidator: backup job notes; blank/URL/garbage → 422 (1–500)."""
    if not value:
        raise ValueError("backup notes must be a non-empty narrative (1–500 chars)")
    if len(value) > 500:
        raise ValueError("backup notes must be a non-empty narrative (1–500 chars)")
    if "://" in value or "@" in value:
        raise ValueError("backup notes must be a non-empty narrative (1–500 chars)")
    if not re.search(r"[A-Za-z0-9]", value):
        raise ValueError("backup notes must be a non-empty narrative (1–500 chars)")
    return value


# Backup job notes — BackupJob.notes Text; keep ≤500 at API boundary.
BackupNotesValue = Annotated[
    str,
    BeforeValidator(coerce_bank_name_value),
    AfterValidator(validate_backup_notes_value),
]


class JournalCreate(BaseModel):
    """Manual journal create — description + optional entry_date (BR-10.2).

    `description` ∈ JournalDescriptionValue (strip; 2–500; ≥1 letter/digit; no
    `://`/`@`); blank/`!!!`/`http://…` → **422** (was free `str`; empty/garbage
    could persist on the ledger). Optional `reference` ∈ JournalReferenceValue
    (strip; 1–100; ≥1 letter/digit; no `://`/`@`); omit/`null` → no reference;
    blank/`!!!`/`http://…` → **422** (was free `str`; blank silently dropped /
    garbage could persist on journal `reference`). Optional `entry_date` ∈
    IsoDateQueryValue; omit/`null` → now; blank/invalid → **422**.
    """

    description: JournalDescriptionValue
    # omit/`null` → no reference; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank silently dropped / garbage could persist on JournalEntry.reference).
    reference: JournalReferenceValue | None = None
    # IsoDateQueryValue as expense_date / SO delivery_date / subscription start_at.
    entry_date: IsoDateQueryValue | None = None
    lines: list[JournalLineCreate] = Field(min_length=2)


class JournalUnpost(BaseModel):
    """Manual journal unpost — typed reason required (BR-10.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class ChequeLifecycleReason(BaseModel):
    """Cheque bounce / cancel — typed reason required (BR-10.4 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class PeriodCloseBody(BaseModel):
    """Close books through an inclusive calendar date (BR-10.2).

    `through_date` ∈ IsoDateQueryValue (required); blank/invalid → **422**.
    """

    # IsoDateQueryValue as JournalCreate.entry_date / expense_date.
    through_date: IsoDateQueryValue
    reason: str = Field(min_length=1, max_length=500)


class PeriodReopenBody(BaseModel):
    """Reopen: set an earlier closed-through date, or null to clear — reason required (BR-10.2 honesty).

    Optional `through_date` ∈ IsoDateQueryValue; omit/`null` → clear; blank/invalid → **422**.
    """

    through_date: IsoDateQueryValue | None = None
    reason: str = Field(min_length=1, max_length=500)


class PosSessionOpen(BaseModel):
    store_id: str | None = None
    opening_cash: float = Field(default=0, ge=0)


class PosSessionClose(BaseModel):
    actual_cash: float = Field(ge=0)
    closing_cash: float | None = None
    # omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`;
    # blank/garbage could persist on PosSession.notes Text).
    notes: PosSessionCloseNotesValue | None = None


class PosPaymentLine(BaseModel):
    """One tender toward a POS sale total (supports split payments).

    Optional `reference` ∈ PaymentReferenceValue; omit/`null` → no tender
    reference; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage
    could persist on POS payment `reference`).
    """

    # BR-8.1 — schema Literal (+ wallet aliases via BeforeValidator); blank/invalid → 422
    payment_method: PosTenderMethod = "cash"
    amount: float = Field(gt=0)
    # omit/`null` → no tender reference; blank/`!!!`/`http://…` → **422** (was free
    # `str`; blank/garbage could persist on POS payment reference).
    reference: PaymentReferenceValue | None = None
    liquid_account_id: str | None = None


class PosSaleCreate(BaseModel):
    session_id: str | None = None
    party_id: str | None = None
    # omit/`null` → walk-in (no name); blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist)
    customer_name: PosCustomerNameValue | None = None
    subtotal: float = 0
    tax: float = 0
    total: float = 0
    discount_amount: float = Field(default=0, ge=0)
    # BR-8.1 — only completed POS create; omit → completed; blank/invalid → 422
    # (was free str; garbage persisted on transactions.status)
    status: Literal["completed"] = "completed"
    # BR-8.1 — omit → cash; blank/invalid → 422; split allowed when payments[] present
    payment_method: PosSalePaymentMethod = "cash"
    payments: list[PosPaymentLine] | None = None
    payload: dict = Field(default_factory=dict)
    items: list[LineItem] = Field(min_length=1)
    override_credit_limit: bool = False
    override_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_override_reason_when_flagged(self):
        return _require_credit_override_reason(self)
