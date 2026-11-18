import math

import pytest

from rag.index import Hit
from rag.metrics import coverage_at_k, hit_at_k, mrr_at_k, ndcg_at_k

# Worked by hand: rank 1 irrelevant, rank 2 page-only, rank 3 and 5 hold the quote.
G = [0, 1, 2, 0, 2]


def test_hit_at_k():
    assert hit_at_k(G, 2) == 0.0  # the page-only chunk does not count
    assert hit_at_k(G, 3) == 1.0


def test_mrr_first_quote_at_rank_3():
    assert mrr_at_k(G, 5) == pytest.approx(1 / 3)
    assert mrr_at_k(G, 2) == 0.0


def test_mrr_rank_1():
    assert mrr_at_k([2, 0], 10) == 1.0


def test_ndcg_hand_computed():
    dcg = 1 / math.log2(3) + 3 / math.log2(4) + 3 / math.log2(6)
    ideal = 3 / math.log2(2) + 3 / math.log2(3)  # two gold quotes, both ranked first
    assert ndcg_at_k(G, 5, ideal=[2, 2]) == pytest.approx(dcg / ideal)
    assert ndcg_at_k(G, 5, ideal=[2, 2]) == pytest.approx(0.6727, abs=1e-4)


def test_ndcg_perfect_is_1_and_empty_is_0():
    assert ndcg_at_k([2, 2, 0], 3, ideal=[2, 2]) == pytest.approx(1.0)
    assert ndcg_at_k([0, 0, 0], 3, ideal=[2]) == 0.0


def test_ndcg_ideal_is_capped_by_k():
    # one slot, two gold quotes: the best possible is a single quote at rank 1
    assert ndcg_at_k([2], 1, ideal=[2, 2]) == pytest.approx(1.0)


def _hit(doc, text):
    return Hit(chunk_id="c", score=0.0, doc_id=doc, page=1, heading_path="", text=text)


def test_coverage_counts_each_gold_entry_once():
    gold = [
        {"doc_id": "a", "page": 1, "evidence_quote": "first fact"},
        {"doc_id": "b", "page": 1, "evidence_quote": "second fact"},
    ]
    hits = [_hit("a", "the first fact"), _hit("a", "first fact again"), _hit("b", "the second fact")]
    assert coverage_at_k(hits, gold, 2) == 0.5
    assert coverage_at_k(hits, gold, 3) == 1.0


def test_coverage_requires_the_gold_document():
    gold = [{"doc_id": "a", "page": 1, "evidence_quote": "first fact"}]
    assert coverage_at_k([_hit("b", "first fact")], gold, 1) == 0.0


def test_page_only_chunks_in_the_ranking_cannot_push_ndcg_above_one():
    # The bug found on 16 Nov: gains [2, 1] with one gold quote scored 1.21 when the ideal was
    # "one quote chunk per gold entry". An ideal that also holds the page-only chunk gives exactly 1.
    assert ndcg_at_k([2, 1, 0], 10, ideal=[2, 1]) == pytest.approx(1.0)
    assert ndcg_at_k([1, 2, 0], 10, ideal=[2, 1]) < 1.0


def test_no_ranking_drawn_from_the_ideal_pool_exceeds_one():
    import itertools

    pool = [2, 2, 1, 1, 0, 0]  # every chunk relevant to the question, plus two irrelevant ones
    ideal = [g for g in pool if g]
    for ranking in itertools.permutations(pool):
        assert 0.0 <= ndcg_at_k(list(ranking), 4, ideal) <= 1.0 + 1e-12


def test_ideal_order_does_not_matter():
    assert ndcg_at_k([2, 1], 5, ideal=[1, 2]) == pytest.approx(1.0)
