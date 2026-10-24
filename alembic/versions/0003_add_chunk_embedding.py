"""add embedding and embedding_model to chunks, with an HNSW index

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# BGE-M3. Written out here and not imported: a migration describes one moment in time.
DIM = 1024


def upgrade() -> None:
    op.add_column("chunks", sa.Column("embedding", Vector(DIM)))
    op.add_column("chunks", sa.Column("embedding_model", sa.Text()))
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_embedding_hnsw", table_name="chunks")
    op.drop_column("chunks", "embedding_model")
    op.drop_column("chunks", "embedding")
