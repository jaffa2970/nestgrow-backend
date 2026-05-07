"""Widen messaggi_cache.tipo from ENUM to VARCHAR(50)

The License Server sends types beyond info/warning/critical (e.g. 'aggiornamento',
'comunicazione'). VARCHAR(50) accepts any value; the application normalises on read.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-07 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "messaggi_cache",
        "tipo",
        type_=sa.String(50),
        existing_nullable=False,
        server_default="info",
    )


def downgrade() -> None:
    op.alter_column(
        "messaggi_cache",
        "tipo",
        type_=sa.Enum("info", "warning", "critical"),
        existing_nullable=False,
        server_default="info",
    )
