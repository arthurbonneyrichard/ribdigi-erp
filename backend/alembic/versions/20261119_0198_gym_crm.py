"""Gym CRM: leads, marketing consent, campaigns and their recipients.

Revision ID: 20261119_0198
Revises: 20261119_0197
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0198"
down_revision = "20261119_0197"
branch_labels = None
depends_on = None


def _fk(name, table, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable, index=True)


def upgrade() -> None:
    op.add_column("gym_members", sa.Column("marketing_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("gym_members", sa.Column("consent_at", sa.DateTime()))
    op.create_table(
        "gym_leads", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        sa.Column("full_name", sa.String(180), nullable=False), sa.Column("phone", sa.String(40), index=True), sa.Column("email", sa.String(255)),
        sa.Column("source", sa.String(30), nullable=False, server_default="walk_in", index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new", index=True),
        sa.Column("assigned_to", sa.String(36)), sa.Column("next_follow_up", sa.Date(), index=True), sa.Column("trial_ends_on", sa.Date()),
        sa.Column("notes", sa.Text()), sa.Column("marketing_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        _fk("member_id", "gym_members", True), _fk("referred_by_member_id", "gym_members", True),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_campaigns", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False), sa.Column("kind", sa.String(10), nullable=False, server_default="marketing"),
        sa.Column("subject", sa.String(200)), sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", index=True),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()), sa.Column("sent_at", sa.DateTime()),
    )
    op.create_table(
        "gym_campaign_recipients", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        _fk("campaign_id", "gym_campaigns"), _fk("member_id", "gym_members", True), _fk("lead_id", "gym_leads", True),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("detail", sa.String(300)), sa.Column("sent_at", sa.DateTime()),
        sa.UniqueConstraint("campaign_id", "address", name="uq_gym_campaign_address"),
    )


def downgrade() -> None:
    for t in ("gym_campaign_recipients", "gym_campaigns", "gym_leads"):
        op.drop_table(t)
    op.drop_column("gym_members", "consent_at")
    op.drop_column("gym_members", "marketing_consent")
