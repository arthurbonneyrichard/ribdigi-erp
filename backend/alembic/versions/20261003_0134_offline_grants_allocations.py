"""Server-issued offline POS grants, per-device stock allocations, conflict resolution.

Revision ID: 20261003_0134
Revises: 20261003_0133

Offline grants are device-bound and expire; expiry blocks new offline sales but
never invalidates sales recorded inside the window. Allocations reserve a slice
of store stock per device so two offline tills cannot sell the same units.
Sync events gain a resolution trail so conflicts are resolved, never deleted.
Quotations gain a client_request_id so offline-captured quotes submit once.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261003_0134"
down_revision = "20261003_0133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "pos_devices" in tables:
        cols = {c["name"] for c in insp.get_columns("pos_devices")}
        if "offline_blocked" not in cols:
            op.add_column(
                "pos_devices",
                sa.Column("offline_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
            )

    if "offline_grants" not in tables:
        op.create_table(
            "offline_grants",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("device_id", sa.String(length=64), nullable=False),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
            sa.Column("warehouse_id", sa.String(length=36), nullable=True),
            sa.Column("industry", sa.String(length=40), nullable=True),
            sa.Column("allowed_actions", sa.JSON(), nullable=True),
            sa.Column("can_override_allocation", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("issued_at", sa.DateTime(), nullable=False),
            sa.Column("valid_until", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("revoke_reason", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_offline_grants_tenant_id", "offline_grants", ["tenant_id"])
        op.create_index("ix_offline_grants_user_id", "offline_grants", ["user_id"])
        op.create_index("ix_offline_grants_device_id", "offline_grants", ["device_id"])
        op.create_index("ix_offline_grants_store_id", "offline_grants", ["store_id"])
        op.create_index("ix_offline_grants_issued_at", "offline_grants", ["issued_at"])
        op.create_index("ix_offline_grants_valid_until", "offline_grants", ["valid_until"])

    if "offline_stock_allocations" not in tables:
        op.create_table(
            "offline_stock_allocations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("grant_id", sa.String(length=36), sa.ForeignKey("offline_grants.id"), nullable=False),
            sa.Column("device_id", sa.String(length=64), nullable=False),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
            sa.Column("warehouse_id", sa.String(length=36), nullable=True),
            sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("allocated_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
            sa.Column("sold_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
            sa.Column("released_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("grant_id", "product_id", name="uq_offline_alloc_grant_product"),
        )
        op.create_index("ix_offline_stock_allocations_tenant_id", "offline_stock_allocations", ["tenant_id"])
        op.create_index("ix_offline_stock_allocations_grant_id", "offline_stock_allocations", ["grant_id"])
        op.create_index("ix_offline_stock_allocations_device_id", "offline_stock_allocations", ["device_id"])
        op.create_index(
            "ix_offline_stock_allocations_warehouse_id", "offline_stock_allocations", ["warehouse_id"]
        )
        op.create_index(
            "ix_offline_stock_allocations_product_id", "offline_stock_allocations", ["product_id"]
        )

    if "offline_sync_events" in tables:
        cols = {c["name"] for c in insp.get_columns("offline_sync_events")}
        if "resolution" not in cols:
            op.add_column("offline_sync_events", sa.Column("resolution", sa.String(length=40), nullable=True))
        if "resolved_by" not in cols:
            op.add_column("offline_sync_events", sa.Column("resolved_by", sa.String(length=36), nullable=True))
        if "resolved_at" not in cols:
            op.add_column("offline_sync_events", sa.Column("resolved_at", sa.DateTime(), nullable=True))
        if "resolution_note" not in cols:
            op.add_column("offline_sync_events", sa.Column("resolution_note", sa.Text(), nullable=True))

    if "sales_quotations" in tables:
        cols = {c["name"] for c in insp.get_columns("sales_quotations")}
        if "client_request_id" not in cols:
            op.add_column(
                "sales_quotations",
                sa.Column("client_request_id", sa.String(length=64), nullable=True),
            )
            op.create_index(
                "ix_sales_quotations_client_request_id", "sales_quotations", ["client_request_id"]
            )
            op.create_index(
                "uq_sales_quotations_tenant_client_request",
                "sales_quotations",
                ["tenant_id", "client_request_id"],
                unique=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "sales_quotations" in tables:
        cols = {c["name"] for c in insp.get_columns("sales_quotations")}
        if "client_request_id" in cols:
            op.drop_index("uq_sales_quotations_tenant_client_request", table_name="sales_quotations")
            op.drop_index("ix_sales_quotations_client_request_id", table_name="sales_quotations")
            op.drop_column("sales_quotations", "client_request_id")
    if "offline_sync_events" in tables:
        cols = {c["name"] for c in insp.get_columns("offline_sync_events")}
        for name in ("resolution_note", "resolved_at", "resolved_by", "resolution"):
            if name in cols:
                op.drop_column("offline_sync_events", name)
    if "offline_stock_allocations" in tables:
        op.drop_table("offline_stock_allocations")
    if "offline_grants" in tables:
        op.drop_table("offline_grants")
    if "pos_devices" in tables:
        cols = {c["name"] for c in insp.get_columns("pos_devices")}
        if "offline_blocked" in cols:
            op.drop_column("pos_devices", "offline_blocked")
