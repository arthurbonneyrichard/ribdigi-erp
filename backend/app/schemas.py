from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


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
    industry: str = "retail"
    currency: str = "GHS"
    admin_email: EmailStr
    admin_password: str


class TenantProfileUpdate(BaseModel):
    company_name: str | None = None
    industry: str | None = None
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
    tax_filing_period: str | None = None
    date_format: str | None = None
    decimal_separator: str | None = None
    thousand_separator: str | None = None
    time_format: str | None = None
    inactivity_timeout_minutes: int | None = Field(default=None, ge=5, le=480)


class TenantSuspendRequest(BaseModel):
    reason: str | None = None


class TenantSubscriptionAssign(BaseModel):
    package_code: str
    term_value: int = Field(..., ge=1, le=120)
    term_unit: str = "months"  # months | years
    start_at: datetime | None = None
    activate: bool = True
    enabled_modules: list[str] | None = None


class TenantModulesUpdate(BaseModel):
    enabled_modules: list[str] | None = None
    reset_to_package: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "cashier"
    phone: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    record_scope: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None
    # Record visibility: own | department | branch | all
    record_scope: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    clear_branch: bool = False
    clear_department: bool = False


class PlatformGrantAccess(BaseModel):
    """Grant an existing app user access to the software-owner dashboard."""

    user_id: str
    role: str = "platform_support"


class PlatformRevokeAccess(BaseModel):
    """Revoke software-owner dashboard access; keep the account as an app user."""

    fallback_role: str = "company_admin"


class AccountCreate(BaseModel):
    code: str
    name: str
    account_type: str = "asset"
    liquid_kind: str | None = None  # cash | bank
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
    kind: str = "transfer"  # transfer | deposit | withdrawal
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
    base_role: str | None = None
    record_scope: str | None = None


class CustomRoleUpdate(BaseModel):
    label: str | None = None
    permissions: dict[str, list[str]] | None = None
    record_scope: str | None = None
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
    tax_supply_class: str = "standard"
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
    tax_supply_class: str | None = None
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
    profile_type: str | None = "registered"
    category: str | None = None
    status: str = "active"
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
    profile_type: str | None = None
    category: str | None = None
    status: str | None = None
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
    status: str = "completed"
    payload: dict = Field(default_factory=dict)
    items: list[LineItem] = Field(default_factory=list)
    override_credit_limit: bool = False
    override_reason: str | None = Field(default=None, max_length=500)


class CreditLimitOverrideBody(BaseModel):
    """Optional body for posting sales that may exceed credit limit (BR-11.1)."""

    override_credit_limit: bool = False
    override_reason: str | None = Field(default=None, max_length=500)


class StockAdjust(BaseModel):
    quantity: float
    reason: str  # damage | theft | expiry | found | lost
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
    # Stock-out (BR-5.2): sale | transfer | adjustment | damage | internal | other
    reference_type: str | None = None
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
    payment_method: str = "cash"
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
    payment_method: str = "cash"
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
    payment_method: str | None = None
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
    comment: str | None = None
    reason: str | None = None


class RecurringExpenseCreate(BaseModel):
    category: str | None = None
    category_id: str | None = None
    description: str = ""
    amount: float = Field(gt=0)
    frequency: str = "monthly"
    payment_method: str = "bank_transfer"
    payee: str | None = None
    branch_id: str | None = None
    department_id: str | None = None


class RecurringExpenseUpdate(BaseModel):
    is_active: bool | None = None
    amount: float | None = Field(default=None, gt=0)
    payee: str | None = None
    clear_payee: bool = False
    description: str | None = None
    payment_method: str | None = None
    frequency: str | None = None
    category_id: str | None = None
    category: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    clear_branch: bool = False
    clear_department: bool = False


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
    drawer_mode: str | None = None
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
    warehouse_type: str = "retail"
    manager_id: str | None = None
    address: str | None = None
    capacity: float | None = Field(default=None, ge=0)


class WarehouseUpdate(BaseModel):
    name: str | None = None
    store_id: str | None = None
    clear_store: bool = False
    warehouse_type: str | None = None
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
    reason: str | None = None


class TaxCreate(BaseModel):
    name: str
    rate: float = Field(ge=0)
    tax_type: str = "vat"
    pricing_mode: str = "exclusive"
    components: list[dict] | None = None
    is_reverse_charge: bool = False
    is_default: bool = False
    is_active: bool = True


class TaxUpdate(BaseModel):
    name: str | None = None
    rate: float | None = Field(default=None, ge=0)
    tax_type: str | None = None
    pricing_mode: str | None = None
    components: list[dict] | None = None
    is_reverse_charge: bool | None = None
    is_active: bool | None = None


class TaxCalculateRequest(BaseModel):
    amount: float = Field(gt=0)
    rate: float | None = None
    tax_rate_id: str | None = None
    pricing_mode: str | None = None
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
    reason: str | None = None
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
    reason: str | None = None


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
    # Required coded reason (BR-6.6); no silent default to "other"
    reason: str
    notes: str | None = None
    items: list[PurchaseReturnItemCreate] = Field(min_length=1)


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
    reason: str | None = None


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


class SalesReturnItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    # Required coded condition (BR-7.5); no silent sellable/discard from restock
    condition: str
    variant_id: str | None = None


class SalesReturnCreate(BaseModel):
    sales_invoice_id: str
    # Required coded reason (BR-7.5); no silent default to "other"
    reason: str
    restock: bool = True
    notes: str | None = None
    items: list[SalesReturnItemCreate] = Field(min_length=1)


class SalesReturnPost(BaseModel):
    settlement_method: str | None = None  # adjust | refund (required when return exceeds open AR)
    payment_method: str = "cash"
    liquid_account_id: str | None = None


class CustomerPaymentCreate(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    sales_invoice_id: str | None = None
    payment_method: str = "cash"
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
    default_invoice_template: str | None = None
    default_receipt_paper: str | None = None


class ExchangeRateUpsert(BaseModel):
    currency_code: str
    rate_to_base: float = Field(gt=0)


class ExchangeRateRefresh(BaseModel):
    currencies: list[str] | None = None


class FxAutoRefreshUpdate(BaseModel):
    fx_auto_refresh: bool


class BankConnectionCreate(BaseModel):
    account_id: str
    provider: str = "mock"
    display_name: str | None = None
    external_account_id: str | None = None
    feed_url: str | None = None
    access_token: str | None = None
    auto_sync: bool = True
    auto_match_after_sync: bool = True
    sync_lookback_days: int = Field(default=30, ge=1, le=365)


class BankConnectionUpdate(BaseModel):
    provider: str | None = None
    display_name: str | None = None
    external_account_id: str | None = None
    feed_url: str | None = None
    access_token: str | None = None
    clear_credentials: bool | None = None
    auto_sync: bool | None = None
    auto_match_after_sync: bool | None = None
    sync_lookback_days: int | None = Field(default=None, ge=1, le=365)
    is_active: bool | None = None


class SupplierPaymentCreate(BaseModel):
    supplier_id: str
    amount: float = Field(gt=0)
    purchase_order_id: str | None = None
    purchase_invoice_id: str | None = None
    payment_method: str = "bank_transfer"
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


class PeriodCloseBody(BaseModel):
    """Close books through an inclusive calendar date (BR-10.2)."""

    through_date: date


class PeriodReopenBody(BaseModel):
    """Reopen: set an earlier closed-through date, or null to clear."""

    through_date: date | None = None


class PosSessionOpen(BaseModel):
    store_id: str | None = None
    opening_cash: float = Field(default=0, ge=0)


class PosSessionClose(BaseModel):
    actual_cash: float = Field(ge=0)
    closing_cash: float | None = None
    notes: str | None = None


class PosPaymentLine(BaseModel):
    """One tender toward a POS sale total (supports split payments)."""

    payment_method: str = "cash"
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
    status: str = "completed"
    payment_method: str = "cash"
    payments: list[PosPaymentLine] | None = None
    payload: dict = Field(default_factory=dict)
    items: list[LineItem] = Field(min_length=1)
    override_credit_limit: bool = False
    override_reason: str | None = Field(default=None, max_length=500)
