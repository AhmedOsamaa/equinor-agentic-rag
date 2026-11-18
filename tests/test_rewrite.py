from rag import rewrite
from rag.index import Hit


def test_parse_queries_basic_and_fenced():
    assert rewrite.parse_queries('{"queries": ["a", "b"]}') == ["a", "b"]
    assert rewrite.parse_queries('```json\n{"queries": ["a"]}\n```') == ["a"]


def test_parse_queries_drops_blanks_duplicates_and_caps():
    raw = '{"queries": ["a", " ", "a", "b", "c", "d", "e"]}'
    assert rewrite.parse_queries(raw) == ["a", "b", "c"]


def test_parse_queries_malformed_gives_empty():
    assert rewrite.parse_queries("not json") == []
    assert rewrite.parse_queries('{"queries": "a"}') == []
    assert rewrite.parse_queries('{"other": []}') == []


def _hit(cid: str) -> Hit:
    return Hit(chunk_id=cid, doc_id="d", page=1, text=cid, score=0.0, heading_path="")


class _Result:
    def __init__(self, ids):
        self.hits = [_hit(i) for i in ids]


def _fake_search(monkeypatch, lists):
    monkeypatch.setattr(rewrite, "search", lambda q, mode, pool: _Result(lists[q]))


def test_multi_search_merges_by_rrf_when_nothing_is_kept(monkeypatch):
    _fake_search(monkeypatch, {"q1": ["x", "y"], "q2": ["z", "y"]})
    merged = rewrite.multi_search(["q1", "q2"], k=3, keep=0)
    # y is in both lists (ranks 2 and 2): 2/62 beats z (rank 1 in one list only): 1/61.
    assert merged[0].chunk_id == "y"
    assert {h.chunk_id for h in merged} == {"x", "y", "z"}


def test_multi_search_keeps_top_of_original_then_fills_by_rrf(monkeypatch):
    # Worked by hand, RRF k = 60. a and b are the original's top 2, so they stay first in its order.
    # The other chunks, by RRF score: x 1/61, y 1/62, c 1/63, d 1/64. Only two slots are left, so x and y.
    _fake_search(monkeypatch, {"orig": ["a", "b", "c", "d"], "rew": ["x", "y", "a", "b"]})
    merged = rewrite.multi_search(["orig", "rew"], k=4, keep=2)
    assert [h.chunk_id for h in merged] == ["a", "b", "x", "y"]


def test_multi_search_original_top_survives_a_rewrite_that_ignores_it(monkeypatch):
    _fake_search(monkeypatch, {"orig": ["a", "b", "c"], "rew": ["x", "y", "z"]})
    merged = rewrite.multi_search(["orig", "rew"], k=3, keep=1)
    assert merged[0].chunk_id == "a"
    assert len(merged) == 3 and len({h.chunk_id for h in merged}) == 3


def test_multi_search_keep_larger_than_k_and_single_query(monkeypatch):
    _fake_search(monkeypatch, {"orig": ["a", "b", "c", "d"]})
    assert [h.chunk_id for h in rewrite.multi_search(["orig"], k=3, keep=10)] == ["a", "b", "c"]
    assert [h.chunk_id for h in rewrite.multi_search(["orig"], k=3, keep=1)] == ["a", "b", "c"]
