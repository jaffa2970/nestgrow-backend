"""zone config fields + messaggi_cache table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-07 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Zone: irrigation configuration columns ---
    op.add_column("zone", sa.Column("descrizione_coltura", sa.String(100), nullable=True))
    op.add_column("zone", sa.Column("umidita_soglia_min", sa.Float(), nullable=True))
    op.add_column("zone", sa.Column("umidita_soglia_max", sa.Float(), nullable=True))
    op.add_column("zone", sa.Column("durata_irrigazione_sec", sa.Integer(), nullable=True))
    op.add_column(
        "zone",
        sa.Column("irrigazione_auto", sa.Boolean(), nullable=False, server_default="1"),
    )

    # --- Messages cache from License Server ---
    op.create_table(
        "messaggi_cache",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column(
            "tipo",
            sa.Enum("info", "warning", "critical"),
            nullable=False,
            server_default="info",
        ),
        sa.Column("titolo", sa.String(200), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("data_msg", sa.DateTime(), nullable=False),
        sa.Column("letto", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("ricevuto_il", sa.DateTime(), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("messaggi_cache")
    op.drop_column("zone", "irrigazione_auto")
    op.drop_column("zone", "durata_irrigazione_sec")
    op.drop_column("zone", "umidita_soglia_max")
    op.drop_column("zone", "umidita_soglia_min")
    op.drop_column("zone", "descrizione_coltura")
