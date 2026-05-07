"""Add jwt_token column to licenza_cache

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-07 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "licenza_cache",
        sa.Column("jwt_token", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("licenza_cache", "jwt_token")
