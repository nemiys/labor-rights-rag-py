"""Store the chunks of a law with their vectors, computing only what changed.

Each run compares the chunks the law should have now with the chunks stored:
  new       -> stored, and a vector is computed
  unchanged -> left alone (the saving: the model runs only on new text)
  gone      -> deleted, so an answer can never quote a section that was removed
A chunk's identity is (section, part, hash of the text that is embedded). The hash covers
the header too, so a renamed law or a different model recomputes the vector.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.chunking.chunker import chunk_section
from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.ingest.pipeline import IndexStats, content_hash
from labor_rights_rag.parsing.wikitext import ParsedLaw
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.normalize import to_search_text

Key = tuple[str, int, str]  # section number, part, hash of the embedded text


async def index_law(
    session: AsyncSession, law: Law, parsed: ParsedLaw, embedder: Embedder
) -> IndexStats:
    stats = IndexStats()
    rows = await session.scalars(select(Chunk).where(Chunk.law_id == law.id))
    stored: dict[Key, Chunk] = {
        (row.section_number, row.chunk_index, row.content_hash): row for row in rows
    }

    wanted: set[Key] = set()
    to_embed: list[tuple[Chunk, str]] = []
    for section in parsed.sections:
        # The short, common name goes into the header; the full official name is on the law.
        for chunk in chunk_section(law.wikisource_title, section):
            key = (chunk.section_number, chunk.chunk_index, content_hash(chunk.embed_text))
            wanted.add(key)
            row = stored.get(key)
            if row is None:
                row = Chunk(
                    law_id=law.id,
                    section_number=chunk.section_number,
                    chunk_index=chunk.chunk_index,
                    heading_path=chunk.heading_path,
                    text=chunk.text,
                    content_hash=key[2],
                )
                session.add(row)
                stats.added += 1
            row.amended_years = chunk.amended_years
            # Rewritten on every run, so a change in the normalization rules needs no model.
            row.search_text = to_search_text(chunk.embed_text)
            if row.embedding is not None and row.embedding_model == embedder.name:
                stats.kept += 1
            else:
                to_embed.append((row, chunk.embed_text))

    for key, row in stored.items():
        if key not in wanted:
            await session.delete(row)
            stats.removed += 1

    if to_embed:
        # The model is CPU-bound: a thread keeps the event loop free, as in vector_search.
        vectors = await asyncio.to_thread(embedder.embed_documents, [text for _, text in to_embed])
        for (row, _), vector in zip(to_embed, vectors, strict=True):
            row.embedding = vector
            row.embedding_model = embedder.name
    stats.embedded = len(to_embed)
    await session.flush()
    return stats
