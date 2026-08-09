"""Webhook endpoints and delivery log (Stage 6 W1)

Revision ID: 20260809_0079
Revises: 20260809_0078
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0079"
down_revision = "20260809_0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("secret_enc", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("last_delivery_at", sa.DateTime(), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "webhook_id",
            sa.String(length=36),
            sa.ForeignKey("webhook_endpoints.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("event", sa.String(length=80), nullable=False, index=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending", index=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")
