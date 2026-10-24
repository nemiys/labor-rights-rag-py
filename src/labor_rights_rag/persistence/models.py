"""Database tables: one row per law, and one row per searchable chunk of a law.

The full-text-search column is deliberately missing: its shape depends on how Hebrew
text is normalized (decided in stage 4), and Alembic adds it then without losing data.
"""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from labor_rights_rag.embeddings.base import EMBEDDING_DIM
from labor_rights_rag.persistence.database import Base

CURRENCY_STATUSES = ("ok", "ahead", "behind", "unknown")


class Law(Base):
    __tablename__ = "laws"
    __table_args__ = (
        CheckConstraint(
            "currency_status IN ('ok', 'ahead', 'behind', 'unknown')",
            name="ck_laws_currency_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Knesset OData id; also builds the link to the law's page on the Knesset site.
    odata_id: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(Text)
    wikisource_title: Mapped[str] = mapped_column(Text)
    validity: Mapped[str | None] = mapped_column(Text)
    last_publication_date: Mapped[date | None]
    # Hebrew year (5786) of the latest amendment the text includes, and that amendment as
    # published in Reshumot: the verification card links to the official PDF.
    last_amendment_year: Mapped[int | None]
    last_amendment_label: Mapped[str | None] = mapped_column(Text)
    last_amendment_url: Mapped[str | None] = mapped_column(Text)
    # Wikisource revision id and a hash of the text: if neither changed, skip re-processing.
    revid: Mapped[int | None]
    content_hash: Mapped[str | None] = mapped_column(Text)
    currency_status: Mapped[str] = mapped_column(Text, default="unknown")
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="law", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        # Idempotent indexing: the same text of the same section is never stored twice.
        UniqueConstraint(
            "law_id",
            "section_number",
            "chunk_index",
            "content_hash",
            name="uq_chunks_law_section_chunk_hash",
        ),
        # Nearest-neighbour search by cosine distance.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    law_id: Mapped[int] = mapped_column(ForeignKey("laws.id", ondelete="CASCADE"), index=True)
    # Text, not int: sections like "5א" exist.
    section_number: Mapped[str] = mapped_column(Text)
    # Position inside the section when a long section is split into several chunks.
    chunk_index: Mapped[int] = mapped_column(default=0)
    heading_path: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)  # the quote: the body only, verbatim from the law
    amended_years: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    # Hash of the text that is embedded (header + body): if it did not change, the
    # vector does not need to be computed again.
    content_hash: Mapped[str] = mapped_column(Text)
    # Empty until the chunk is embedded. Vectors of different models cannot be compared,
    # so the model's name is stored with each one.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    law: Mapped[Law] = relationship(back_populates="chunks")
