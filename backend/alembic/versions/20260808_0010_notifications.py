"""notification categories and preferences

Revision ID: 20260808_0010
Revises: 20260808_0009
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0010"
down_revision = "20260808_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("category", sa.String(length=40), nullable=False, server_default="system"),
    )
    op.add_column("notifications", sa.Column("entity_type", sa.String(length=50), nullable=True))
    op.add_column("notifications", sa.Column("entity_id", sa.String(length=36), nullable=True))
    op.create_index("ix_notifications_category", "notifications", ["category"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id"),
    )
    op.create_index("ix_notification_preferences_user", "notification_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_category", table_name="notifications")
    op.drop_column("notifications", "entity_id")
    op.drop_column("notifications", "entity_type")
    op.drop_column("notifications", "category")
