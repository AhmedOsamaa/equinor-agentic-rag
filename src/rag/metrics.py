"""Retrieval metrics, written by hand so every number can be traced.

Inputs are gains in rank order (see `rag.matcher`): 2 = quote in chunk, 1 = gold page only,
0 = other. Only gain 2 counts as "relevant" for hit, coverage and MRR, because a chunk that is
merely on the right page may not contain the answer. nDCG uses the graded gains.
"""

import math

from rag.evidence import contains_quote
from rag.index import Hit

RELEVANT = 2


def hit_at_k(gains: list[int], k: int) -> float:
    """1.0 if any of the top k chunks holds a gold quote, else 0.0."""
    return float(any(g >= RELEVANT for g in gains[:k]))


def coverage_at_k(hits: list[Hit], gold: list[dict], k: int) -> float:
    """Share of the gold evidence entries whose quote is in some top-k chunk.

    Equals hit@k for one-quote questions; for multi-page questions it shows whether the
    retriever found all the evidence or only part of it.
    """
    if not gold:
        raise ValueError("coverage needs at least one gold entry")
    found = sum(
        any(h.doc_id == g["doc_id"] and contains_quote(h.text, g["evidence_quote"]) for h in hits[:k])
        for g in gold
    )
    return found / len(gold)


def mrr_at_k(gains: list[int], k: int) -> float:
    """1 / rank of the first relevant chunk within the top k, else 0."""
    for rank, g in enumerate(gains[:k], start=1):
        if g >= RELEVANT:
            return 1.0 / rank
    return 0.0


def _dcg(gains: list[int]) -> float:
    # 2**g - 1 makes a quote hit (gain 2) worth 3 and a page-only hit worth 1.
    return sum((2**g - 1) / math.log2(rank + 1) for rank, g in enumerate(gains, start=1))


def ndcg_at_k(gains: list[int], k: int, ideal: list[int]) -> float:
    """DCG of the ranking divided by the DCG of the best possible ranking.

    `ideal` is the gains of every chunk in the corpus that is relevant to the question (see
    `rag.matcher.ideal_gains`). It must hold at least the gains the ranking can contain, otherwise
    the ratio can exceed 1; the eval checks that no metric leaves [0, 1].
    """
    best = _dcg(sorted(ideal, reverse=True)[:k])
    return _dcg(gains[:k]) / best if best else 0.0
