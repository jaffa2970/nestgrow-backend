"""zona intervallo lettura

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-08
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "zone",
        sa.Column(
            "intervallo_lettura_sec",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )


def downgrade() -> None:
    op.drop_column("zone", "intervallo_lettura_sec")
