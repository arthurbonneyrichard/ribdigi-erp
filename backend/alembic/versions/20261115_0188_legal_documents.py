"""Editable legal pages: every saved version of privacy, terms, refunds and cookies.

Revision ID: 20261115_0188
Revises: 20261115_0187
Create Date: 2026-11-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_0188"
down_revision = "20261115_0187"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_document_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_by_name", sa.String(150), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("slug", "version", name="uq_legal_document_versions_slug_version"),
    )
    op.create_index("ix_legal_document_versions_slug", "legal_document_versions", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_legal_document_versions_slug", table_name="legal_document_versions")
    op.drop_table("legal_document_versions")
