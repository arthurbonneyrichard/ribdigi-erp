from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, model_validator

from app.pos import coerce_payment_method_value
from app.tenants import (
    coerce_date_format_value,
    coerce_decimal_separator_value,
    coerce_industry_value,
    coerce_tax_filing_period_value,
    coerce_thousand_separator_value,
    coerce_time_format_value,
)
from app.expenses import coerce_expense_payment_method_value
from app.print_branding import coerce_invoice_template_value, coerce_receipt_paper_value

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
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    clear_password: bool = False
    from_email: str | None = None
    from_name: str | None = None
    use_tls: bool | None = None
    use_ssl: bool | None = None


class SmsTestRequest(BaseModel):
    to: str | None = None


class SmsSettingsUpdate(BaseModel):
    account_sid: str | None = None
    auth_token: str | None = None
    clear_auth_token: bool = False
    from_number: str | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TenantCreate(BaseModel):
    company_name: str
    slug: str
    # BR-1.2 — schema Literal (+ case coerce via BeforeValidator); omit → retail;
    # blank/invalid → 422 (no silent retail from garbage).
    industry: IndustryValue = "retail"
    currency: str = "GHS"
    admin_email: EmailStr
    admin_password: str


class TenantProfileUpdate(BaseModel):
    company_name: str | None = None
    # omit = no change; blank/invalid → 422 (same IndustryValue Literal)
    industry: IndustryValue | None = None
    currency: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    address: str | None = None
    legal_name: str | None = None
    registration_number: str | None = None
    contact_person: str | None = None
    billing_address: str | None = None
    shipping_address: str | None = None
    timezone: str | None = None
    fiscal_year_start: str | None = None
    tax_jurisdiction: str | None = None
    tax_registration_number: str | None = None
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
    start_at: datetime | None = None
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
    full_name: str
    password: str
    role: str = "cashier"
    phone: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    # BR-3.3 — omit = role default; blank/invalid → 422 (no silent all from "")
    record_scope: RecordScopeValue | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
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
    """Create a platform staff user on the software-owner workspace."""

    email: str = Field(min_length=3)
    full_name: str = Field(min_length=1)
    password: str = Field(min_length=1)
    # Same Literal as grant; omit → platform_support; blank/invalid → 422
    # (was free dict; API `role or "platform_support"` silently coerced "")
    role: PlatformRoleValue = "platform_support"
    phone: str | None = None


class PlatformStaffUpdate(BaseModel):
    """Patch platform staff — omit = no change; blank role → 422."""

    full_name: str | None = Field(default=None, min_length=1)
    role: PlatformRoleValue | None = None
    phone: str | None = None
    is_active: bool | None = None


class PlatformRevokeAccess(BaseModel):
    """Revoke software-owner dashboard access; keep the account as an app user."""

    # Non-platform system roles Literal (+ strip/lower); omit → company_admin;
    # blank/invalid/platform → 422 (was free str; "" silently coerced to company_admin)
    fallback_role: AppFallbackRoleValue = "company_admin"


class AccountCreate(BaseModel):
    code: str
    name: str
    # BR-10.3 / COA — schema Literal; omit → asset; blank/invalid → 422
    account_type: Literal["asset", "liability", "equity", "income", "expense"] = "asset"
    # omit/null = non-liquid; blank/invalid → 422 (no silent None from "")
    liquid_kind: Literal["cash", "bank"] | None = None
    bank_name: str | None = None
    account_number: str | None = None
    bank_branch: str | None = None


class AccountUpdate(BaseModel):
    name: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    bank_branch: str | None = None
    is_active: bool | None = None


class OpeningBalanceLine(BaseModel):
    account_id: str | None = None
    account_code: str | None = None
    amount: float = Field(gt=0)


class OpeningBalanceCreate(BaseModel):
    lines: list[OpeningBalanceLine] = Field(min_length=1)
    reference: str | None = None
    notes: str | None = None


class CashTransferCreate(BaseModel):
    # BR-10.3 — schema Literal; omit defaults to transfer; blank/invalid → 422
    kind: Literal["transfer", "deposit", "withdrawal"] = "transfer"
    from_account_id: str | None = None
    to_account_id: str | None = None
    amount: float = Field(gt=0)
    reference: str | None = None
    notes: str | None = None


class BranchCreate(BaseModel):
    code: str
    name: str
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    manager_id: str | None = None


class BranchUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    manager_id: str | None = None
    clear_manager: bool = False
    is_active: bool | None = None


class DepartmentCreate(BaseModel):
    code: str
    name: str
    branch_id: str | None = None
    head_user_id: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = None
    branch_id: str | None = None
    clear_branch: bool = False
    head_user_id: str | None = None
    clear_head: bool = False
    is_active: bool | None = None


class CustomRoleCreate(BaseModel):
    key: str
    label: str
    permissions: dict[str, list[str]] | None = None
    # Clone-from system role; omit/null OK when permissions set; blank/unknown/super_admin → 422
    base_role: CustomRoleBaseRoleValue | None = None
    # BR-3.3 — omit = base_role/own default; blank/invalid → 422
    record_scope: RecordScopeValue | None = None


class CustomRoleUpdate(BaseModel):
    label: str | None = None
    permissions: dict[str, list[str]] | None = None
    record_scope: RecordScopeValue | None = None
    is_active: bool | None = None


class ProductCreate(BaseModel):
    name: str
    sku: str | None = None  # omit/blank → auto-allocate unique SKU (BR-5.1)
    barcode: str | None = None
    description: str | None = None
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
    name: str | None = None
    sku: str | None = None
    barcode: str | None = None
    description: str | None = None
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
    notes: str | None = None
    product_ids: list[str] | None = None


class StockCountItemUpdate(BaseModel):
    product_id: str
    counted_qty: float
    notes: str | None = None


class StockCountItemsUpdate(BaseModel):
    items: list[StockCountItemUpdate]


class StockCountCancel(BaseModel):
    """Draft stock count cancel — typed reason required (BR-5.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class ProductCategoryCreate(BaseModel):
    code: str
    name: str
    parent_id: str | None = None
    tax_rate_id: str | None = None


class ProductCategoryUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    parent_id: str | None = None
    tax_rate_id: str | None = None
    is_active: bool | None = None


class BrandCreate(BaseModel):
    code: str
    name: str
    description: str | None = None


class BrandUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class UnitOfMeasureCreate(BaseModel):
    code: str
    name: str
    base_unit_id: str | None = None
    conversion_ratio: float | None = 1


class UnitOfMeasureUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    is_active: bool | None = None
    base_unit_id: str | None = None
    conversion_ratio: float | None = None
    clear_base: bool = False


class UnitConvertPreview(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    from_unit_id: str | None = None


class ProductVariantCreate(BaseModel):
    name: str
    sku: str | None = None  # omit/blank → auto-allocate unique SKU (BR-5.1)
    barcode: str | None = None
    size: str | None = None
    color: str | None = None
    flavor: str | None = None
    dosage: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None


class ProductVariantUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    barcode: str | None = None
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
    name: str
    code: str | None = None
    # BR-6.1 / BR-7.1 — OpenAPI union Literal; kind-specific allow-list still enforced
    # in _normalize_party_profile. Omit → registered; blank/invalid → 422.
    profile_type: Literal[
        "walk_in", "registered", "trade", "manufacturer", "service", "other"
    ] = "registered"
    category: str | None = None
    status: Literal["active", "inactive"] = "active"
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    credit_limit: float = 0
    payment_terms_days: int = Field(default=30, ge=0, le=3650)
    customer_group_id: str | None = None


class PartyUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    # omit = no change; blank/invalid → 422 (no silent registered)
    profile_type: (
        Literal["walk_in", "registered", "trade", "manufacturer", "service", "other"] | None
    ) = None
    category: str | None = None
    status: Literal["active", "inactive"] | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    credit_limit: float | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    customer_group_id: str | None = None


class PartyContactCreate(BaseModel):
    name: str
    phone: str | None = None
    email: EmailStr | None = None
    designation: str | None = None
    is_primary: bool = False


class PartyContactUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    designation: str | None = None
    is_primary: bool | None = None


class CustomerGroupCreate(BaseModel):
    name: str
    code: str | None = None
    discount_percent: float = 0


class CustomerGroupUpdate(BaseModel):
    name: str | None = None
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
    notes: str | None = None
    warehouse_id: str | None = None


class StockMove(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None  # entered UoM; converted to product.unit_id for stock
    notes: str | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_id: str | None = None
    batch_number: str | None = None
    manufacturing_date: datetime | None = None
    expiry_date: datetime | None = None
    # Optional on stock-in; stock-out uses StockOut with required Literal
    reference_type: str | None = None
    reference_id: str | None = None


class StockOut(BaseModel):
    """Manual stock-out (BR-5.2) — coded reference_type required at schema."""

    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None
    notes: str | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_id: str | None = None
    # OpenAPI Literal → omit/blank/invalid → 422
    reference_type: Literal["sale", "transfer", "adjustment", "damage", "internal", "other"]
    reference_id: str | None = None


class OpeningStockLine(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_id: str | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_number: str | None = None
    manufacturing_date: datetime | None = None
    expiry_date: datetime | None = None
    unit_cost: float | None = Field(default=None, ge=0)  # defaults to product.cost_price
    notes: str | None = None


class OpeningStockCreate(BaseModel):
    lines: list[OpeningStockLine] = Field(min_length=1)
    post_journal: bool = True
    reference: str | None = None
    notes: str | None = None


class ExpenseCreate(BaseModel):
    category: str | None = None
    category_id: str | None = None
    description: str = ""
    amount: float = Field(gt=0)
    # BR-9.2 — schema Literal (+ aliases via BeforeValidator); omit → cash;
    # blank/invalid → 422 (no silent cash from garbage).
    payment_method: ExpensePaymentMethod = "cash"
    liquid_account_id: str | None = None
    reference: str | None = None
    payee: str | None = None
    store_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    expense_date: datetime | None = None


class AiDocumentExpenseCreate(BaseModel):
    """Explicit Create draft expense from reviewed OCR fields (BR-21.8)."""

    amount: float = Field(gt=0)
    payee: str | None = None
    description: str | None = None
    reference: str | None = None
    category_id: str | None = None
    category: str | None = None
    payment_method: ExpensePaymentMethod = "cash"
    expense_date: str | datetime | None = None
    store_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None


class AiDocumentPurchaseInvoiceCreate(BaseModel):
    """Explicit Create draft purchase invoice from reviewed OCR + matched PO (BR-21.8)."""

    purchase_order_id: str
    supplier_id: str | None = None
    supplier_invoice_number: str | None = None
    notes: str | None = None
    is_reverse_charge: bool = False
    invoice_date: str | datetime | None = None


class ExpenseUpdate(BaseModel):
    category: str | None = None
    category_id: str | None = None
    description: str | None = None
    amount: float | None = Field(default=None, gt=0)
    # omit = no change; blank/invalid → 422
    payment_method: ExpensePaymentMethod | None = None
    reference: str | None = None
    payee: str | None = None
    expense_date: datetime | None = None
    store_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    clear_store: bool = False
    clear_branch: bool = False
    clear_department: bool = False


class ExpenseCategoryCreate(BaseModel):
    code: str
    name: str
    budget_amount: float = Field(default=0, ge=0)
    account_id: str | None = None


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
    account_id: str | None = None
    clear_account: bool = False


class ExpenseDecision(BaseModel):
    """Approve path — optional typed comment (BR-9.3)."""

    comment: str | None = None


class ExpenseReject(BaseModel):
    """Expense reject — typed reason required (BR-9.3 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class RecurringExpenseCreate(BaseModel):
    category: str | None = None
    category_id: str | None = None
    description: str = ""
    amount: float = Field(gt=0)
    # BR-9.5 — schema Literal; omit defaults to monthly; blank/invalid → 422
    frequency: Literal["daily", "weekly", "monthly", "yearly"] = "monthly"
    # BR-9.2 / BR-9.5 — same ExpensePaymentMethod Literal; omit → bank_transfer
    payment_method: ExpensePaymentMethod = "bank_transfer"
    payee: str | None = None
    branch_id: str | None = None
    department_id: str | None = None


class RecurringExpenseUpdate(BaseModel):
    is_active: bool | None = None
    amount: float | None = Field(default=None, gt=0)
    payee: str | None = None
    clear_payee: bool = False
    description: str | None = None
    payment_method: ExpensePaymentMethod | None = None
    frequency: Literal["daily", "weekly", "monthly", "yearly"] | None = None
    category_id: str | None = None
    category: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    clear_branch: bool = False
    clear_department: bool = False


class RecurringSkipNext(BaseModel):
    """Skip next recurring occurrence — typed reason required (BR-9.5 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class ApprovalLevelUpdate(BaseModel):
    min_amount: float = Field(gt=0)
    roles: list[str] = Field(min_length=1)
    label: str | None = None
    step: int | None = None


class ExpenseThresholdUpdate(BaseModel):
    expense_approval_threshold: float | None = Field(default=None, gt=0)
    expense_l2_threshold: float | None = Field(default=None, gt=0)
    levels: list[ApprovalLevelUpdate] | None = None
    expense_numbering: DocumentNumberingFields | None = None


class StoreCreate(BaseModel):
    name: str
    code: str
    address: str | None = None
    phone: str | None = None
    manager_id: str | None = None
    branch_id: str | None = None
    operating_hours: dict | None = None


class StoreUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    manager_id: str | None = None
    clear_manager: bool = False
    branch_id: str | None = None
    clear_branch: bool = False
    is_active: bool | None = None
    operating_hours: dict | None = None


class StoreDrawerSettingsUpdate(BaseModel):
    # BR-8.1 — schema Literal; omit = no change; blank/invalid → 422 (no silent none)
    drawer_mode: Literal["none", "mock", "network", "browser_bridge"] | None = None
    drawer_host: str | None = None
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
    name: str
    code: str
    store_id: str | None = None
    # BR-2.4 — schema Literal; omit defaults to retail; blank/invalid → 422
    warehouse_type: Literal["retail", "bulk", "cold_storage", "other"] = "retail"
    manager_id: str | None = None
    address: str | None = None
    capacity: float | None = Field(default=None, ge=0)


class WarehouseUpdate(BaseModel):
    name: str | None = None
    store_id: str | None = None
    clear_store: bool = False
    warehouse_type: Literal["retail", "bulk", "cold_storage", "other"] | None = None
    manager_id: str | None = None
    clear_manager: bool = False
    address: str | None = None
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
    notes: str | None = None
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


class TaxCreate(BaseModel):
    name: str
    rate: float = Field(ge=0)
    # BR-12.1 — schema Literal; omit defaults; blank/invalid → 422
    tax_type: Literal["vat", "gst", "sales_tax", "custom"] = "vat"
    pricing_mode: Literal["exclusive", "inclusive"] = "exclusive"
    components: list[dict] | None = None
    is_reverse_charge: bool = False
    is_default: bool = False
    is_active: bool = True


class TaxUpdate(BaseModel):
    name: str | None = None
    rate: float | None = Field(default=None, ge=0)
    # BR-12.1 — omit = no change; blank/invalid → 422
    tax_type: Literal["vat", "gst", "sales_tax", "custom"] | None = None
    pricing_mode: Literal["exclusive", "inclusive"] | None = None
    components: list[dict] | None = None
    is_reverse_charge: bool | None = None
    is_active: bool | None = None


class TaxCalculateRequest(BaseModel):
    amount: float = Field(gt=0)
    rate: float | None = None
    tax_rate_id: str | None = None
    # BR-12.1 — omit → exclusive at calc; blank/invalid → 422
    pricing_mode: Literal["exclusive", "inclusive"] | None = None
    components: list[dict] | None = None
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
    notes: str | None = None
    delivery_address: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class PurchaseOrderAmend(BaseModel):
    items: list[PurchaseOrderItemCreate] | None = None
    notes: str | None = None
    delivery_address: str | None = None
    due_date: datetime | None = None
    clear_due_date: bool = False
    # Required typed reason (BR-6.3 honesty); no silent amend
    reason: str = Field(min_length=1, max_length=500)
    notify_supplier: bool = False
    to: str | None = None


class PurchaseOrderCancel(BaseModel):
    """PO cancel — typed reason required (BR-6.3 honesty)."""

    reason: str = Field(min_length=1, max_length=500)

class PurchaseRequestItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    variant_id: str | None = None
    notes: str | None = None


class PurchaseRequestCreate(BaseModel):
    preferred_supplier_id: str | None = None
    warehouse_id: str | None = None
    required_date: datetime | None = None
    department: str | None = None
    notes: str | None = None
    items: list[PurchaseRequestItemCreate] = Field(min_length=1)


class PurchaseRequestReject(BaseModel):
    """Purchase request reject — typed reason required (BR-6.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class PurchaseRequestConvert(BaseModel):
    supplier_id: str | None = None


class PurchaseApprovalLevelUpdate(BaseModel):
    roles: list[str] = Field(min_length=1)
    label: str | None = None
    step: int | None = None


class PurchaseApprovalSettingsUpdate(BaseModel):
    levels: list[PurchaseApprovalLevelUpdate] = Field(min_length=1)


class LowStockSuggestionLine(BaseModel):
    product_id: str
    quantity: float | None = Field(default=None, gt=0)
    warehouse_id: str | None = None
    preferred_supplier_id: str | None = None
    notes: str | None = None


class LowStockSuggestionsCreate(BaseModel):
    lines: list[LowStockSuggestionLine] = Field(min_length=1)
    notes: str | None = None
    department: str | None = None
    include_open: bool = False


class GrnItemCreate(BaseModel):
    po_item_id: str
    received_qty: float = Field(gt=0)
    accepted_qty: float | None = None
    rejected_qty: float = Field(default=0, ge=0)
    rejection_reason: str | None = None
    # Optional lot for accepted stock (BR-6.4); required when product.tracks_batches
    batch_number: str | None = None
    manufacturing_date: datetime | None = None
    expiry_date: datetime | None = None

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
    notes: str | None = None
    items: list[GrnItemCreate] = Field(min_length=1)


class PurchaseReturnItemCreate(BaseModel):
    goods_receipt_item_id: str
    quantity: float = Field(gt=0)


class PurchaseReturnCreate(BaseModel):
    goods_receipt_id: str
    # Required coded reason (BR-6.6); OpenAPI Literal → omit/blank/invalid → 422
    reason: Literal["damaged", "wrong_item", "expiry", "quality", "other"]
    notes: str | None = None
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
    notes: str | None = None
    # Buyer self-assesses VAT (excluded from AP); posts Dr Input Tax / Cr Tax Payable on approve.
    is_reverse_charge: bool = False
    currency: str | None = None
    exchange_rate: float | None = Field(default=None, gt=0)
    items: list[PurchaseInvoiceItemCreate] | None = None


class PurchaseInvoiceUpdate(BaseModel):
    supplier_invoice_number: str | None = None
    notes: str | None = None
    invoice_date: datetime | None = None
    due_date: datetime | None = None


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
    notes: str | None = None
    store_id: str | None = None
    currency: str | None = None
    exchange_rate: float | None = Field(default=None, gt=0)
    is_reverse_charge: bool = False
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesQuotationCreate(BaseModel):
    customer_id: str
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = None
    valid_days: int = Field(default=14, ge=1, le=365)
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesQuotationReject(BaseModel):
    """Quotation reject — typed reason required (BR-7.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class SalesOrderCreate(BaseModel):
    customer_id: str
    quotation_id: str | None = None
    store_id: str | None = None
    delivery_date: datetime | None = None
    delivery_address: str | None = None
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = None
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesOrderConfirm(BaseModel):
    store_id: str | None = None
    delivery_date: datetime | None = None
    delivery_address: str | None = None


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
    notes: str | None = None
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
    reference: str | None = None
    notes: str | None = None
    cheque_number: str | None = None
    bank_name: str | None = None
    cheque_date: datetime | None = None
    apply_early_discount: bool | None = None
    liquid_account_id: str | None = None
    currency: str | None = None
    exchange_rate: float | None = Field(default=None, gt=0)


class EarlyPaySettingsUpdate(BaseModel):
    early_pay_discount_pct: float = Field(ge=0, le=100)
    early_pay_discount_days: int = Field(ge=0, le=365)


class SalesInvoiceNumberingUpdate(BaseModel):
    """Legacy flat body for invoice-only PATCH /sales/settings."""

    prefix: str = Field(min_length=1, max_length=20)
    next_number: int = Field(default=1, ge=1, le=999999)


class DocumentNumberingFields(BaseModel):
    prefix: str = Field(min_length=1, max_length=20)
    next_number: int = Field(default=1, ge=1, le=999999)


class SalesSettingsUpdate(BaseModel):
    invoice_numbering: DocumentNumberingFields | None = None
    quotation_numbering: DocumentNumberingFields | None = None
    sales_order_numbering: DocumentNumberingFields | None = None
    sales_return_numbering: DocumentNumberingFields | None = None
    credit_note_numbering: DocumentNumberingFields | None = None
    payment_receipt_numbering: DocumentNumberingFields | None = None
    # Legacy flat fields (invoice only)
    prefix: str | None = Field(default=None, min_length=1, max_length=20)
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


ScheduleFrequencyValue = Annotated[
    Literal["daily", "weekly"],
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


class ReportScheduleCreate(BaseModel):
    """Email report schedule create (BR-14)."""

    name: str = Field(min_length=2)
    # Schema Literal; blank/unknown → 422 (was free str → service 400)
    report_type: ReportTypeValue
    format: ReportExportFormatValue = "xlsx"
    # omit → daily; blank/invalid → 422 (was free dict; "" coerced to daily in service)
    frequency: ScheduleFrequencyValue = "daily"
    weekday: int | None = Field(default=None, ge=0, le=6)
    hour_utc: int = Field(default=6, ge=0, le=23)
    recipients: list[str] | str | None = None
    enabled: bool = True


class ReportScheduleUpdate(BaseModel):
    """Email report schedule patch — omit = no change; blank frequency/format/report_type → 422."""

    name: str | None = Field(default=None, min_length=2)
    report_type: ReportTypeValue | None = None
    format: ReportExportFormatValue | None = None
    frequency: ScheduleFrequencyValue | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    hour_utc: int | None = Field(default=None, ge=0, le=23)
    recipients: list[str] | str | None = None
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


class WebhookCreate(BaseModel):
    """Outbound webhook endpoint create."""

    url: str = Field(min_length=1)
    # Closed event catalog; blank/unknown item → 422; empty list → 422
    events: list[WebhookEventValue] = Field(min_length=1)
    secret: str | None = None
    description: str | None = None
    is_active: bool = True


class WebhookUpdate(BaseModel):
    """Outbound webhook endpoint patch — omit = no change."""

    url: str | None = Field(default=None, min_length=1)
    events: list[WebhookEventValue] | None = Field(default=None, min_length=1)
    description: str | None = None
    is_active: bool | None = None
    rotate_secret: bool = False


class ExchangeRateUpsert(BaseModel):
    currency_code: str
    rate_to_base: float = Field(gt=0)


class ExchangeRateRefresh(BaseModel):
    currencies: list[str] | None = None


class FxAutoRefreshUpdate(BaseModel):
    fx_auto_refresh: bool


class BankConnectionCreate(BaseModel):
    account_id: str
    # BR-10.3 — schema Literal; omit defaults to mock; blank/invalid → 422
    provider: Literal["mock", "http_json"] = "mock"
    display_name: str | None = None
    external_account_id: str | None = None
    feed_url: str | None = None
    access_token: str | None = None
    auto_sync: bool = True
    auto_match_after_sync: bool = True
    sync_lookback_days: int = Field(default=30, ge=1, le=365)


class BankConnectionUpdate(BaseModel):
    # BR-10.3 — omit = no change; blank/invalid → 422 (no silent mock)
    provider: Literal["mock", "http_json"] | None = None
    display_name: str | None = None
    external_account_id: str | None = None
    feed_url: str | None = None
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


class SupplierPaymentCreate(BaseModel):
    supplier_id: str
    amount: float = Field(gt=0)
    purchase_order_id: str | None = None
    purchase_invoice_id: str | None = None
    # BR-11.2 — same settlement Literal; omit → bank_transfer; blank/invalid → 422
    payment_method: SettlementPaymentMethod = "bank_transfer"
    reference: str | None = None
    notes: str | None = None
    cheque_number: str | None = None
    bank_name: str | None = None
    cheque_date: datetime | None = None
    apply_early_discount: bool | None = None
    liquid_account_id: str | None = None
    currency: str | None = None
    exchange_rate: float | None = Field(default=None, gt=0)


class CreditLimitUpdate(BaseModel):
    credit_limit: float = Field(ge=0)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)


class NotificationPreferencesUpdate(BaseModel):
    preferences: dict


class JournalLineCreate(BaseModel):
    account_id: str | None = None
    account_code: str | None = None
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)
    description: str | None = None


class JournalCreate(BaseModel):
    description: str
    reference: str | None = None
    entry_date: date | None = None
    lines: list[JournalLineCreate] = Field(min_length=2)


class JournalUnpost(BaseModel):
    """Manual journal unpost — typed reason required (BR-10.2 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class ChequeLifecycleReason(BaseModel):
    """Cheque bounce / cancel — typed reason required (BR-10.4 honesty)."""

    reason: str = Field(min_length=1, max_length=500)


class PeriodCloseBody(BaseModel):
    """Close books through an inclusive calendar date (BR-10.2)."""

    through_date: date
    reason: str = Field(min_length=1, max_length=500)


class PeriodReopenBody(BaseModel):
    """Reopen: set an earlier closed-through date, or null to clear — reason required (BR-10.2 honesty)."""

    through_date: date | None = None
    reason: str = Field(min_length=1, max_length=500)


class PosSessionOpen(BaseModel):
    store_id: str | None = None
    opening_cash: float = Field(default=0, ge=0)


class PosSessionClose(BaseModel):
    actual_cash: float = Field(ge=0)
    closing_cash: float | None = None
    notes: str | None = None


class PosPaymentLine(BaseModel):
    """One tender toward a POS sale total (supports split payments)."""

    # BR-8.1 — schema Literal (+ wallet aliases via BeforeValidator); blank/invalid → 422
    payment_method: PosTenderMethod = "cash"
    amount: float = Field(gt=0)
    reference: str | None = None
    liquid_account_id: str | None = None


class PosSaleCreate(BaseModel):
    session_id: str | None = None
    party_id: str | None = None
    customer_name: str | None = Field(default=None, max_length=180)
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
