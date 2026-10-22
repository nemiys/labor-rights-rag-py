from pathlib import Path

import pytest

from labor_rights_rag.ingest.corpus import CorpusLaw, load_corpus


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "corpus.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_wikisource_title_defaults_to_the_law_title(tmp_path: Path) -> None:
    path = _write(tmp_path, '[[law]]\ntitle = "חוק חופשה שנתית"\n')

    assert load_corpus(path) == [CorpusLaw("חוק חופשה שנתית", "חוק חופשה שנתית")]


def test_wikisource_title_can_be_overridden(tmp_path: Path) -> None:
    path = _write(tmp_path, '[[law]]\ntitle = "חוק א"\nwikisource_title = "חוק א (נוסח משולב)"\n')

    assert load_corpus(path)[0].wikisource_title == "חוק א (נוסח משולב)"


def test_entry_without_title_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, '[[law]]\nwikisource_title = "x"\n')

    with pytest.raises(ValueError, match="without a title"):
        load_corpus(path)


def test_duplicate_title_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, '[[law]]\ntitle = "חוק א"\n[[law]]\ntitle = "חוק א"\n')

    with pytest.raises(ValueError, match="duplicate"):
        load_corpus(path)


def test_the_real_corpus_file_is_valid() -> None:
    laws = load_corpus(Path("corpus.toml"))

    assert len(laws) >= 20
