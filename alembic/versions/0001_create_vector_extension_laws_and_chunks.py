"""create vector extension, laws and chunks

Revision ID: 0001
Revises:
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enabled now (it does not depend on the vector size); the embedding column
    # itself is added in stage 3, once the embedding model is chosen.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "laws",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("odata_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("wikisource_title", sa.Text(), nullable=False),
        sa.Column("validity", sa.Text()),
        sa.Column("last_publication_date", sa.Date()),
        sa.Column("last_amendment_year", sa.Integer()),
        sa.Column("revid", sa.Integer()),
        sa.Column("content_hash", sa.Text()),
        sa.Column("currency_status", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "currency_status IN ('ok', 'ahead', 'behind', 'unknown')",
            name="ck_laws_currency_status",
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "law_id",
            sa.Integer(),
            sa.ForeignKey("laws.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_number", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("heading_path", sa.Text()),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "amended_years",
            sa.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "law_id",
            "section_number",
            "chunk_index",
            "content_hash",
            name="uq_chunks_law_section_chunk_hash",
        ),
    )
    op.create_index("ix_chunks_law_id", "chunks", ["law_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_law_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("laws")
    op.execute("DROP EXTENSION IF EXISTS vector")
