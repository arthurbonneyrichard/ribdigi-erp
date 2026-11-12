"""HRM people work: recruitment, reviews, training, contracts, cases, assets, claims, notices.

Revision ID: 20261113_0167
Revises: 20261113_0166
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0167"
down_revision = "20261113_0166"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _employee():
    return sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True)


def _created():
    return [sa.Column("created_by", sa.String(36), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=True)]


TABLES = {
    "hrm_vacancies": lambda: [
        _id(), _tenant(),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("openings", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("closes_on", sa.Date(), nullable=True),
        *_created(),
    ],
    "hrm_candidates": lambda: [
        _id(), _tenant(),
        sa.Column("vacancy_id", sa.String(36), sa.ForeignKey("hrm_vacancies.id"), nullable=False, index=True),
        sa.Column("full_name", sa.String(180), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("stage", sa.String(16), nullable=False, server_default="applied", index=True),
        sa.Column("interview_at", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("offered_basic", sa.Numeric(14, 2), nullable=True),
        sa.Column("employee_id", sa.String(36), nullable=True),
        *_created(),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    ],
    "hrm_reviews": lambda: [
        _id(), _tenant(), _employee(),
        sa.Column("cycle", sa.String(60), nullable=False),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("self_comment", sa.Text(), nullable=True),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.Column("overall", sa.Numeric(4, 2), nullable=True),
        sa.Column("reviewer_id", sa.String(36), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_created(),
    ],
    "hrm_trainings": lambda: [
        _id(), _tenant(),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(160), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_months", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    ],
    "hrm_training_records": lambda: [
        _id(), _tenant(),
        sa.Column("training_id", sa.String(36), sa.ForeignKey("hrm_trainings.id"), nullable=False, index=True),
        _employee(),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True, index=True),
        sa.Column("result", sa.String(120), nullable=True),
        sa.Column("certificate_ref", sa.String(120), nullable=True),
        *_created(),
    ],
    "hrm_contracts": lambda: [
        _id(), _tenant(), _employee(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True, index=True),
        sa.Column("probation_ends_on", sa.Date(), nullable=True, index=True),
        sa.Column("confirmed_on", sa.Date(), nullable=True),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        *_created(),
    ],
    "hrm_cases": lambda: [
        _id(), _tenant(),
        sa.Column("case_number", sa.String(40), nullable=False),
        _employee(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(160), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("hearing_at", sa.DateTime(), nullable=True),
        sa.Column("outcome", sa.String(24), nullable=True),
        sa.Column("outcome_note", sa.Text(), nullable=True),
        sa.Column("employee_response", sa.Text(), nullable=True),
        sa.Column("raised_by", sa.String(36), nullable=True),
        sa.Column("closed_by", sa.String(36), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "case_number", name="uq_hrm_case_number"),
    ],
    "hrm_assets": lambda: [
        _id(), _tenant(), _employee(),
        sa.Column("item", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False, server_default="other"),
        sa.Column("serial", sa.String(120), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("condition_out", sa.String(120), nullable=True),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.Column("condition_back", sa.String(120), nullable=True),
        *_created(),
    ],
    "hrm_claims": lambda: [
        _id(), _tenant(),
        sa.Column("claim_number", sa.String(40), nullable=False),
        _employee(),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("receipt_ref", sa.String(120), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
        sa.Column("decision_note", sa.String(255), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("paid_method", sa.String(20), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "claim_number", name="uq_hrm_claim_number"),
    ],
    "hrm_notices": lambda: [
        _id(), _tenant(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_created(),
    ],
}


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    for name, columns in TABLES.items():
        if name not in have:
            op.create_table(name, *columns())


def downgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    for name in reversed(list(TABLES)):
        if name in have:
            op.drop_table(name)
