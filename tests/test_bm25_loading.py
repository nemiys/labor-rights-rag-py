"""The BM25 index serves only the debug modes of /search, so it is built on first use."""

from types import SimpleNamespace
from typing import Any

import pytest

from labor_rights_rag.api import dependencies


async def test_the_index_is_built_on_first_use_and_then_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[object] = []

    async def fake_load(session: Any) -> object:
        index = object()
        built.append(index)
        return index

    monkeypatch.setattr(dependencies, "load_bm25_index", fake_load)
    request: Any = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    load = dependencies.get_bm25(request, session=None)  # type: ignore[arg-type]
    first = await load()
    second = await load()

    assert first is second is built[0]
    assert len(built) == 1


def test_getting_the_loader_builds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A vector search also receives the loader; it must not pay for the index."""

    async def fail(session: Any) -> object:
        raise AssertionError("the index was built")

    monkeypatch.setattr(dependencies, "load_bm25_index", fail)
    request: Any = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    dependencies.get_bm25(request, session=None)  # type: ignore[arg-type]
