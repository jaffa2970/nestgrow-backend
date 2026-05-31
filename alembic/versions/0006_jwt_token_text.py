"""Widen jwt_token to TEXT (RSA JWTs exceed VARCHAR(500))

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-07 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "licenza_cache",
        "jwt_token",
        type_=sa.Text,
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "licenza_cache",
        "jwt_token",
        type_=sa.String(500),
        existing_nullable=True,
    )
