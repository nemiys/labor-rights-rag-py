"""Vector search: the chunks whose meaning is closest to the question."""

import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.settings import settings


async def use_exact_vector_scan(session: AsyncSession) -> None:
    """Make the vector queries of this transaction exact.

    An HNSW index is an approximate search. On a small table, or after many rows were deleted
    and inserted, it can return fewer rows than asked for. For about a thousand vectors a scan
    of the whole table takes milliseconds and is exact, so that is the default. The index stays
    in the schema for a corpus that grows (see docs/adr/0011). The setting VECTOR_INDEX turns it
    on, with a scan that goes on until it has enough rows, in exact order.
    """
    if settings.vector_index:
        await session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
    else:
        await session.execute(text("SET LOCAL enable_indexscan = off"))


async def vector_search(
    session: AsyncSession,
    embedder: Embedder,
    query: str,
    k: int,
    law_odata_id: int | None = None,
) -> list[Hit]:
    await use_exact_vector_scan(session)
    # The model is CPU-bound: a thread keeps the event loop free for other requests.
    vector = await asyncio.to_thread(embedder.embed_query, query)
    distance = Chunk.embedding.cosine_distance(vector)
    statement = (
        select(
            Chunk.id,
            Law.odata_id,
            Law.name,
            Chunk.section_number,
            Chunk.chunk_index,
            Chunk.text,
            distance.label("distance"),
        )
        .join(Law, Chunk.law_id == Law.id)
        # Vectors of different models cannot be compared (this also skips unembedded chunks).
        .where(Chunk.embedding_model == embedder.name)
        .order_by(distance)
        .limit(k)
    )
    if law_odata_id is not None:
        statement = statement.where(Law.odata_id == law_odata_id)

    rows = (await session.execute(statement)).all()
    return [
        Hit(
            rank=position,
            score=1 - row.distance,
            chunk_id=row.id,
            law_odata_id=row.odata_id,
            law_name=row.name,
            section_number=row.section_number,
            chunk_index=row.chunk_index,
            text=row.text,
        )
        for position, row in enumerate(rows, start=1)
    ]
