"""Support tickets, conversation, attachments, outbox, and recipients.

Revision ID: 20261011_0137
Revises: 20261008_0136
Create Date: 2026-10-11

Single head after 20261008_0136. Does not stamp or create_all.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "20261011_0137"
down_revision = "20261008_0136"
branch_labels = None
depends_on = None

_DEFAULT_RECIPIENT_ID = "3f1c8a2e-6b47-4d9a-8e15-0c4a9b7d2e61"


def upgrade() -> None:
    op.create_table(
        "support_ticket_sequences",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("year"),
    )
    op.create_table(
        "support_notification_recipients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_test_status", sa.String(length=20), nullable=True),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_test_error", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(
        "ix_support_notification_recipients_email",
        "support_notification_recipients",
        ["email"],
    )
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reference", sa.String(length=20), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_user_id", sa.String(length=36), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=36), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference", name="uq_support_tickets_reference"),
    )
    op.create_index("ix_support_tickets_tenant_id", "support_tickets", ["tenant_id"])
    op.create_index("ix_support_tickets_created_by", "support_tickets", ["created_by"])
    op.create_index("ix_support_tickets_category", "support_tickets", ["category"])
    op.create_index("ix_support_tickets_priority", "support_tickets", ["priority"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
    op.create_index("ix_support_tickets_assignee_user_id", "support_tickets", ["assignee_user_id"])
    op.create_index("ix_support_tickets_tenant_status", "support_tickets", ["tenant_id", "status"])
    op.create_index("ix_support_tickets_created_at", "support_tickets", ["created_at"])
    op.create_table(
        "support_ticket_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("author_user_id", sa.String(length=36), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_ticket_messages_tenant_id", "support_ticket_messages", ["tenant_id"])
    op.create_index("ix_support_ticket_messages_ticket_id", "support_ticket_messages", ["ticket_id"])
    op.create_index("ix_support_messages_ticket", "support_ticket_messages", ["ticket_id", "created_at"])
    op.create_table(
        "support_ticket_attachments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["support_ticket_messages.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_ticket_attachments_tenant_id", "support_ticket_attachments", ["tenant_id"])
    op.create_index("ix_support_ticket_attachments_ticket_id", "support_ticket_attachments", ["ticket_id"])
    op.create_table(
        "support_ticket_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_ticket_events_tenant_id", "support_ticket_events", ["tenant_id"])
    op.create_index("ix_support_ticket_events_ticket_id", "support_ticket_events", ["ticket_id"])
    op.create_index("ix_support_events_ticket", "support_ticket_events", ["ticket_id", "created_at"])
    op.create_table(
        "support_email_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("link_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_support_email_outbox_idempotency"),
    )
    op.create_index("ix_support_email_outbox_tenant_id", "support_email_outbox", ["tenant_id"])
    op.create_index("ix_support_email_outbox_ticket_id", "support_email_outbox", ["ticket_id"])
    op.create_index("ix_support_email_outbox_status", "support_email_outbox", ["status"])
    op.create_index("ix_support_email_outbox_recipient", "support_email_outbox", ["recipient_email"])

    now = datetime.utcnow()
    op.execute(
        sa.text(
            "INSERT INTO support_notification_recipients "
            "(id, email, is_active, created_at, updated_at) "
            "VALUES (:id, :email, :active, :now, :now)"
        ).bindparams(
            id=_DEFAULT_RECIPIENT_ID,
            email="support@ribdigihouse.com",
            active=True,
            now=now,
        )
    )


def downgrade() -> None:
    op.drop_index("ix_support_email_outbox_recipient", table_name="support_email_outbox")
    op.drop_index("ix_support_email_outbox_status", table_name="support_email_outbox")
    op.drop_index("ix_support_email_outbox_ticket_id", table_name="support_email_outbox")
    op.drop_index("ix_support_email_outbox_tenant_id", table_name="support_email_outbox")
    op.drop_table("support_email_outbox")
    op.drop_index("ix_support_events_ticket", table_name="support_ticket_events")
    op.drop_index("ix_support_ticket_events_ticket_id", table_name="support_ticket_events")
    op.drop_index("ix_support_ticket_events_tenant_id", table_name="support_ticket_events")
    op.drop_table("support_ticket_events")
    op.drop_index("ix_support_ticket_attachments_ticket_id", table_name="support_ticket_attachments")
    op.drop_index("ix_support_ticket_attachments_tenant_id", table_name="support_ticket_attachments")
    op.drop_table("support_ticket_attachments")
    op.drop_index("ix_support_messages_ticket", table_name="support_ticket_messages")
    op.drop_index("ix_support_ticket_messages_ticket_id", table_name="support_ticket_messages")
    op.drop_index("ix_support_ticket_messages_tenant_id", table_name="support_ticket_messages")
    op.drop_table("support_ticket_messages")
    op.drop_index("ix_support_tickets_created_at", table_name="support_tickets")
    op.drop_index("ix_support_tickets_tenant_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_assignee_user_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_priority", table_name="support_tickets")
    op.drop_index("ix_support_tickets_category", table_name="support_tickets")
    op.drop_index("ix_support_tickets_created_by", table_name="support_tickets")
    op.drop_index("ix_support_tickets_tenant_id", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_index("ix_support_notification_recipients_email", table_name="support_notification_recipients")
    op.drop_table("support_notification_recipients")
    op.drop_table("support_ticket_sequences")
