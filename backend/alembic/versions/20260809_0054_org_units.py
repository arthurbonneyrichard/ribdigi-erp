"""Branches, departments, and user/store org unit FKs

Revision ID: 20260809_0054
Revises: 20260809_0053
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0054"
down_revision = "20260809_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_branches_tenant_code"),
    )
    op.create_index("ix_branches_tenant_id", "branches", ["tenant_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("branch_id", sa.String(length=36), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )
    op.create_index("ix_departments_tenant_id", "departments", ["tenant_id"])
    op.create_index("ix_departments_branch_id", "departments", ["branch_id"])

    op.add_column("users", sa.Column("branch_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("department_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_users_branch_id", "users", "branches", ["branch_id"], ["id"])
    op.create_foreign_key("fk_users_department_id", "users", "departments", ["department_id"], ["id"])
    op.create_index("ix_users_branch_id", "users", ["branch_id"])
    op.create_index("ix_users_department_id", "users", ["department_id"])

    op.add_column("stores", sa.Column("branch_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_stores_branch_id", "stores", "branches", ["branch_id"], ["id"])
    op.create_index("ix_stores_branch_id", "stores", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_stores_branch_id", table_name="stores")
    op.drop_constraint("fk_stores_branch_id", "stores", type_="foreignkey")
    op.drop_column("stores", "branch_id")

    op.drop_index("ix_users_department_id", table_name="users")
    op.drop_index("ix_users_branch_id", table_name="users")
    op.drop_constraint("fk_users_department_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_branch_id", "users", type_="foreignkey")
    op.drop_column("users", "department_id")
    op.drop_column("users", "branch_id")

    op.drop_index("ix_departments_branch_id", table_name="departments")
    op.drop_index("ix_departments_tenant_id", table_name="departments")
    op.drop_table("departments")
    op.drop_index("ix_branches_tenant_id", table_name="branches")
    op.drop_table("branches")
