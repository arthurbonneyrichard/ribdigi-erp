"""HRM: training budgets and cost, interview panels with scores.

Revision ID: 20261119_0191
Revises: 20261119_0190
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0191"
down_revision = "20261119_0190"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def upgrade() -> None:
    op.add_column("hrm_training_records", sa.Column("cost", sa.Numeric(14, 2), nullable=True))
    op.create_table(
        "hrm_training_budgets", _id(), _tenant(),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "year", name="uq_hrm_training_budget_year"),
    )
    op.create_table(
        "hrm_interviews", _id(), _tenant(),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("hrm_candidates.id"), nullable=False, index=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("panel", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="scheduled", index=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "hrm_interview_scores", _id(), _tenant(),
        sa.Column("interview_id", sa.String(36), sa.ForeignKey("hrm_interviews.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("interview_id", "employee_id", name="uq_hrm_interview_score"),
    )


def downgrade() -> None:
    op.drop_table("hrm_interview_scores")
    op.drop_table("hrm_interviews")
    op.drop_table("hrm_training_budgets")
    op.drop_column("hrm_training_records", "cost")
