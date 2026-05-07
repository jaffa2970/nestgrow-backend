"""culle refactor — culla as license unit, 4 zones per culla, new MQTT topics

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-07 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Disable FK checks so we can drop/recreate in any order
    op.execute("SET FOREIGN_KEY_CHECKS=0")

    # Drop tables that depend on old zone schema
    op.drop_table("irrigazioni")
    op.execute("DROP INDEX IF EXISTS idx_ts_zona ON letture")
    op.drop_table("letture")
    op.drop_table("zone")

    op.execute("SET FOREIGN_KEY_CHECKS=1")

    # --- New culle table (the licensed unit) ---
    op.create_table(
        "culle",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("device_id", sa.String(50), nullable=True),
        sa.Column("attiva", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("creato_il", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    # --- New zone table: 4 zones per culla, auto-created ---
    op.create_table(
        "zone",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "culla_id",
            sa.Integer(),
            sa.ForeignKey("culle.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("numero_zona", sa.Integer(), nullable=False),  # 1-4
        sa.Column("nome", sa.String(50), nullable=True),
        sa.Column(
            "pianta_id",
            sa.Integer(),
            sa.ForeignKey("piante.id"),
            nullable=True,
        ),
        sa.Column("attiva", sa.Boolean(), nullable=False, server_default="1"),
        sa.UniqueConstraint("culla_id", "numero_zona", name="uq_culla_zona"),
    )

    # --- Letture (sensor history) ---
    op.create_table(
        "letture",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "zona_id",
            sa.Integer(),
            sa.ForeignKey("zone.id"),
            nullable=False,
        ),
        sa.Column("umidita_pct", sa.Float(), nullable=True),
        sa.Column("livello_serbatoio_pct", sa.Float(), nullable=True),
    )
    op.create_index("idx_ts_zona", "letture", ["ts", "zona_id"])

    # --- Irrigazioni (irrigation log) ---
    op.create_table(
        "irrigazioni",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "zona_id",
            sa.Integer(),
            sa.ForeignKey("zone.id"),
            nullable=False,
        ),
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

    # --- Add tenant info columns to licenza_cache ---
    op.add_column(
        "licenza_cache",
        sa.Column("ragione_sociale", sa.String(200), nullable=True),
    )
    op.add_column(
        "licenza_cache",
        sa.Column("piva", sa.String(20), nullable=True),
    )
    op.add_column(
        "licenza_cache",
        sa.Column("email", sa.String(200), nullable=True),
    )

    # Clear the seeded free-plan row so the user must register explicitly
    op.execute("DELETE FROM licenza_cache WHERE id = 1")


def downgrade() -> None:
    op.drop_column("licenza_cache", "email")
    op.drop_column("licenza_cache", "piva")
    op.drop_column("licenza_cache", "ragione_sociale")

    op.execute("SET FOREIGN_KEY_CHECKS=0")
    op.drop_table("irrigazioni")
    op.execute("DROP INDEX IF EXISTS idx_ts_zona ON letture")
    op.drop_table("letture")
    op.drop_table("zone")
    op.drop_table("culle")
    op.execute("SET FOREIGN_KEY_CHECKS=1")

    # Restore original zone table (no data migration)
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
        sa.Column("trigger", sa.Enum("ai", "manuale", "soglia"), nullable=False, server_default="soglia"),
        sa.Column("esito", sa.Enum("ok", "serbatoio_vuoto", "timeout"), nullable=False, server_default="ok"),
    )
