"""add last amendment label and url to laws

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("laws", sa.Column("last_amendment_label", sa.Text()))
    op.add_column("laws", sa.Column("last_amendment_url", sa.Text()))


def downgrade() -> None:
    op.drop_column("laws", "last_amendment_url")
    op.drop_column("laws", "last_amendment_label")
