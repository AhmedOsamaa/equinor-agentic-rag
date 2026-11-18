"""Cross-encoder reranking.

The search stages score a chunk and the query separately (an embedding of each, or word
counts). A cross-encoder reads the query and one chunk TOGETHER and outputs a relevance score,
which is slower but more accurate; so it only re-orders the few candidates the cheap stages found.
"""

from dataclasses import replace

from rag import config
from rag.index import Hit

_model = None


def get_reranker():
    """The cross-encoder, loaded once (the first use downloads about 1 GB)."""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(config.RERANK_MODEL)
    return _model


def rerank(query: str, hits: list[Hit]) -> list[Hit]:
    """The same hits, re-ordered best first; `score` becomes the reranker's score (a raw
    logit, not a probability; higher is more relevant)."""
    if not hits:
        return []
    scores = get_reranker().predict([(query, h.text) for h in hits], show_progress_bar=False)
    ordered = sorted(zip(hits, scores), key=lambda pair: -float(pair[1]))
    return [replace(h, score=float(s)) for h, s in ordered]
