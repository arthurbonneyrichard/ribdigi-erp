"""ADR-002 paid billing scaffold tables (PARTIAL — Complete still MISSING).

Revision ID: 20260914_0114
Revises: 20260914_0113
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0114"
down_revision = "20260914_0113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_billing_customers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="stripe"),
        sa.Column("provider_customer_id", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            name="uq_tenant_billing_customers_tenant_provider",
        ),
    )
    op.create_index(
        "ix_tenant_billing_customers_tenant_id",
        "tenant_billing_customers",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tenant_billing_customers_provider_customer_id",
        "tenant_billing_customers",
        ["provider_customer_id"],
    )

    op.create_table(
        "tenant_billing_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "billing_customer_id",
            sa.String(length=36),
            sa.ForeignKey("tenant_billing_customers.id"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="stripe"),
        sa.Column("provider_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("plan_code", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="incomplete"),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_status", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_tenant_billing_subscriptions_provider_sub",
        ),
    )
    op.create_index(
        "ix_tenant_billing_subscriptions_tenant_id",
        "tenant_billing_subscriptions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tenant_billing_subscriptions_billing_customer_id",
        "tenant_billing_subscriptions",
        ["billing_customer_id"],
    )
    op.create_index(
        "ix_tenant_billing_subscriptions_status",
        "tenant_billing_subscriptions",
        ["status"],
    )

    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="stripe"),
        sa.Column("provider_event_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processing_status", sa.String(length=40), nullable=False, server_default="received"),
        sa.Column("processing_note", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_billing_webhook_events_provider_event",
        ),
    )
    op.create_index(
        "ix_billing_webhook_events_tenant_id",
        "billing_webhook_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_billing_webhook_events_event_type",
        "billing_webhook_events",
        ["event_type"],
    )
    op.create_index(
        "ix_billing_webhook_events_processing_status",
        "billing_webhook_events",
        ["processing_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_billing_webhook_events_processing_status", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_event_type", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_tenant_id", table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")
    op.drop_index("ix_tenant_billing_subscriptions_status", table_name="tenant_billing_subscriptions")
    op.drop_index(
        "ix_tenant_billing_subscriptions_billing_customer_id",
        table_name="tenant_billing_subscriptions",
    )
    op.drop_index("ix_tenant_billing_subscriptions_tenant_id", table_name="tenant_billing_subscriptions")
    op.drop_table("tenant_billing_subscriptions")
    op.drop_index(
        "ix_tenant_billing_customers_provider_customer_id",
        table_name="tenant_billing_customers",
    )
    op.drop_index("ix_tenant_billing_customers_tenant_id", table_name="tenant_billing_customers")
    op.drop_table("tenant_billing_customers")
