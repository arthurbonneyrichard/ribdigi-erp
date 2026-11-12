"""Package prices per industry and the software owner's VAT on subscription invoices.

Revision ID: 20261112_0161
Revises: 20261112_0160
Create Date: 2026-11-12
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "20261112_0161"
down_revision = "20261112_0160"
branch_labels = None
depends_on = None

# Starting monthly prices in GHS per industry: (starter, professional, enterprise).
# Yearly = 10 x monthly. Keep in step with saas_billing.INDUSTRY_MONTHLY_PRICES.
INDUSTRY_MONTHLY_PRICES = {
    "hotel": ("349.00", "799.00", "1499.00"),
    "restaurant": ("249.00", "599.00", "1199.00"),
    "fmcg": ("299.00", "699.00", "1399.00"),
    "bakery": ("179.00", "449.00", "899.00"),
    "gym": ("149.00", "349.00", "699.00"),
    "hrm": ("149.00", "349.00", "699.00"),
}


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "industry" not in _cols("platform_billing_plans"):
        op.add_column("platform_billing_plans", sa.Column("industry", sa.String(40), nullable=True))
        op.create_index("ix_platform_billing_plans_industry", "platform_billing_plans", ["industry"])
    if "consent_tax_rate" not in _cols("tenant_billing_accounts"):
        op.add_column(
            "tenant_billing_accounts", sa.Column("consent_tax_rate", sa.Numeric(6, 3), nullable=True)
        )
    inv = _cols("tenant_billing_invoices")
    for name, col in (
        ("net_amount", sa.Numeric(14, 2)),
        ("tax_amount", sa.Numeric(14, 2)),
        ("tax_rate", sa.Numeric(6, 3)),
        ("tax_label", sa.String(40)),
    ):
        if name not in inv:
            op.add_column("tenant_billing_invoices", sa.Column(name, col, nullable=True))
    if "platform_billing_tax" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "platform_billing_tax",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("rate", sa.Numeric(6, 3), nullable=False, server_default="0"),
            sa.Column("label", sa.String(40), nullable=False, server_default="VAT"),
            sa.Column("registration_number", sa.String(40), nullable=True),
            sa.Column("prices_include_tax", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_by", sa.String(36), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    # Add the industry plans only where the code is missing, so a price the owner
    # already set is kept. An empty catalog is seeded by the app on first use.
    have = {row[0] for row in bind.execute(sa.text("SELECT code FROM platform_billing_plans"))}
    if not have:
        return
    plans = sa.table(
        "platform_billing_plans",
        sa.column("id", sa.String),
        sa.column("code", sa.String),
        sa.column("package_code", sa.String),
        sa.column("industry", sa.String),
        sa.column("name", sa.String),
        sa.column("interval", sa.String),
        sa.column("amount", sa.Numeric),
        sa.column("currency", sa.String),
        sa.column("trial_days", sa.Integer),
        sa.column("grace_days", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    now = datetime.utcnow()
    rows = []
    for industry, prices in INDUSTRY_MONTHLY_PRICES.items():
        label = "FMCG" if industry == "fmcg" else ("HRM" if industry == "hrm" else industry.title())
        for package_code, monthly in zip(("starter", "professional", "enterprise"), prices):
            for interval, amount in (("month", monthly), ("year", f"{float(monthly) * 10:.2f}")):
                code = f"{package_code}-{interval}-{industry}"
                if code in have:
                    continue
                word = "monthly" if interval == "month" else "yearly"
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "code": code,
                        "package_code": package_code,
                        "industry": industry,
                        "name": f"{package_code.title()} {word} ({label})",
                        "interval": interval,
                        "amount": amount,
                        "currency": "GHS",
                        "trial_days": 14,
                        "grace_days": 7,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
    if rows:
        op.bulk_insert(plans, rows)


def downgrade() -> None:
    if "platform_billing_tax" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("platform_billing_tax")
    inv = _cols("tenant_billing_invoices")
    for name in ("tax_label", "tax_rate", "tax_amount", "net_amount"):
        if name in inv:
            op.drop_column("tenant_billing_invoices", name)
    if "consent_tax_rate" in _cols("tenant_billing_accounts"):
        op.drop_column("tenant_billing_accounts", "consent_tax_rate")
    if "industry" in _cols("platform_billing_plans"):
        op.drop_index("ix_platform_billing_plans_industry", table_name="platform_billing_plans")
        op.drop_column("platform_billing_plans", "industry")
