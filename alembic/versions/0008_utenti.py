"""Add utenti table with admin seed

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-08 00:00:00.000000

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "utenti",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("ruolo", sa.Enum("administrator", "user"), nullable=False, server_default="user"),
        sa.Column("attivo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("creato_il", sa.DateTime, server_default=sa.func.now()),
    )

    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        raise ValueError(
            "ADMIN_PASSWORD non impostata — "
            "impossibile creare utente admin di default"
        )
    hashed = pwd.hash(admin_password)
    op.execute(
        sa.text(
            "INSERT INTO utenti (username, password_hash, ruolo, attivo) "
            "VALUES (:u, :h, 'administrator', TRUE)"
        ).bindparams(u="admin", h=hashed)
    )


def downgrade() -> None:
    op.drop_table("utenti")
