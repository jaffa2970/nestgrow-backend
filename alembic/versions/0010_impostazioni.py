"""impostazioni table

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-14
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "impostazioni",
        sa.Column("chiave", sa.String(50), primary_key=True),
        sa.Column("valore", sa.String(200), nullable=False),
        sa.Column("descrizione", sa.String(200), nullable=True),
    )
    op.execute(
        "INSERT INTO impostazioni (chiave, valore, descrizione) VALUES "
        "('retention_giorni', '30', 'Giorni di storico letture da conservare')"
    )


def downgrade() -> None:
    op.drop_table("impostazioni")
