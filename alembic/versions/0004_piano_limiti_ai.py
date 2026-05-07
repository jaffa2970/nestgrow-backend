"""Update piano_limiti: enterprise→ai (10 culle), remove ultra

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-07 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename enterprise → ai and set correct limit
    op.execute(
        "UPDATE piano_limiti SET piano='ai', max_culle=10 WHERE piano='enterprise'"
    )
    # Remove ultra (maps to ai now)
    op.execute("DELETE FROM piano_limiti WHERE piano='ultra'")
    # Ensure ai row exists even if enterprise wasn't there
    op.execute(
        "INSERT IGNORE INTO piano_limiti (piano, max_culle) VALUES ('ai', 10)"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE piano_limiti SET piano='enterprise', max_culle=20 WHERE piano='ai'"
    )
    op.execute(
        "INSERT IGNORE INTO piano_limiti (piano, max_culle) VALUES ('ultra', 9999)"
    )
