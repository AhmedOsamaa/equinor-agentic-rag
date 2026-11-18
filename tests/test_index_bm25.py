"""BM25 tests on a tiny hand-made corpus (no model, temporary index folder)."""

import pytest

from rag import config, index
from rag.chunk import Chunk

TEXTS = [
    "Flaring of gas is prohibited unless approved by the regulator.",
    "Equinor reduced flaring emissions in 2025. Flaring emissions fell.",
    "The operator shall report emissions of CO2 and methane each year.",
    "Section 59a Analysis of oil and condensate samples.",
]


@pytest.fixture
def built(tmp_path, monkeypatch):
    chunks = [Chunk("d", i + 1, t, [f"d:{i}"], ("Doc",), f"d:{i:04d}") for i, t in enumerate(TEXTS)]
    monkeypatch.setattr(index, "read_chunks", lambda: chunks)
    monkeypatch.setattr(config, "BM25_INDEX_DIR", tmp_path / "bm25")
    monkeypatch.setattr(config, "BM25_BUILD_INFO", tmp_path / "bm25_build.json")
    monkeypatch.setattr(config, "BM25_USE_EMBED_TEXT", False)
    monkeypatch.setattr(index, "_bm25", None)
    index.build_bm25_index()
    return chunks


def test_numbers_and_clause_references_stay_whole():
    words = index.tokenize(["TRIF 1,041 and 0.043 under Sections 1-3 and 2-2, Scope 1, 2025-2030 at Equinor's"])[0]
    assert "1,041" in words and "0.043" in words and "1-3" in words and "2-2" in words
    assert "1" in words  # single digits are kept
    assert "s" not in words  # single letters are not
    assert "2025" in words and "2030" in words  # a year range splits into the two years


def test_stopwords_are_removed():
    assert index.tokenize(["the operator and the regulator"])[0] == ["operator", "regulator"]


def test_rare_exact_word_ranks_its_chunk_first(built):
    hits = index.search_bm25("Section 59a", k=3)
    assert hits[0].chunk_id == "d:0003"
    assert hits[0].score > 0


def test_more_matching_words_rank_higher_and_nonmatching_chunks_are_left_out(built):
    hits = index.search_bm25("flaring emissions", k=4)
    assert [h.chunk_id for h in hits] == ["d:0001", "d:0000", "d:0002"]  # c3 matches nothing
    assert hits[0].score > hits[1].score > hits[2].score > 0


def test_query_with_only_unknown_words_returns_nothing(built):
    assert index.search_bm25("zzzunknown") == []


def test_saved_index_reloads_with_the_same_ranking(built, monkeypatch):
    before = [h.chunk_id for h in index.search_bm25("flaring emissions", k=4)]
    monkeypatch.setattr(index, "_bm25", None)  # force a reload from disk
    assert [h.chunk_id for h in index.search_bm25("flaring emissions", k=4)] == before


def test_stale_index_is_refused(built, monkeypatch):
    monkeypatch.setattr(index, "_bm25", None)
    monkeypatch.setattr(index, "read_chunks", lambda: built[:3])  # chunks changed after the build
    with pytest.raises(RuntimeError, match="stale"):
        index.search_bm25("flaring")
