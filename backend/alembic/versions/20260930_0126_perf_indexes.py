"""POS / product list indexes for tenant-scoped search and session lists.

Revision ID: 20260930_0126
Revises: 20260928_0125

Moved from colliding 20260816_0106 (page-speed indexes). Historical 0106 on
this lineage is 20260917_0106 (client_request_id); printer routing is 0125.
CREATE INDEX IF NOT EXISTS so a prior 0106 apply is a no-op.
"""

from __future__ import annotations

from alembic import op

revision = "20260930_0126"
down_revision = "20260928_0125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_products_tenant_id_is_active "
        "ON products (tenant_id, is_active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_auth_sessions_tenant_id_user_id_revoked_at "
        "ON auth_sessions (tenant_id, user_id, revoked_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_auth_sessions_tenant_id_user_id_revoked_at")
    op.execute("DROP INDEX IF EXISTS ix_products_tenant_id_is_active")
