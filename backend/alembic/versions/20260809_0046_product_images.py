"""Product image gallery

Revision ID: 20260809_0046
Revises: 20260809_0045
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0046"
down_revision = "20260809_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_images",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_product_images_tenant_id", "product_images", ["tenant_id"])
    op.create_index("ix_product_images_product_id", "product_images", ["product_id"])

    # Backfill primary gallery rows from existing products.image_url
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, tenant_id, image_url FROM products "
            "WHERE image_url IS NOT NULL AND image_url != ''"
        )
    ).fetchall()
    import uuid

    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO product_images "
                "(id, tenant_id, product_id, storage_key, content_type, sort_order, "
                "is_primary, original_filename, created_at) "
                "VALUES (:id, :tenant_id, :product_id, :storage_key, NULL, 0, true, NULL, CURRENT_TIMESTAMP)"
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": row.tenant_id if hasattr(row, "tenant_id") else row[1],
                "product_id": row.id if hasattr(row, "id") else row[0],
                "storage_key": row.image_url if hasattr(row, "image_url") else row[2],
            },
        )


def downgrade() -> None:
    op.drop_table("product_images")
