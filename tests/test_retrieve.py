import pytest

from rag import config, rerank, retrieve
from rag.index import Hit


def test_rrf_worked_example():
    # vector A B C D, BM25 C E F A
    fused = retrieve.rrf([["A", "B", "C", "D"], ["C", "E", "F", "A"]], k=60)
    ids = [cid for cid, _ in fused]
    scores = dict(fused)
    assert ids == ["C", "A", "B", "E", "F", "D"]
    assert scores["C"] == pytest.approx(1 / 63 + 1 / 61)
    assert scores["A"] == pytest.approx(1 / 61 + 1 / 64)
    assert scores["B"] == pytest.approx(1 / 62) and scores["E"] == pytest.approx(1 / 62)


def test_rrf_tie_goes_to_the_earlier_list_and_is_repeatable():
    # B (vector rank 2) and E (BM25 rank 2) have the same score; the vector list comes first
    runs = [[cid for cid, _ in retrieve.rrf([["A", "B"], ["C", "E"]], k=60)] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    ids = runs[0]
    assert ids.index("B") < ids.index("E")


def test_rrf_chunk_in_both_lists_beats_a_chunk_in_one():
    ids = [cid for cid, _ in retrieve.rrf([["X", "Y"], ["Z", "Y"]], k=60)]
    assert ids[0] == "Y"  # rank 2 in both lists beats rank 1 in only one


def test_rrf_single_list_keeps_its_order_and_empty_input_is_fine():
    assert [cid for cid, _ in retrieve.rrf([["A", "B", "C"]])] == ["A", "B", "C"]
    assert retrieve.rrf([]) == [] and retrieve.rrf([[], []]) == []


def test_rrf_smaller_k_makes_the_top_rank_count_more():
    gap = lambda k: dict(retrieve.rrf([["A", "B"]], k=k))["A"] - dict(retrieve.rrf([["A", "B"]], k=k))["B"]
    assert gap(1) > gap(60)


def hit(cid, score=0.0):
    return Hit(cid, score, "d", 1, "path", f"text of {cid}")


@pytest.fixture
def fake_backends(monkeypatch):
    calls = {}

    def fake_vector(query, n, query_vector=None):
        calls["vector_n"] = n
        return [hit(c) for c in ["A", "B", "C", "D"]]

    def fake_bm25(query, n):
        calls["bm25_n"] = n
        return [hit(c) for c in ["C", "E", "F", "A"]]

    monkeypatch.setattr(retrieve, "encode_query", lambda q: "vector-of-query")
    monkeypatch.setattr(retrieve, "search_vector", fake_vector)
    monkeypatch.setattr(retrieve, "search_bm25", fake_bm25)
    return calls


def test_vector_mode_uses_only_the_vector_search(fake_backends):
    result = retrieve.search("q", "vector", k=2)
    assert [h.chunk_id for h in result.hits] == ["A", "B"]
    assert "bm25_search" not in result.timings and "rrf" not in result.timings
    assert fake_backends["vector_n"] == 2


def test_hybrid_mode_fuses_and_fetches_extra_candidates(fake_backends):
    result = retrieve.search("q", "hybrid", k=3)
    assert [h.chunk_id for h in result.hits] == ["C", "A", "B"]
    assert fake_backends["vector_n"] == fake_backends["bm25_n"] == config.RETRIEVE_CANDIDATES
    assert result.hits[0].score == pytest.approx(1 / 63 + 1 / 61)  # the score is the RRF score
    assert result.hits[0].text == "text of C"


def test_hybrid_rerank_mode_reorders_the_top_candidates(fake_backends, monkeypatch):
    seen = {}

    def fake_rerank(query, hits):
        seen["ids"] = [h.chunk_id for h in hits]
        return sorted(hits, key=lambda h: h.chunk_id, reverse=True)  # a recognisable new order

    monkeypatch.setattr(rerank, "rerank", fake_rerank)
    result = retrieve.search("q", "hybrid_rerank", k=2)
    assert seen["ids"] == ["C", "A", "B", "E", "F", "D"]  # the fused order went in
    assert [h.chunk_id for h in result.hits] == ["F", "E"]
    assert "rerank" in result.timings


def test_every_stage_is_timed_and_total_covers_them(fake_backends, monkeypatch):
    monkeypatch.setattr(rerank, "rerank", lambda q, hits: hits)
    t = retrieve.search("q", "hybrid_rerank", k=3).timings
    assert {"embed_query", "vector_search", "bm25_search", "rrf", "rerank", "total"} <= set(t)
    assert t["total"] >= sum(v for key, v in t.items() if key != "total") - 1e-6


def test_unknown_mode_is_refused(fake_backends):
    with pytest.raises(ValueError, match="unknown mode"):
        retrieve.search("q", "magic")


def test_reranker_orders_by_score_and_replaces_the_score(monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs, show_progress_bar=False):
            return [0.1 if "A" in text else 0.9 for _, text in pairs]

    monkeypatch.setattr(rerank, "_model", FakeCrossEncoder())
    out = rerank.rerank("q", [hit("A", 5.0), hit("B", 4.0)])
    assert [h.chunk_id for h in out] == ["B", "A"]
    assert out[0].score == pytest.approx(0.9)
    assert rerank.rerank("q", []) == []


# ---- pin_top_ranked ----
from rag.retrieve import pin_top_ranked  # noqa: E402


def test_a_first_ranked_chunk_outside_the_top_n_replaces_the_last_one_and_the_rest_keep_order():
    fused = ["a", "b", "c", "d", "e", "x"]            # x is 1st in the BM25 list but fused 6th
    out = pin_top_ranked(fused, [["a"], ["x"]], 3)
    assert out == ["a", "b", "x", "c", "d", "e"]      # x took c's slot; c is pushed behind, nothing is lost


def test_nothing_changes_when_the_first_ranked_chunks_are_already_inside():
    fused = ["a", "b", "c", "d"]
    assert pin_top_ranked(fused, [["a"], ["b"]], 3) == fused


def test_a_pinned_chunk_is_never_displaced_by_another_pinned_one():
    out = pin_top_ranked(["a", "b", "c", "x", "y"], [["c"], ["x"]], 3)   # c is pinned, so x replaces b
    assert out[:3] == ["a", "x", "c"] and set(out) == {"a", "b", "c", "x", "y"}


def test_both_pins_are_fitted_even_when_both_are_outside():
    out = pin_top_ranked(["a", "b", "c", "d", "x", "y"], [["x"], ["y"]], 3)
    assert set(out[:3]) == {"a", "x", "y"} and set(out) == {"a", "b", "c", "d", "x", "y"}
