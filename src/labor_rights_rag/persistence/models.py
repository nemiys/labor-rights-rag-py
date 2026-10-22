"""Database tables: one row per law, and one row per searchable chunk of a law.

The embedding and full-text-search columns are deliberately missing. Their shape
depends on decisions that are made later (embedding model in stage 3, Hebrew text
normalization in stage 4), and Alembic adds them then without losing data.
"""

from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    last_amendment_year: Mapped[int | None]
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
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    law_id: Mapped[int] = mapped_column(ForeignKey("laws.id", ondelete="CASCADE"), index=True)
    # Text, not int: sections like "5א" exist.
    section_number: Mapped[str] = mapped_column(Text)
    # Position inside the section when a long section is split into several chunks.
    chunk_index: Mapped[int] = mapped_column(default=0)
    heading_path: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    amended_years: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    content_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    law: Mapped[Law] = relationship(back_populates="chunks")
