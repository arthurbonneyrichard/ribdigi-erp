"""HRM 360 feedback on reviews.

Revision ID: 20261113_0176
Revises: 20261113_0175
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0176"
down_revision = "20261113_0175"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hrm_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("hrm_reviews.id"), nullable=False, index=True),
        sa.Column("from_employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="asked"),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("improve", sa.Text(), nullable=True),
        sa.Column("asked_by", sa.String(36), nullable=True),
        sa.Column("given_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("review_id", "from_employee_id", name="uq_hrm_feedback_once"),
    )


def downgrade() -> None:
    op.drop_table("hrm_feedback")
