"""Restaurant package prices: Starter GHS 179, Enterprise GHS 1,099 a month (yearly = 10 months).

Only rows still at the old starting price are changed, so a price the owner set by hand is kept.

Revision ID: 20261124_0235
Revises: 20261122_0234
Create Date: 2026-11-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261124_0235"
down_revision = "20261122_0234"
branch_labels = None
depends_on = None

# (plan code, old amount, new amount)
CHANGES = (
    ("starter-month-restaurant", "249.00", "179.00"),
    ("starter-year-restaurant", "2490.00", "1790.00"),
    ("enterprise-month-restaurant", "1199.00", "1099.00"),
    ("enterprise-year-restaurant", "11990.00", "10990.00"),
)


def _swap(old_idx: int, new_idx: int) -> None:
    bind = op.get_bind()
    if "platform_billing_plans" not in sa.inspect(bind).get_table_names():
        return
    for change in CHANGES:
        bind.execute(
            sa.text("UPDATE platform_billing_plans SET amount = :new WHERE code = :code AND amount = :old"),
            {"code": change[0], "old": change[old_idx], "new": change[new_idx]},
        )


def upgrade() -> None:
    _swap(1, 2)


def downgrade() -> None:
    _swap(2, 1)
