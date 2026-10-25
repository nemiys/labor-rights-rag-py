"""Run the ingest: `uv run python -m labor_rights_rag.ingest [--report PATH]`.

Fetches every law in corpus.toml from both sources, stores the ones that pass the
checks, and prints a report. Exit code 1 when a law could not be stored.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.embeddings.factory import EMBEDDER_NAMES, make_embedder
from labor_rights_rag.ingest.corpus import load_corpus
from labor_rights_rag.ingest.indexing import index_law
from labor_rights_rag.ingest.knesset import KnessetClient
from labor_rights_rag.ingest.pipeline import LawResult, collect, save_law
from labor_rights_rag.ingest.report import format_report
from labor_rights_rag.ingest.wikisource import WikisourceClient
from labor_rights_rag.persistence.database import engine, session_factory
from labor_rights_rag.persistence.models import Law
from labor_rights_rag.settings import settings


async def run(embedder: Embedder) -> list[LawResult]:
    corpus = load_corpus(Path(settings.corpus_path))
    results: list[LawResult] = []
    headers = {"User-Agent": settings.http_user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=30) as http:
        registry = KnessetClient(http, settings.knesset_odata_url)
        pages = WikisourceClient(http, settings.wikisource_api_url)
        for law in corpus:
            results.append(await collect(law, registry, pages))
            await asyncio.sleep(settings.request_delay_seconds)  # be gentle with both sites

    fetched_at = datetime.now(UTC)
    async with session_factory() as session:
        for result in results:
            if result.storable:
                await save_law(session, result, fetched_at)
                assert result.knesset and result.parsed
                law = await session.scalar(
                    select(Law).where(Law.odata_id == result.knesset.odata_id)
                )
                assert law
                result.index = await index_law(session, law, result.parsed, embedder)
                await session.commit()  # a law at a time: a failure keeps what is done
        await session.commit()
    await engine.dispose()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and store the laws in corpus.toml")
    parser.add_argument("--report", type=Path, help="also write the report to this file")
    parser.add_argument(
        "--embedder",
        choices=EMBEDDER_NAMES,
        default="bge-m3",
        help="the model that computes the vectors (hash: a fake one, for development)",
    )
    args = parser.parse_args()

    results = asyncio.run(run(make_embedder(args.embedder)))
    report = format_report(results)
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Hebrew on Windows
    print(report)
    return 0 if all(r.storable for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
