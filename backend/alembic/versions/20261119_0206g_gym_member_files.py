"""Gym member files: photo, ID, waiver, progress photos.

Revision ID: 20261119_0206g
Revises: 20261119_0205g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0206g"
down_revision = "20261119_0205g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gym_member_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("gym_members.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False, index=True),
        sa.Column("storage_key", sa.String(500), nullable=False), sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("gym_member_files")
