"""SaaS subscription plans, consent, invoices, and webhook events.

Revision ID: 20261006_0116
Revises: 20260920_0115
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa

revision = "20261006_0116"
down_revision = "20260920_0115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_billing_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("package_code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("trial_days", sa.Integer(), nullable=False),
        sa.Column("grace_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_platform_billing_plans_code", "platform_billing_plans", ["code"])
    op.create_index("ix_platform_billing_plans_package_code", "platform_billing_plans", ["package_code"])
    op.create_table(
        "tenant_billing_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("billing_status", sa.String(length=32), nullable=False),
        sa.Column("auto_renew", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("consent_version", sa.String(length=40), nullable=True),
        sa.Column("consent_at", sa.DateTime(), nullable=True),
        sa.Column("consent_user_id", sa.String(length=36), nullable=True),
        sa.Column("consent_plan_id", sa.String(length=36), nullable=True),
        sa.Column("consent_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("consent_currency", sa.String(length=3), nullable=True),
        sa.Column("consent_interval", sa.String(length=16), nullable=True),
        sa.Column("gateway_provider", sa.String(length=32), nullable=True),
        sa.Column("gateway_customer_ref", sa.String(length=120), nullable=True),
        sa.Column("gateway_authorization_ref", sa.String(length=160), nullable=True),
        sa.Column("paid_through", sa.DateTime(), nullable=True),
        sa.Column("next_renewal_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(), nullable=True),
        sa.Column("last_notice_key", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["platform_billing_plans.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index("ix_tenant_billing_accounts_tenant_id", "tenant_billing_accounts", ["tenant_id"])
    op.create_table(
        "tenant_billing_invoices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("gateway_reference", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["tenant_billing_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_tenant_billing_invoice_key"),
    )
    op.create_index("ix_tenant_billing_invoices_tenant_id", "tenant_billing_invoices", ["tenant_id"])
    op.create_table(
        "tenant_billing_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("failure_reason", sa.String(length=200), nullable=True),
        sa.Column("gateway_reference", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["tenant_billing_invoices.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id", "attempt_number", name="uq_tenant_billing_attempt"),
    )
    op.create_index("ix_tenant_billing_attempts_invoice_id", "tenant_billing_attempts", ["invoice_id"])
    op.create_table(
        "tenant_billing_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("gateway_event_id", sa.String(length=160), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("invoice_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway_event_id"),
    )
    op.create_index("ix_tenant_billing_events_gateway_event_id", "tenant_billing_events", ["gateway_event_id"])


def downgrade() -> None:
    op.drop_table("tenant_billing_events")
    op.drop_table("tenant_billing_attempts")
    op.drop_table("tenant_billing_invoices")
    op.drop_table("tenant_billing_accounts")
    op.drop_table("platform_billing_plans")
