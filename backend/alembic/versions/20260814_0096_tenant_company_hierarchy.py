"""ADR-490 — Tenant → Company hierarchy tables + company_id backfill.

Revision ID: 20260814_0096
Revises: 20260813_0095
Create Date: 2026-08-14
"""

from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa

revision = "20260814_0096"
down_revision = "20260813_0095"
branch_labels = None
depends_on = None

BUSINESS_TYPES = [
    ("supermarket", "Supermarket", 10),
    ("mini_mart", "Mini Mart", 20),
    ("pharmacy", "Pharmacy", 30),
    ("restaurant", "Restaurant", 40),
    ("wholesale", "Wholesale", 50),
    ("distribution", "Distribution", 60),
    ("retail", "Retail", 70),
    ("bakery", "Bakery", 80),
    ("hardware", "Hardware", 90),
    ("electronics", "Electronics", 100),
    ("fashion", "Fashion", 110),
    ("general_trading", "General Trading", 120),
    ("other", "Other", 999),
]

# Operational tables that receive company_id (must match models.py).
COMPANY_SCOPED_TABLES = [
    "branches",
    "departments",
    "stores",
    "warehouses",
    "warehouse_stocks",
    "product_categories",
    "brands",
    "units_of_measure",
    "products",
    "product_variants",
    "product_images",
    "product_batches",
    "stock_movements",
    "stock_reservations",
    "customer_groups",
    "parties",
    "party_contacts",
    "transactions",
    "expense_categories",
    "expenses",
    "expense_approval_actions",
    "recurring_expenses",
    "accounts",
    "bank_account_connections",
    "bank_statements",
    "bank_clearing_groups",
    "bank_clearing_book_links",
    "bank_statement_lines",
    "exchange_rates",
    "tax_rates",
    "notifications",
    "ai_queries",
    "ai_report_templates",
    "audit_logs",
    "audit_cold_archives",
    "purchase_requests",
    "purchase_request_approval_actions",
    "purchase_request_items",
    "purchase_orders",
    "purchase_order_items",
    "purchase_order_amendments",
    "goods_receipts",
    "goods_receipt_items",
    "sales_invoices",
    "sales_invoice_items",
    "customer_payments",
    "supplier_payments",
    "cheques",
    "pos_sessions",
    "pos_payments",
    "journal_entries",
    "journal_entry_lines",
    "stock_transfers",
    "stock_transfer_items",
    "stock_counts",
    "stock_count_items",
    "report_schedules",
    "sales_quotations",
    "sales_quotation_items",
    "sales_orders",
    "sales_order_items",
    "sales_returns",
    "sales_return_items",
    "purchase_returns",
    "purchase_return_items",
    "purchase_invoices",
    "purchase_invoice_items",
    "pos_held_carts",
]


def _uid() -> str:
    return str(uuid.uuid4())


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    op.add_column("tenants", sa.Column("max_companies", sa.Integer(), server_default="1", nullable=False))
    op.add_column("tenants", sa.Column("max_users", sa.Integer(), server_default="25", nullable=False))
    op.add_column("tenants", sa.Column("max_branches", sa.Integer(), server_default="5", nullable=False))
    op.add_column("tenants", sa.Column("max_stores", sa.Integer(), server_default="5", nullable=False))
    op.add_column("tenants", sa.Column("max_warehouses", sa.Integer(), server_default="5", nullable=False))

    op.create_table(
        "business_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_business_types_code", "business_types", ["code"], unique=True)

    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False, server_default="MAIN"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("business_type_id", sa.String(36), sa.ForeignKey("business_types.id"), nullable=True),
        sa.Column("industry", sa.String(50), nullable=False, server_default="retail"),
        sa.Column("legal_name", sa.String(200), nullable=True),
        sa.Column("registration_number", sa.String(80), nullable=True),
        sa.Column("tax_registration_number", sa.String(40), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GHS"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Africa/Accra"),
        sa.Column("fiscal_year_start", sa.String(5), nullable=False, server_default="01-01"),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "code"),
    )
    op.create_index("ix_companies_tenant_id", "companies", ["tenant_id"])
    op.create_index("ix_companies_business_type_id", "companies", ["business_type_id"])

    op.create_table(
        "user_company_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="cashier"),
        sa.Column("permissions", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "user_id", "company_id"),
    )
    op.create_index("ix_user_company_memberships_tenant_id", "user_company_memberships", ["tenant_id"])
    op.create_index("ix_user_company_memberships_user_id", "user_company_memberships", ["user_id"])
    op.create_index("ix_user_company_memberships_company_id", "user_company_memberships", ["company_id"])

    # Seed business types
    bt_ids = {}
    for code, label, sort_order in BUSINESS_TYPES:
        bt_id = _uid()
        bt_ids[code] = bt_id
        op.execute(
            sa.text(
                "INSERT INTO business_types (id, code, label, is_active, sort_order, created_at) "
                "VALUES (:id, :code, :label, true, :sort_order, CURRENT_TIMESTAMP)"
            ).bindparams(id=bt_id, code=code, label=label, sort_order=sort_order)
        )

    # Backfill one default company per tenant
    tenants = op.get_bind().execute(
        sa.text(
            "SELECT id, company_name, industry, legal_name, registration_number, "
            "tax_registration_number, phone, email, website, address, currency, timezone, "
            "fiscal_year_start, logo_url FROM tenants"
        )
    ).fetchall()
    company_by_tenant: dict[str, str] = {}
    for row in tenants:
        tid = row[0]
        cid = _uid()
        company_by_tenant[tid] = cid
        industry = (row[2] or "retail").lower()
        bt = bt_ids.get(industry) or bt_ids.get("retail") or bt_ids.get("other")
        op.execute(
            sa.text(
                "INSERT INTO companies (id, tenant_id, code, name, business_type_id, industry, "
                "legal_name, registration_number, tax_registration_number, phone, email, website, "
                "address, currency, timezone, fiscal_year_start, logo_url, is_active, is_default, "
                "created_at, updated_at) VALUES ("
                ":id, :tenant_id, 'MAIN', :name, :bt, :industry, :legal_name, :reg, :tax, :phone, "
                ":email, :website, :address, :currency, :timezone, :fys, :logo, true, true, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ).bindparams(
                id=cid,
                tenant_id=tid,
                name=row[1] or "Company",
                bt=bt,
                industry=row[2] or "retail",
                legal_name=row[3],
                reg=row[4],
                tax=row[5],
                phone=row[6],
                email=row[7],
                website=row[8],
                address=row[9],
                currency=row[10] or "GHS",
                timezone=row[11] or "Africa/Accra",
                fys=row[12] or "01-01",
                logo=row[13],
            )
        )

    # Membership for every user on default company
    users = op.get_bind().execute(sa.text("SELECT id, tenant_id, role, permissions FROM users")).fetchall()
    for u in users:
        uid, tid, role, perms = u[0], u[1], u[2] or "cashier", u[3]
        cid = company_by_tenant.get(tid)
        if not cid:
            continue
        op.execute(
            sa.text(
                "INSERT INTO user_company_memberships "
                "(id, tenant_id, user_id, company_id, role, permissions, is_active, created_at) "
                "VALUES (:id, :tenant_id, :user_id, :company_id, :role, :permissions, true, CURRENT_TIMESTAMP)"
            ).bindparams(
                id=_uid(),
                tenant_id=tid,
                user_id=uid,
                company_id=cid,
                role=role,
                permissions=perms,
            )
        )

    # Add company_id columns + backfill
    for table in COMPANY_SCOPED_TABLES:
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "company_id" in cols:
            continue
        if "tenant_id" not in cols:
            continue
        op.add_column(table, sa.Column("company_id", sa.String(36), nullable=True))
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])
        # Backfill from tenant's default company
        op.execute(
            sa.text(
                f"UPDATE {table} SET company_id = ("
                f"SELECT c.id FROM companies c WHERE c.tenant_id = {table}.tenant_id "
                f"AND c.is_default = true LIMIT 1)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table in reversed(COMPANY_SCOPED_TABLES):
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "company_id" not in cols:
            continue
        try:
            op.drop_index(f"ix_{table}_company_id", table_name=table)
        except Exception:
            pass
        op.drop_column(table, "company_id")

    op.drop_table("user_company_memberships")
    op.drop_table("companies")
    op.drop_table("business_types")
    for col in ("max_warehouses", "max_stores", "max_branches", "max_users", "max_companies"):
        op.drop_column("tenants", col)
