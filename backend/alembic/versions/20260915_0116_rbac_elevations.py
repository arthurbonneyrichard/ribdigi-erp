"""RBAC elevation / break-glass grants table (MVP Complete for this slice).

Revision ID: 20260915_0116
Revises: 20260915_0115
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260915_0116"
down_revision = "20260915_0115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rbac_elevations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("granted_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_rbac_elevations_tenant_id", "rbac_elevations", ["tenant_id"])
    op.create_index("ix_rbac_elevations_user_id", "rbac_elevations", ["user_id"])
    op.create_index("ix_rbac_elevations_expires_at", "rbac_elevations", ["expires_at"])
    op.create_index("ix_rbac_elevations_granted_by", "rbac_elevations", ["granted_by"])


def downgrade() -> None:
    op.drop_index("ix_rbac_elevations_granted_by", table_name="rbac_elevations")
    op.drop_index("ix_rbac_elevations_expires_at", table_name="rbac_elevations")
    op.drop_index("ix_rbac_elevations_user_id", table_name="rbac_elevations")
    op.drop_index("ix_rbac_elevations_tenant_id", table_name="rbac_elevations")
    op.drop_table("rbac_elevations")
