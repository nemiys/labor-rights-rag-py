"""Text search: the chunks that contain the words of the question (see ADR-0006)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.normalize import query_terms


async def text_search(
    session: AsyncSession, query: str, k: int, law_odata_id: int | None = None
) -> list[Hit]:
    terms = query_terms(query)
    if not terms:  # nothing but question words: there is nothing to look for
        return []

    # The terms hold only letters and digits (see normalize.py), so they are safe in a
    # tsquery. OR: a natural-language question never has every word in one section.
    tsquery = func.to_tsquery("simple", " | ".join(terms))
    rank = func.ts_rank_cd(Chunk.tsv, tsquery)
    statement = (
        select(
            Chunk.id,
            Law.odata_id,
            Law.name,
            Chunk.section_number,
            Chunk.chunk_index,
            Chunk.text,
            rank.label("rank"),
        )
        .join(Law, Chunk.law_id == Law.id)
        .where(Chunk.tsv.op("@@")(tsquery))
        .order_by(rank.desc(), Chunk.id)  # the id makes ties come out the same every time
        .limit(k)
    )
    if law_odata_id is not None:
        statement = statement.where(Law.odata_id == law_odata_id)

    rows = (await session.execute(statement)).all()
    return [
        Hit(
            rank=position,
            score=float(row.rank),
            chunk_id=row.id,
            law_odata_id=row.odata_id,
            law_name=row.name,
            section_number=row.section_number,
            chunk_index=row.chunk_index,
            text=row.text,
        )
        for position, row in enumerate(rows, start=1)
    ]
