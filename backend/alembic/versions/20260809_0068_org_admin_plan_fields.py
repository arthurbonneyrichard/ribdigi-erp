"""Org admin fields, store hours, warehouse attrs, tenant plan/legal

Revision ID: 20260809_0068
Revises: 20260809_0067
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0068"
down_revision = "20260809_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("branches") as batch:
        batch.add_column(sa.Column("manager_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch.create_foreign_key("fk_branches_manager_id_users", "users", ["manager_id"], ["id"])

    with op.batch_alter_table("departments") as batch:
        batch.add_column(sa.Column("head_user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_departments_head_user_id_users", "users", ["head_user_id"], ["id"])

    with op.batch_alter_table("stores") as batch:
        batch.add_column(sa.Column("operating_hours", sa.JSON(), nullable=True))

    with op.batch_alter_table("warehouses") as batch:
        batch.add_column(sa.Column("warehouse_type", sa.String(length=40), nullable=False, server_default="retail"))
        batch.add_column(sa.Column("manager_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("address", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("capacity", sa.Numeric(14, 3), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")))
        batch.create_foreign_key("fk_warehouses_manager_id_users", "users", ["manager_id"], ["id"])

    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("plan_code", sa.String(length=40), nullable=False, server_default="trial"))
        batch.add_column(sa.Column("legal_name", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("registration_number", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("billing_address", sa.Text(), nullable=True))
        batch.add_column(sa.Column("shipping_address", sa.Text(), nullable=True))
        batch.add_column(sa.Column("warehouse_address", sa.Text(), nullable=True))
        batch.add_column(sa.Column("contact_person_name", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("contact_person_email", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("contact_person_phone", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("inactivity_timeout_minutes", sa.Integer(), nullable=False, server_default="30"))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("inactivity_timeout_minutes")
        batch.drop_column("contact_person_phone")
        batch.drop_column("contact_person_email")
        batch.drop_column("contact_person_name")
        batch.drop_column("warehouse_address")
        batch.drop_column("shipping_address")
        batch.drop_column("billing_address")
        batch.drop_column("registration_number")
        batch.drop_column("legal_name")
        batch.drop_column("plan_code")

    with op.batch_alter_table("warehouses") as batch:
        batch.drop_constraint("fk_warehouses_manager_id_users", type_="foreignkey")
        batch.drop_column("is_active")
        batch.drop_column("capacity")
        batch.drop_column("address")
        batch.drop_column("manager_id")
        batch.drop_column("warehouse_type")

    with op.batch_alter_table("stores") as batch:
        batch.drop_column("operating_hours")

    with op.batch_alter_table("departments") as batch:
        batch.drop_constraint("fk_departments_head_user_id_users", type_="foreignkey")
        batch.drop_column("head_user_id")

    with op.batch_alter_table("branches") as batch:
        batch.drop_constraint("fk_branches_manager_id_users", type_="foreignkey")
        batch.drop_column("email")
        batch.drop_column("phone")
        batch.drop_column("manager_id")
