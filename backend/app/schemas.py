from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class SmsTestRequest(BaseModel):
    to: str | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    # ADR-006: MVP accepts English only; other locales rejected until packs ship.
    preferred_language: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TenantCreate(BaseModel):
    company_name: str
    slug: str
    industry: str = "retail"
    currency: str = "GHS"
    timezone: str | None = None
    tax_jurisdiction: str | None = None
    admin_email: EmailStr
    admin_password: str
    admin_full_name: str = "Company Administrator"


class DocumentNumberSeriesUpdate(BaseModel):
    prefix: str | None = None
    include_year: bool | None = None
    pad: int | None = Field(default=None, ge=1, le=12)
    next_number: int | None = Field(default=None, ge=1)


class DocumentNumberingUpdate(BaseModel):
    sales_invoice: DocumentNumberSeriesUpdate | None = None
    purchase_invoice: DocumentNumberSeriesUpdate | None = None
    purchase_order: DocumentNumberSeriesUpdate | None = None
    goods_receipt: DocumentNumberSeriesUpdate | None = None
    sales_quotation: DocumentNumberSeriesUpdate | None = None
    sales_order: DocumentNumberSeriesUpdate | None = None
    sales_return: DocumentNumberSeriesUpdate | None = None
    sales_credit_note: DocumentNumberSeriesUpdate | None = None
    purchase_return: DocumentNumberSeriesUpdate | None = None
    purchase_debit_note: DocumentNumberSeriesUpdate | None = None


class TenantProfileUpdate(BaseModel):
    company_name: str | None = None
    industry: str | None = None
    currency: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    address: str | None = None
    timezone: str | None = None
    fiscal_year_start: str | None = None
    tax_jurisdiction: str | None = None
    tax_registration_number: str | None = None
    tax_filing_period: str | None = None
    document_numbering: DocumentNumberingUpdate | None = None
    invoice_print_template: str | None = None
    receipt_print_template: str | None = None
    document_header: str | None = None
    document_footer: str | None = None
    plan_code: str | None = None
    legal_name: str | None = None
    registration_number: str | None = None
    billing_address: str | None = None
    shipping_address: str | None = None
    warehouse_address: str | None = None
    contact_person_name: str | None = None
    contact_person_email: EmailStr | None = None
    contact_person_phone: str | None = None
    inactivity_timeout_minutes: int | None = Field(default=None, ge=5, le=480)
    date_format: str | None = None
    number_format: str | None = None
    time_format: str | None = None


class EmailSettingsUpdate(BaseModel):
    smtp_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    clear_password: bool = False
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str | None = None
    smtp_use_tls: bool | None = None
    smtp_use_ssl: bool | None = None


class InvoiceSendRequest(BaseModel):
    to: str | None = None


class TenantSuspendRequest(BaseModel):
    reason: str | None = None


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
    slug: str
    label: str
    description: str | None = None
    base_role: str | None = "cashier"
    permissions: dict | None = None
    record_scope: str = "own"


class CustomRoleUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    permissions: dict | None = None
    record_scope: str | None = None
    is_active: bool | None = None


class CustomRolePermissionsUpdate(BaseModel):
    permissions: dict
    record_scope: str | None = None


class ProductCreate(BaseModel):
    name: str
    sku: str
    barcode: str | None = None
    category: str = "General"
    category_id: str | None = None
    brand_id: str | None = None
    unit_id: str | None = None
    cost_price: float = 0
    selling_price: float = 0
    stock_qty: float = 0
    minimum_stock: float = 0
    reorder_level: float = 0
    weight: float | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    tax_rate_id: str | None = None
    tax_exempt: bool = False
    tracks_batches: bool = False


class ProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    barcode: str | None = None
    category: str | None = None
    category_id: str | None = None
    brand_id: str | None = None
    unit_id: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None
    minimum_stock: float | None = None
    reorder_level: float | None = None
    weight: float | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    tax_rate_id: str | None = None
    tax_exempt: bool | None = None
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
    is_active: bool | None = None
    tax_rate_id: str | None = None


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
    conversion_factor: float = Field(default=1, gt=0)


class UnitOfMeasureUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    base_unit_id: str | None = None
    conversion_factor: float | None = Field(default=None, gt=0)
    is_active: bool | None = None
    clear_base_unit: bool = False


class ProductVariantCreate(BaseModel):
    name: str
    sku: str
    barcode: str | None = None
    size: str | None = None
    color: str | None = None
    flavor: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None


class ProductVariantUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    barcode: str | None = None
    size: str | None = None
    color: str | None = None
    flavor: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None
    is_active: bool | None = None


class ProductImagePrimaryUpdate(BaseModel):
    is_primary: bool = True


class PartyCreate(BaseModel):
    """Legacy minimal customer create; prefer CustomerCreate."""

    name: str
    email: EmailStr | None = None
    phone: str | None = None
    credit_limit: float = 0
    code: str | None = None
    party_type: str | None = "registered"
    category: str | None = None
    address: str | None = None
    notes: str | None = None
    payment_terms_days: int = 0


class SupplierContactCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    designation: str | None = None
    is_primary: bool = False


class CustomerContactCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    designation: str | None = None
    is_primary: bool = False


class CustomerCreate(BaseModel):
    name: str
    code: str | None = None
    party_type: str | None = "registered"
    category: str | None = None
    customer_group_id: str | None = None
    customer_group: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None
    payment_terms_days: int = 0
    credit_limit: float = 0
    contacts: list[CustomerContactCreate] = Field(default_factory=list)


class CustomerUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    party_type: str | None = None
    category: str | None = None
    customer_group_id: str | None = None
    customer_group: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None
    payment_terms_days: int | None = None
    credit_limit: float | None = None
    status: str | None = None


class CustomerGroupCreate(BaseModel):
    name: str
    discount_percent: float = Field(default=0, ge=0, le=100)


class CustomerGroupUpdate(BaseModel):
    name: str | None = None
    discount_percent: float | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class SupplierCreate(BaseModel):
    name: str
    code: str | None = None
    party_type: str | None = None
    category: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    payment_terms_days: int = 0
    early_pay_discount_pct: float | None = Field(default=None, ge=0, le=100)
    early_pay_discount_days: int | None = Field(default=None, ge=0, le=365)
    credit_limit: float = 0
    contacts: list[SupplierContactCreate] = Field(default_factory=list)


class SupplierUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    party_type: str | None = None
    category: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    payment_terms_days: int | None = None
    early_pay_discount_pct: float | None = Field(default=None, ge=0, le=100)
    early_pay_discount_days: int | None = Field(default=None, ge=0, le=365)
    credit_limit: float | None = None
    status: str | None = None


class LineItem(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
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


class StockAdjust(BaseModel):
    quantity: float
    notes: str | None = None
    reason: str = "other"
    warehouse_id: str | None = None


class StockMove(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    notes: str | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_id: str | None = None
    batch_number: str | None = None
    manufacturing_date: datetime | None = None
    expiry_date: datetime | None = None


class OpeningStockLine(BaseModel):
    product_id: str
    quantity: float = Field(ge=0)
    mode: str = "add"
    notes: str | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_number: str | None = None
    manufacturing_date: datetime | None = None
    expiry_date: datetime | None = None
    fiscal_period: str | None = None


class OpeningStockRequest(BaseModel):
    """Single-line or multi-line opening stock (BR-5.2)."""

    product_id: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    mode: str = "add"
    notes: str | None = None
    warehouse_id: str | None = None
    variant_id: str | None = None
    batch_number: str | None = None
    manufacturing_date: datetime | None = None
    expiry_date: datetime | None = None
    fiscal_period: str | None = None
    items: list[OpeningStockLine] = Field(default_factory=list)


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
    department_id: str | None = None
    expense_date: datetime | None = None


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
    department_id: str | None = None
    clear_store: bool = False
    clear_department: bool = False


class ExpenseOcrApply(BaseModel):
    """Stage 10 A1 — human-confirmed OCR field apply (no silent auto-write)."""

    confirm: bool = False
    category: str | None = None
    category_id: str | None = None
    description: str | None = None
    amount: float | None = Field(default=None, gt=0)
    payment_method: str | None = None
    reference: str | None = None
    payee: str | None = None
    expense_date: datetime | None = None


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
    store_id: str | None = None
    department_id: str | None = None


class RecurringExpenseUpdate(BaseModel):
    """Skip or modify the next occurrence; optionally pause the series."""

    skip_next: bool | None = None
    next_amount: float | None = Field(default=None, gt=0)
    next_description: str | None = None
    clear_next_override: bool | None = None
    is_active: bool | None = None
    amount: float | None = Field(default=None, gt=0)
    description: str | None = None
    frequency: str | None = None
    payment_method: str | None = None
    payee: str | None = None


class ApprovalLevelUpdate(BaseModel):
    min_amount: float = Field(gt=0)
    roles: list[str] = Field(min_length=1)
    label: str | None = None
    step: int | None = None


class ExpenseThresholdUpdate(BaseModel):
    expense_approval_threshold: float | None = Field(default=None, gt=0)
    expense_l2_threshold: float | None = Field(default=None, gt=0)
    levels: list[ApprovalLevelUpdate] | None = None


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
    operating_hours: dict | None = None
    is_active: bool | None = None


class StoreDrawerSettingsUpdate(BaseModel):
    drawer_mode: str | None = None
    drawer_host: str | None = None
    drawer_port: int | None = Field(default=None, ge=1, le=65535)
    drawer_open_on_cash: bool | None = None


class PosDrawerOpen(BaseModel):
    reason: str = "manual"


class StoreReorderPolicyUpdate(BaseModel):
    product_id: str
    minimum_stock: float = Field(default=0, ge=0)
    reorder_level: float = Field(ge=0)
    reorder_qty: float = Field(default=0, ge=0)


class InventoryFefoSettingsUpdate(BaseModel):
    fefo_strict_warehouse: bool


class WarehouseCreate(BaseModel):
    name: str
    code: str
    store_id: str | None = None
    warehouse_type: str | None = "retail"
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
    is_active: bool | None = None


class StockTransferItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)


class StockTransferCreate(BaseModel):
    from_store_id: str
    to_store_id: str
    notes: str | None = None
    submit: bool = False
    items: list[StockTransferItemCreate] = Field(min_length=1)


class WarehouseStockTransferCreate(BaseModel):
    from_warehouse_id: str
    to_warehouse_id: str
    notes: str | None = None
    submit: bool = False
    items: list[StockTransferItemCreate] = Field(min_length=1)


class LowStockReorderPoCreate(BaseModel):
    product_id: str
    supplier_id: str
    quantity: float | None = Field(default=None, gt=0)
    warehouse_id: str | None = None
    unit_price: float | None = Field(default=None, ge=0)
    notes: str | None = None


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
    """Partial update for tax rate lifecycle (Stage 14 T1)."""

    name: str | None = None
    rate: float | None = Field(default=None, ge=0)
    tax_type: str | None = None
    pricing_mode: str | None = None
    components: list[dict] | None = None
    clear_components: bool = False
    is_reverse_charge: bool | None = None
    is_default: bool | None = None
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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class EmailVerifyConfirm(BaseModel):
    token: str


class EmailVerificationResend(BaseModel):
    email: EmailStr
    tenant_id: str


class PurchaseOrderItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    tax_rate: float = Field(default=0, ge=0)
    discount: float = Field(default=0, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    warehouse_id: str | None = None
    delivery_address: str | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class BarcodeLabelItem(BaseModel):
    product_id: str
    variant_id: str | None = None
    copies: int = Field(default=1, ge=1, le=50)


class BarcodeLabelPrintRequest(BaseModel):
    items: list[BarcodeLabelItem] = Field(min_length=1, max_length=100)
    format: str = "html"
    include_price: bool = True
    columns: int = Field(default=3, ge=1, le=4)
    # Stage 97 I1 — barcode (default) or qr
    code_type: str = "barcode"


class PurchaseOrderItemUpdate(BaseModel):
    id: str | None = None
    product_id: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    tax_rate: float = Field(default=0, ge=0)
    discount: float = Field(default=0, ge=0)


class PurchaseOrderUpdate(BaseModel):
    warehouse_id: str | None = None
    delivery_address: str | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemUpdate] | None = None
    reason: str | None = None


class PurchaseOrderAmend(BaseModel):
    reason: str = Field(min_length=1)
    warehouse_id: str | None = None
    delivery_address: str | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemUpdate] | None = None


class PurchaseRequestItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_price: float | None = None
    tax_rate: float = Field(default=0, ge=0)
    notes: str | None = None


class PurchaseRequestCreate(BaseModel):
    supplier_id: str
    warehouse_id: str | None = None
    department: str | None = None
    required_date: datetime | None = None
    notes: str | None = None
    items: list[PurchaseRequestItemCreate] = Field(min_length=1)


class PurchaseRequestReject(BaseModel):
    reason: str | None = None


class PurchaseRequestDecision(BaseModel):
    comment: str | None = None


class PurchaseRequestApprovalSettingsUpdate(BaseModel):
    levels: list[ApprovalLevelUpdate] = Field(min_length=1)


class GrnItemCreate(BaseModel):
    po_item_id: str
    received_qty: float = Field(gt=0)
    accepted_qty: float | None = None
    rejected_qty: float = Field(default=0, ge=0)
    rejection_reason: str | None = None
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
    reason: str = "other"
    notes: str | None = None
    items: list[PurchaseReturnItemCreate] = Field(min_length=1)


class PurchaseInvoiceItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_price: float | None = None
    tax_rate: float = Field(default=0, ge=0)
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


class PurchaseInvoiceOcrApply(BaseModel):
    """Stage 10 A1 — human-confirmed OCR header apply on draft purchase invoices."""

    confirm: bool = False
    supplier_invoice_number: str | None = None
    notes: str | None = None
    invoice_date: datetime | None = None
    due_date: datetime | None = None


class SalesInvoiceItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
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
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesQuotationCreate(BaseModel):
    customer_id: str
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = None
    valid_days: int = Field(default=14, ge=1, le=365)
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesOrderCreate(BaseModel):
    customer_id: str
    quotation_id: str | None = None
    store_id: str | None = None
    warehouse_id: str | None = None
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = None
    delivery_date: datetime | None = None
    delivery_address: str | None = None
    items: list[SalesInvoiceItemCreate] = Field(min_length=1)


class SalesOrderUpdate(BaseModel):
    notes: str | None = None
    delivery_date: datetime | None = None
    delivery_address: str | None = None
    store_id: str | None = None
    warehouse_id: str | None = None


class SalesReturnItemCreate(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    condition: str | None = None
    variant_id: str | None = None


class SalesReturnCreate(BaseModel):
    sales_invoice_id: str
    reason: str = "other"
    restock: bool = True
    notes: str | None = None
    items: list[SalesReturnItemCreate] = Field(min_length=1)


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
    store_id: str | None = None
    lines: list[JournalLineCreate] = Field(min_length=2)


class CoaAccountCreate(BaseModel):
    """Create a non-system chart-of-accounts entry (BR-10.1)."""

    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=150)
    account_type: str = Field(description="asset|liability|equity|income|expense")
    parent_id: str | None = None


class CoaAccountUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    account_type: str | None = None
    parent_id: str | None = None
    is_active: bool | None = None


class OpeningBalanceCreate(BaseModel):
    """Natural-side opening balance amount (positive = natural balance)."""

    amount: float
    description: str | None = None


class LiquidAccountCreate(BaseModel):
    """Create a cash or bank GL account (BR-10.3)."""

    kind: str = Field(description="cash or bank")
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=150)
    bank_name: str | None = None
    account_number: str | None = None
    bank_branch: str | None = None


class LiquidAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    bank_name: str | None = None
    account_number: str | None = None
    bank_branch: str | None = None
    clear_bank_details: bool | None = None


class LiquidTransferCreate(BaseModel):
    """Deposit / withdrawal / transfer between liquid accounts."""

    from_account_id: str
    to_account_id: str
    amount: float = Field(gt=0)
    description: str | None = None
    reference: str | None = None
    kind: str | None = Field(
        default=None,
        description="Optional deposit|withdrawal|transfer; inferred from account types when omitted",
    )


class PosSessionOpen(BaseModel):
    store_id: str | None = None
    opening_cash: float = Field(default=0, ge=0)


class PosSessionClose(BaseModel):
    actual_cash: float = Field(ge=0)
    closing_cash: float | None = None
    notes: str | None = None


class PosPaymentLine(BaseModel):
    """One tender toward a POS sale total (BR-8.1 split payments)."""

    payment_method: str = "cash"
    amount: float = Field(gt=0)
    reference: str | None = None
    liquid_account_id: str | None = None


class CreditLimitOverrideRequest(BaseModel):
    """Optional body for invoice post / credit sale when exceeding the limit (BR-11.1)."""

    credit_limit_override: bool = False
    credit_override_reason: str | None = None


class PosSaleCreate(BaseModel):
    session_id: str | None = None
    party_id: str | None = None
    subtotal: float = 0
    tax: float = 0
    total: float = 0
    discount_amount: float = Field(default=0, ge=0)
    status: str = "completed"
    payment_method: str = "cash"
    payments: list[PosPaymentLine] | None = None
    credit_limit_override: bool = False
    credit_override_reason: str | None = None
    payload: dict = Field(default_factory=dict)
    items: list[LineItem] = Field(min_length=1)
