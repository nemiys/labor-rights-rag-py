"""Vector search: the chunks whose meaning is closest to the question."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit


async def vector_search(
    session: AsyncSession,
    embedder: Embedder,
    query: str,
    k: int,
    law_odata_id: int | None = None,
) -> list[Hit]:
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
