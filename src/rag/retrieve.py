"""The one retrieval entry point: search(query, mode, k).

mode "vector"         embedding search only
mode "hybrid"         vector + BM25, merged with Reciprocal Rank Fusion
mode "hybrid_rerank"  hybrid, then a cross-encoder re-orders the top candidates

Every call returns the ranked chunks and the seconds spent in each stage.

Run: uv run python -m rag.retrieve "your question" --mode hybrid --k 5
"""

import argparse
import time
from dataclasses import dataclass, field, replace

from rag import config
from rag.index import Hit, encode_query, search_bm25, search_vector


def rrf(rankings: list[list[str]], k: int | None = None) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion.

    `rankings` is a list of ranked lists of chunk ids (best first). A chunk's score is the sum,
    over the lists it appears in, of 1 / (k + its rank), with rank starting at 1. A chunk
    missing from a list adds nothing for that list. Returns (chunk_id, score), best first.

    Ties keep the order in which the chunks were first met, so chunks of the earlier list win
    (python's sort is stable). That makes the result the same on every run.
    """
    k = config.RRF_K if k is None else k
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: -item[1])


def pin_top_ranked(fused: list[str], rankings: list[list[str]], n: int) -> list[str]:
    """Make sure the 1st-ranked chunk of each retriever is inside the first n of the fused order.

    RRF rewards agreement, so a chunk that one retriever ranks 1st and the other does not list at all
    can fall to rank 20 (dev: equinor_ar2025-114, BM25 rank 1, fused rank 20). If such a chunk is
    outside the first n, it replaces the last chunk of the first n that is not itself pinned. All other
    chunks keep their fused order. Returns the whole reordered list.
    """
    pinned = [r[0] for r in rankings if r]
    head = fused[:n]
    displaced: list[str] = []
    for chunk_id in pinned:
        if chunk_id in head:
            continue
        for i in range(len(head) - 1, -1, -1):
            if head[i] not in pinned:
                displaced.insert(0, head[i])  # it was above everything after n, so it goes right behind the head
                head[i] = chunk_id
                break
    return head + displaced + [c for c in fused[n:] if c not in head]


@dataclass
class SearchResult:
    mode: str
    hits: list[Hit]
    timings: dict[str, float] = field(default_factory=dict)  # seconds per stage


def _timed(timings: dict[str, float], stage: str, func, *args, **kwargs):
    start = time.perf_counter()
    result = func(*args, **kwargs)
    timings[stage] = time.perf_counter() - start
    return result


def search(query: str, mode: str = "hybrid", k: int | None = None) -> SearchResult:
    if mode not in config.RETRIEVE_MODES:
        raise ValueError(f"unknown mode {mode!r}; use one of {config.RETRIEVE_MODES}")
    k = k or config.DEFAULT_K
    timings: dict[str, float] = {}
    start = time.perf_counter()

    # Vector and hybrid fetch more candidates than the k requested, so the fusion has material.
    n = k if mode == "vector" else max(k, config.RETRIEVE_CANDIDATES)
    query_vector = _timed(timings, "embed_query", encode_query, query)
    vector_hits = _timed(timings, "vector_search", search_vector, query, n, query_vector=query_vector)
    if mode == "vector":
        timings["total"] = time.perf_counter() - start
        return SearchResult(mode, vector_hits[:k], timings)

    bm25_hits = _timed(timings, "bm25_search", search_bm25, query, n)
    by_id = {h.chunk_id: h for h in bm25_hits}
    by_id.update({h.chunk_id: h for h in vector_hits})  # both carry the same chunk data
    rankings = [[h.chunk_id for h in vector_hits], [h.chunk_id for h in bm25_hits]]
    fused = _timed(timings, "rrf", rrf, rankings)
    fused_hits = [replace(by_id[cid], score=score) for cid, score in fused]
    if config.PIN_TOP_RANKED:
        # The pinned chunk keeps its own RRF score, so a displaced chunk may now sit above it with a lower score.
        scores = dict(fused)
        size = k if mode == "hybrid" else config.RERANK_CANDIDATES
        order = pin_top_ranked([cid for cid, _ in fused], rankings, size)
        fused_hits = [replace(by_id[cid], score=scores[cid]) for cid in order]

    if mode == "hybrid":
        timings["total"] = time.perf_counter() - start
        return SearchResult(mode, fused_hits[:k], timings)

    # Imported here so the other modes never load the reranker model.
    from rag.rerank import rerank

    reranked = _timed(timings, "rerank", rerank, query, fused_hits[:config.RERANK_CANDIDATES])
    timings["total"] = time.perf_counter() - start
    return SearchResult(mode, reranked[:k], timings)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("query")
    parser.add_argument("--mode", default="hybrid", choices=config.RETRIEVE_MODES)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    result = search(args.query, args.mode, args.k)
    for rank, h in enumerate(result.hits, start=1):
        print(f"{rank:2}. {h.score:8.4f}  {h.chunk_id}  p{h.page}  {h.heading_path[:70]}")
        print(f"      {h.text[:140].replace(chr(10), ' ')}")
    print("\ntimings (s): " + ", ".join(f"{stage} {seconds:.3f}" for stage, seconds in result.timings.items()))


if __name__ == "__main__":
    main()
