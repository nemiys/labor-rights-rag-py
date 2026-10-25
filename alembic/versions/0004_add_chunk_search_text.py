"""add search_text and a generated tsvector with a GIN index to chunks

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("search_text", sa.Text()))
    op.add_column(
        "chunks",
        sa.Column(
            "tsv",
            TSVECTOR(),
            sa.Computed("to_tsvector('simple', coalesce(search_text, ''))", persisted=True),
        ),
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_tsv", table_name="chunks")
    op.drop_column("chunks", "tsv")
    op.drop_column("chunks", "search_text")
