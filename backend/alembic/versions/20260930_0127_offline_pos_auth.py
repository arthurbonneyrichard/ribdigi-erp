"""Tenant offline POS auth hours + offline sync audit table.

Revision ID: 20260930_0127
Revises: 20260930_0126

Default offline window is 168 hours (7 days), matching refresh-token policy.
Configurable per tenant; not a client hardcode. IF NOT EXISTS throughout.
"""

from __future__ import annotations

from alembic import op

revision = "20260930_0127"
down_revision = "20260930_0126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS offline_auth_hours "
        "INTEGER NOT NULL DEFAULT 168"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS offline_sync_events (
            id VARCHAR(36) PRIMARY KEY,
            tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
            user_id VARCHAR(36) REFERENCES users(id),
            device_id VARCHAR(64),
            client_request_id VARCHAR(64),
            sale_id VARCHAR(36) REFERENCES transactions(id),
            store_id VARCHAR(36) REFERENCES stores(id),
            offline_created_at TIMESTAMP WITHOUT TIME ZONE,
            result VARCHAR(40) NOT NULL DEFAULT 'pending',
            conflict_code VARCHAR(80),
            details JSON,
            created_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_offline_sync_events_tenant_id "
        "ON offline_sync_events (tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_offline_sync_events_user_id "
        "ON offline_sync_events (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_offline_sync_events_client_request_id "
        "ON offline_sync_events (client_request_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_offline_sync_events_result "
        "ON offline_sync_events (result)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_offline_sync_events_created_at "
        "ON offline_sync_events (created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_offline_sync_events_created_at")
    op.execute("DROP INDEX IF EXISTS ix_offline_sync_events_result")
    op.execute("DROP INDEX IF EXISTS ix_offline_sync_events_client_request_id")
    op.execute("DROP INDEX IF EXISTS ix_offline_sync_events_user_id")
    op.execute("DROP INDEX IF EXISTS ix_offline_sync_events_tenant_id")
    op.execute("DROP TABLE IF EXISTS offline_sync_events")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS offline_auth_hours")
