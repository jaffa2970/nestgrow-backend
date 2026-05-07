"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "piano_limiti",
        sa.Column("piano", sa.String(20), primary_key=True),
        sa.Column("max_culle", sa.Integer(), nullable=False),
    )

    op.create_table(
        "piante",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("umidita_min", sa.Float(), nullable=False),
        sa.Column("umidita_max", sa.Float(), nullable=False),
        sa.Column("durata_irrigazione_sec", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("creato_il", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "zone",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(50), nullable=False),
        sa.Column(
            "pianta_id",
            sa.Integer(),
            sa.ForeignKey("piante.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("attiva", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("device_id", sa.String(50), nullable=True),
        sa.Column("creato_il", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "letture",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("zona_id", sa.Integer(), sa.ForeignKey("zone.id"), nullable=False),
        sa.Column("umidita_pct", sa.Float(), nullable=True),
        sa.Column("livello_serbatoio_pct", sa.Float(), nullable=True),
    )
    op.create_index("idx_ts_zona", "letture", ["ts", "zona_id"])

    op.create_table(
        "irrigazioni",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("zona_id", sa.Integer(), sa.ForeignKey("zone.id"), nullable=False),
        sa.Column("ts_inizio", sa.DateTime(), nullable=False),
        sa.Column("ts_fine", sa.DateTime(), nullable=True),
        sa.Column("durata_sec", sa.Integer(), nullable=True),
        sa.Column("umidita_pre", sa.Float(), nullable=True),
        sa.Column("umidita_post", sa.Float(), nullable=True),
        sa.Column(
            "trigger",
            sa.Enum("ai", "manuale", "soglia"),
            nullable=False,
            server_default="soglia",
        ),
        sa.Column(
            "esito",
            sa.Enum("ok", "serbatoio_vuoto", "timeout"),
            nullable=False,
            server_default="ok",
        ),
    )

    op.create_table(
        "licenza_cache",
        sa.Column("id", sa.Integer(), primary_key=True, default=1),
        sa.Column("piano", sa.String(20), nullable=False),
        sa.Column("valida_fino", sa.DateTime(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("aggiornato_il", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # --- Seed data ---
    op.bulk_insert(
        sa.table(
            "piano_limiti",
            sa.column("piano", sa.String),
            sa.column("max_culle", sa.Integer),
        ),
        [
            {"piano": "free", "max_culle": 1},
            {"piano": "pro", "max_culle": 5},
            {"piano": "enterprise", "max_culle": 20},
            {"piano": "ultra", "max_culle": 9999},
        ],
    )

    op.bulk_insert(
        sa.table(
            "piante",
            sa.column("nome", sa.String),
            sa.column("umidita_min", sa.Float),
            sa.column("umidita_max", sa.Float),
            sa.column("durata_irrigazione_sec", sa.Integer),
            sa.column("note", sa.Text),
        ),
        [
            {
                "nome": "Basilico",
                "umidita_min": 30.0,
                "umidita_max": 70.0,
                "durata_irrigazione_sec": 20,
                "note": "Pianta aromatica, richiede buon drenaggio",
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("licenza_cache")
    op.drop_table("irrigazioni")
    op.drop_index("idx_ts_zona", table_name="letture")
    op.drop_table("letture")
    op.drop_table("zone")
    op.drop_table("piante")
    op.drop_table("piano_limiti")
