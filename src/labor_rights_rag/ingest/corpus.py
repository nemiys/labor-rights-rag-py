"""The list of laws in the corpus, read from corpus.toml."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CorpusLaw:
    title: str  # as the Knesset registry writes it, without the Hebrew-year suffix
    wikisource_title: str  # page title in the Open Law Book


def load_corpus(path: Path) -> list[CorpusLaw]:
    with path.open("rb") as file:
        entries = tomllib.load(file).get("law", [])

    laws: list[CorpusLaw] = []
    seen: set[str] = set()
    for entry in entries:
        title = entry.get("title")
        if not title:
            raise ValueError(f"corpus entry without a title: {entry}")
        if title in seen:
            raise ValueError(f"duplicate corpus entry: {title}")
        seen.add(title)
        laws.append(CorpusLaw(title=title, wikisource_title=entry.get("wikisource_title", title)))
    return laws
