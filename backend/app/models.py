import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(50), default="retail")
    currency: Mapped[str] = mapped_column(String(10), default="GHS")
    tax_jurisdiction: Mapped[str] = mapped_column(String(10), default="GH")
    tax_registration_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_filing_period: Mapped[str] = mapped_column(String(20), default="monthly")
    status: Mapped[str] = mapped_column(String(20), default="trial")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Accra")
    fiscal_year_start: Mapped[str] = mapped_column(String(5), default="01-01")
    expense_approval_threshold: Mapped[float] = mapped_column(Numeric(14, 2), default=100)
    expense_l2_threshold: Mapped[float] = mapped_column(Numeric(14, 2), default=1000)
    # Optional N-level approval matrix: {"levels": [{step, min_amount, roles, label}, ...]}
    expense_approval_matrix: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # PR role-chain matrix: {"levels": [{step, roles, label}, ...]} (no amount thresholds)
    purchase_approval_matrix: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # e.g. 2/10 net 30 → pct=2, days=10 (0 disables)
    early_pay_discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    early_pay_discount_days: Mapped[int] = mapped_column(Integer, default=0)
    # Sales invoice numbers: {prefix}-{YYYY}-{NNNN} (series resets each calendar year)
    sales_invoice_number_prefix: Mapped[str] = mapped_column(String(20), default="INV")
    sales_invoice_number_next: Mapped[int] = mapped_column(Integer, default=1)
    sales_invoice_number_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # When true, scheduled FX job refreshes this tenant's exchange rates from the live feed.
    fx_auto_refresh: Mapped[bool] = mapped_column(Boolean, default=True)
    # When true, store/warehouse stock-outs only consume batches tagged to that warehouse (no NULL fallback).
    fefo_strict_warehouse: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grace_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_notices: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="cashier")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_pending_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomRole(Base):
    __tablename__ = "custom_roles"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    key: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(120))
    base_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    record_scope: Mapped[str] = mapped_column(String(20), default="own")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthToken(Base):
    """One-time tokens for email verification and password reset."""

    __tablename__ = "auth_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    code: Mapped[str] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Cash drawer: none|mock|network|browser_bridge
    drawer_mode: Mapped[str] = mapped_column(String(30), default="none")
    drawer_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drawer_port: Mapped[int] = mapped_column(Integer, default=9100)
    drawer_open_on_cash: Mapped[bool] = mapped_column(Boolean, default=True)


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(150))
    code: Mapped[str] = mapped_column(String(50))


class WarehouseStock(Base):
    """Per-warehouse quantity; product.stock_qty remains the consolidated total."""

    __tablename__ = "warehouse_stocks"
    __table_args__ = (UniqueConstraint("tenant_id", "warehouse_id", "product_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    reorder_level: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    reorder_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)


class ProductCategory(Base):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "sku"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    sku: Mapped[str] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(100), default="General")
    category_id: Mapped[str | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True, index=True)
    brand_id: Mapped[str | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("units_of_measure.id"), nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cost_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    selling_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    stock_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    reorder_level: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    tax_rate_id: Mapped[str | None] = mapped_column(ForeignKey("tax_rates.id"), nullable=True)
    tax_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    # standard | zero_rated | exempt (tax_exempt kept in sync with exempt)
    tax_supply_class: Mapped[str] = mapped_column(String(20), default="standard")
    tracks_batches: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("tenant_id", "sku"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sku: Mapped[str] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    size: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    flavor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cost_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    selling_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    stock_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductImage(Base):
    """Gallery images for a product; one may be marked primary (synced to products.image_url)."""

    __tablename__ = "product_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductBatch(Base):
    __tablename__ = "product_batches"
    __table_args__ = (UniqueConstraint("tenant_id", "product_id", "batch_number", "variant_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    batch_number: Mapped[str] = mapped_column(String(80), index=True)
    manufacturing_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True, index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("product_batches.id"), nullable=True, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    movement_type: Mapped[str] = mapped_column(String(30), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    quantity_before: Mapped[float] = mapped_column(Numeric(14, 3))
    quantity_after: Mapped[float] = mapped_column(Numeric(14, 3))
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    credit_limit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    tx_type: Mapped[str] = mapped_column(String(30), index=True)
    reference: Mapped[str] = mapped_column(String(80), index=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("pos_sessions.id"), nullable=True, index=True)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    budget_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("expense_categories.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    expense_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    payment_method: Mapped[str] = mapped_column(String(40), default="cash")
    liquid_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payee: Mapped[str | None] = mapped_column(String(150), nullable=True)
    store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_step: Mapped[int] = mapped_column(Integer, default=1)
    approval_steps_required: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExpenseApprovalAction(Base):
    __tablename__ = "expense_approval_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    expense_id: Mapped[str] = mapped_column(ForeignKey("expenses.id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))  # approve | reject | auto_approve
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("expense_categories.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    payment_method: Mapped[str] = mapped_column(String(40), default="bank_transfer")
    payee: Mapped[str | None] = mapped_column(String(150), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(150))
    account_type: Mapped[str] = mapped_column(String(30))
    balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_cash_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bank_account: Mapped[bool] = mapped_column(Boolean, default=False)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(60), nullable=True)


class BankAccountConnection(Base):
    """Live bank feed link for a liquid GL account (API connector)."""

    __tablename__ = "bank_account_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "account_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="mock")  # mock|http_json
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_account_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    feed_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credentials_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_sync: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_match_after_sync: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_lookback_days: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_statement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    statement_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    closing_balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft|in_progress|reconciled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BankClearingGroup(Base):
    """Groups N bank lines against M journal lines when totals match."""

    __tablename__ = "bank_clearing_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    statement_id: Mapped[str] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BankClearingBookLink(Base):
    __tablename__ = "bank_clearing_book_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("bank_clearing_groups.id"), index=True)
    journal_line_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entry_lines.id"), unique=True, index=True
    )


class BankStatementLine(Base):
    __tablename__ = "bank_statement_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    statement_id: Mapped[str] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    txn_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))  # + deposit / - withdrawal
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unmatched")  # unmatched|matched|ignored
    matched_journal_line_id: Mapped[str | None] = mapped_column(
        ForeignKey("journal_entry_lines.id"), nullable=True, index=True
    )
    clearing_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("bank_clearing_groups.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExchangeRate(Base):
    """Foreign currency → tenant base currency (1 unit foreign = rate_to_base base)."""

    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("tenant_id", "currency_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    currency_code: Mapped[str] = mapped_column(String(10), index=True)
    rate_to_base: Mapped[float] = mapped_column(Numeric(18, 8))
    # manual | open_er_api | frankfurter | …
    source: Mapped[str] = mapped_column(String(40), default="manual")
    provider_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaxRate(Base):
    __tablename__ = "tax_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    rate: Mapped[float] = mapped_column(Numeric(7, 4))
    tax_type: Mapped[str] = mapped_column(String(30), default="vat")
    pricing_mode: Mapped[str] = mapped_column(String(20), default="exclusive")
    # Optional compound legs: [{code, name, rate, basis: net|compound}]
    components: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Buyer self-assesses; seller does not charge tax on the document total.
    is_reverse_charge: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="system", index=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="unread", index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Append-only activity log with optional hash chaining for tamper evidence."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(40), default="system", index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    integrity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (UniqueConstraint("tenant_id", "request_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    request_number: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft -> pending -> approved | rejected -> converted
    preferred_supplier_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id"), nullable=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    required_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_step: Mapped[int] = mapped_column(Integer, default=1)
    approval_steps_required: Mapped[int] = mapped_column(Integer, default=1)
    converted_po_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseRequestApprovalAction(Base):
    __tablename__ = "purchase_request_approval_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_request_id: Mapped[str] = mapped_column(ForeignKey("purchase_requests.id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))  # approve | reject
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseRequestItem(Base):
    __tablename__ = "purchase_request_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_request_id: Mapped[str] = mapped_column(ForeignKey("purchase_requests.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("tenant_id", "po_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    po_number: Mapped[str] = mapped_column(String(50), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft -> sent -> partially_received -> received | cancelled
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    emailed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    received_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class PurchaseOrderAmendment(Base):
    __tablename__ = "purchase_order_amendments"
    __table_args__ = (UniqueConstraint("purchase_order_id", "revision_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notified_supplier: Mapped[bool] = mapped_column(Boolean, default=False)
    emailed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "grn_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    grn_number: Mapped[str] = mapped_column(String(50), index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="posted")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    goods_receipt_id: Mapped[str] = mapped_column(ForeignKey("goods_receipts.id"), index=True)
    po_item_id: Mapped[str] = mapped_column(ForeignKey("purchase_order_items.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    received_qty: Mapped[float] = mapped_column(Numeric(14, 3))
    accepted_qty: Mapped[float] = mapped_column(Numeric(14, 3))
    rejected_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalesInvoice(Base):
    __tablename__ = "sales_invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft -> posted/sent/partial/overdue/paid | cancelled
    # posted = approved/open; sent = emailed while unpaid; overdue = past due with balance
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    # Memo tax under reverse charge (not charged to customer / not seller output).
    reverse_charge_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    # Document currency; exchange_rate converts 1 doc unit → base (locked at create).
    currency: Mapped[str] = mapped_column(String(10), default="")
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 8), default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id"), nullable=True, index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quotation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    sales_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    emailed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SalesInvoiceItem(Base):
    __tablename__ = "sales_invoice_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    sales_invoice_id: Mapped[str] = mapped_column(ForeignKey("sales_invoices.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    tax_supply_class: Mapped[str] = mapped_column(String(20), default="standard")
    discount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    line_subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class CustomerPayment(Base):
    __tablename__ = "customer_payments"
    __table_args__ = (UniqueConstraint("tenant_id", "payment_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    payment_number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    sales_invoice_id: Mapped[str | None] = mapped_column(ForeignKey("sales_invoices.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    payment_method: Mapped[str] = mapped_column(String(40), default="cash")
    early_payment_discount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="")
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 8), default=1)
    fx_gain_loss: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    liquid_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"
    __table_args__ = (UniqueConstraint("tenant_id", "payment_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    payment_number: Mapped[str] = mapped_column(String(50), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    purchase_order_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    purchase_invoice_id: Mapped[str | None] = mapped_column(
        ForeignKey("purchase_invoices.id"), nullable=True, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    payment_method: Mapped[str] = mapped_column(String(40), default="bank_transfer")
    early_payment_discount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="")
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 8), default=1)
    fx_gain_loss: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    liquid_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Cheque(Base):
    """Customer (received) or supplier (issued) cheque lifecycle."""

    __tablename__ = "cheques"
    __table_args__ = (UniqueConstraint("tenant_id", "cheque_number", "direction"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    # received (customer) | issued (supplier/expense)
    direction: Mapped[str] = mapped_column(String(20), index=True)
    # pending -> deposited (received) -> cleared | bounced | cancelled
    # pending -> cleared | bounced | cancelled (issued)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    cheque_number: Mapped[str] = mapped_column(String(50), index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cheque_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id"), nullable=True, index=True)
    customer_payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("customer_payments.id"), nullable=True, index=True
    )
    supplier_payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("supplier_payments.id"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deposited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PosSession(Base):
    """Cashier shift / POS session with cash reconciliation."""

    __tablename__ = "pos_sessions"
    __table_args__ = (UniqueConstraint("tenant_id", "session_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_number: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    opening_cash: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    expected_cash: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    actual_cash: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    cash_sales: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    card_sales: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    other_sales: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_sales: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    sale_count: Mapped[int] = mapped_column(Integer, default=0)
    variance: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PosPayment(Base):
    """Tender line for a POS sale (supports split payments)."""

    __tablename__ = "pos_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    sale_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    payment_method: Mapped[str] = mapped_column(String(40), default="cash")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    liquid_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "entry_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    entry_number: Mapped[str] = mapped_column(String(50), index=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    total_debit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_credit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="posted")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    journal_entry_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    debit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    credit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    __table_args__ = (UniqueConstraint("tenant_id", "transfer_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    transfer_number: Mapped[str] = mapped_column(String(50), index=True)
    from_store_id: Mapped[str] = mapped_column(ForeignKey("stores.id"), index=True)
    to_store_id: Mapped[str] = mapped_column(ForeignKey("stores.id"), index=True)
    from_warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    to_warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Dual approval: step 1 source manager → step 2 dest manager (BR-13.2)
    approval_step: Mapped[int] = mapped_column(Integer, default=0)
    approval_steps_required: Mapped[int] = mapped_column(Integer, default=2)
    source_approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dest_approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dest_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipped_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    received_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("stock_transfers.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    shipped_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    received_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)


class StockCount(Base):
    """Physical inventory count session for a warehouse."""

    __tablename__ = "stock_counts"
    __table_args__ = (UniqueConstraint("tenant_id", "count_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    count_number: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StockCountItem(Base):
    __tablename__ = "stock_count_items"
    __table_args__ = (UniqueConstraint("tenant_id", "stock_count_id", "product_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    stock_count_id: Mapped[str] = mapped_column(ForeignKey("stock_counts.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    expected_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    counted_qty: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class BackupJob(Base):
    __tablename__ = "backup_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    storage_path: Mapped[str] = mapped_column(Text, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="")
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True)
    record_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BackupSettings(Base):
    __tablename__ = "backup_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency: Mapped[str] = mapped_column(String(20), default="daily")
    retention_count: Mapped[int] = mapped_column(Integer, default=30)
    hour_utc: Mapped[int] = mapped_column(Integer, default=2)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReportSchedule(Base):
    """Tenant-configured scheduled report email delivery."""

    __tablename__ = "report_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    report_type: Mapped[str] = mapped_column(String(60), index=True)
    format: Mapped[str] = mapped_column(String(10), default="xlsx")
    frequency: Mapped[str] = mapped_column(String(20), default="daily")
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=Mon .. 6=Sun for weekly
    hour_utc: Mapped[int] = mapped_column(Integer, default=6)
    recipients: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TwoFactorBackupCode(Base):
    __tablename__ = "two_factor_backup_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(128), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    public_key: Mapped[str] = mapped_column(Text)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    transports: Mapped[list | None] = mapped_column(JSON, nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    backed_up: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WebAuthnChallenge(Base):
    __tablename__ = "webauthn_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20), index=True)
    challenge: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SalesQuotation(Base):
    __tablename__ = "sales_quotations"
    __table_args__ = (UniqueConstraint("tenant_id", "quotation_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    quotation_number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    converted_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    converted_invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    emailed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SalesQuotationItem(Base):
    __tablename__ = "sales_quotation_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    quotation_id: Mapped[str] = mapped_column(ForeignKey("sales_quotations.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    discount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (UniqueConstraint("tenant_id", "order_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    quotation_id: Mapped[str | None] = mapped_column(ForeignKey("sales_quotations.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id"), nullable=True, index=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    converted_invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StockReservation(Base):
    """Soft allocation against warehouse stock for confirmed sales orders."""

    __tablename__ = "stock_reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    sales_order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    sales_order_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales_order_items.id"), nullable=True, index=True
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    # active | released | consumed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    sales_order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    discount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class SalesReturn(Base):
    __tablename__ = "sales_returns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "return_number"),
        UniqueConstraint("tenant_id", "credit_note_number", name="uq_sales_returns_tenant_credit_note"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    return_number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    sales_invoice_id: Mapped[str] = mapped_column(ForeignKey("sales_invoices.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    reason: Mapped[str] = mapped_column(String(80), default="other")
    restock: Mapped[bool] = mapped_column(Boolean, default=True)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    credit_note_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    settlement_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # adjust = leave as customer credit; refund = cash/bank payout for excess over open AR
    refund_payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    refund_liquid_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    refunded_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SalesReturnItem(Base):
    __tablename__ = "sales_return_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    sales_return_id: Mapped[str] = mapped_column(ForeignKey("sales_returns.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    condition: Mapped[str] = mapped_column(String(40), default="sellable")


class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"
    __table_args__ = (UniqueConstraint("tenant_id", "return_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    return_number: Mapped[str] = mapped_column(String(50), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    goods_receipt_id: Mapped[str] = mapped_column(ForeignKey("goods_receipts.id"), index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # draft -> posted | cancelled
    reason: Mapped[str] = mapped_column(String(80), default="other")
    debit_note_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseReturnItem(Base):
    __tablename__ = "purchase_return_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_return_id: Mapped[str] = mapped_column(ForeignKey("purchase_returns.id"), index=True)
    goods_receipt_item_id: Mapped[str] = mapped_column(ForeignKey("goods_receipt_items.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class PurchaseInvoice(Base):
    __tablename__ = "purchase_invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    purchase_order_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True, index=True)
    goods_receipt_id: Mapped[str | None] = mapped_column(ForeignKey("goods_receipts.id"), nullable=True, index=True)
    supplier_invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # draft -> unpaid -> partial/paid | cancelled; overdue derived when past due
    invoice_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    # Buyer self-assessed VAT (not charged by supplier / not in AP total).
    reverse_charge_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_reverse_charge: Mapped[bool] = mapped_column(Boolean, default=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="")
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 8), default=1)
    # True when approve posted AP (manual invoices). False when GRN already recognized AP.
    ap_posted: Mapped[bool] = mapped_column(Boolean, default=False)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseInvoiceItem(Base):
    __tablename__ = "purchase_invoice_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_invoice_id: Mapped[str] = mapped_column(ForeignKey("purchase_invoices.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    discount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
