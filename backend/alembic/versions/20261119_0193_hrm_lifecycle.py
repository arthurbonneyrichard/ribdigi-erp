"""HRM lifecycle: checklists, exit interviews, benefits, career events, OKRs, custom fields, succession.

Revision ID: 20261119_0193
Revises: 20261119_0192
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0193"
down_revision = "20261119_0192"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _emp(name="employee_id", nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=nullable, index=True)


def _created():
    return sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "hrm_checklist_tasks", _id(), _tenant(), _emp(),
        sa.Column("kind", sa.String(12), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("asset_id", sa.String(36), nullable=True),
        sa.Column("done_on", sa.Date(), nullable=True),
        sa.Column("done_by", sa.String(36), nullable=True),
        _created(),
    )
    op.create_table(
        "hrm_exit_interviews", _id(), _tenant(), _emp(),
        sa.Column("held_on", sa.Date(), nullable=False),
        sa.Column("reason_category", sa.String(24), nullable=False),
        sa.Column("would_return", sa.Boolean(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("held_by", sa.String(36), nullable=True),
        _created(),
        sa.UniqueConstraint("employee_id", name="uq_hrm_exit_interview_person"),
    )
    op.create_table(
        "hrm_benefits", _id(), _tenant(), _emp(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(160), nullable=True),
        sa.Column("policy_number", sa.String(80), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        _created(),
    )
    op.create_table(
        "hrm_career_events", _id(), _tenant(), _emp(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("from_job_title", sa.String(120), nullable=True),
        sa.Column("to_job_title", sa.String(120), nullable=True),
        sa.Column("from_department", sa.String(120), nullable=True),
        sa.Column("to_department", sa.String(120), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        _created(),
    )
    op.create_table(
        "hrm_objectives", _id(), _tenant(),
        sa.Column("kind", sa.String(12), nullable=False, server_default="objective"),
        sa.Column("level", sa.String(12), nullable=False, server_default="employee"),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("hrm_objectives.id"), nullable=True, index=True),
        _emp(nullable=True),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("period", sa.String(16), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(24), nullable=True),
        sa.Column("target", sa.Numeric(16, 2), nullable=True),
        sa.Column("current", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("created_by", sa.String(36), nullable=True),
        _created(),
    )
    op.create_table(
        "hrm_custom_fields", _id(), _tenant(),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False, server_default="text"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _created(),
        sa.UniqueConstraint("tenant_id", "label", name="uq_hrm_custom_field_label"),
    )
    op.create_table(
        "hrm_custom_values", _id(), _tenant(), _emp(),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("hrm_custom_fields.id"), nullable=False, index=True),
        sa.Column("value", sa.String(255), nullable=False),
        sa.UniqueConstraint("employee_id", "field_id", name="uq_hrm_custom_value"),
    )
    op.create_table(
        "hrm_succession", _id(), _tenant(),
        sa.Column("position", sa.String(160), nullable=False),
        _emp("incumbent_id", nullable=True),
        _emp("successor_id"),
        sa.Column("readiness", sa.String(12), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        _created(),
    )


def downgrade() -> None:
    for t in (
        "hrm_succession", "hrm_custom_values", "hrm_custom_fields", "hrm_objectives",
        "hrm_career_events", "hrm_benefits", "hrm_exit_interviews", "hrm_checklist_tasks",
    ):
        op.drop_table(t)
