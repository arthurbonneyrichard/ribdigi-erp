"""HRM documents on staff files and company policies, with typed-name acceptance.

Revision ID: 20261113_0174
Revises: 20261113_0173
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0174"
down_revision = "20261113_0173"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hrm_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="other"),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("needs_ack", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidential", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("uploaded_by", sa.String(36), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "hrm_document_acks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("hrm_documents.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("typed_name", sa.String(150), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.UniqueConstraint("document_id", "employee_id", name="uq_hrm_document_ack"),
    )


def downgrade() -> None:
    op.drop_table("hrm_document_acks")
    op.drop_table("hrm_documents")
