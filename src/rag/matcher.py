"""Relevance labels for retrieved chunks, derived from gold evidence (doc, page, quote).

Gold is written by evidence, never by chunk id, so the labels stay valid when the chunking
changes. Gain scale: 2 = right document and the quote is in the chunk, 1 = right document and
page but the quote is not in the chunk, 0 = anything else.

Known limitation: a quote split across two chunks is in neither, so both score 1.
"""

from collections import defaultdict

from rag.evidence import contains_quote, normalize
from rag.index import Hit


def gain(hit: Hit, gold: list[dict]) -> int:
    """Best gain of one retrieved chunk over all gold entries of a question."""
    best = 0
    for g in gold:
        if hit.doc_id != g["doc_id"]:
            continue
        if contains_quote(hit.text, g["evidence_quote"]):
            return 2  # cannot do better
        if hit.page == g["page"]:
            best = 1
    return best


def gains(hits: list[Hit], gold: list[dict]) -> list[int]:
    """Gain of every hit, in rank order. This list is the input to all the metrics."""
    return [gain(h, gold) for h in hits]


def index_chunks(chunks: list[dict]) -> dict[str, list[tuple[int, str]]]:
    """(page, normalized text) of every chunk, by document, built once so the ideal ranking is cheap."""
    out: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for c in chunks:
        out[c["doc_id"]].append((c["page"], normalize(c["text"])))
    return out


def ideal_gains(gold: list[dict], index: dict[str, list[tuple[int, str]]], k: int) -> list[int]:
    """Gains of the best possible ranking for a question: every chunk of the corpus that is
    relevant to it, best first, cut at k.

    A chunk is gain 2 if it contains a gold quote, else gain 1 if it is on a gold page (the same
    rule as `gain`). nDCG divides by the DCG of this list, so it cannot exceed 1. An earlier version
    assumed one quote chunk per gold entry and ignored the page-only chunks an ideal ranking would
    also hold, which let nDCG reach 1.2 or more when a page-only chunk was retrieved.
    """
    best: dict[tuple[str, int], int] = {}
    for g in gold:
        quote = normalize(g["evidence_quote"])
        for pos, (page, text) in enumerate(index.get(g["doc_id"], [])):
            gain = 2 if quote and quote in text else 1 if page == g["page"] else 0
            if gain > best.get((g["doc_id"], pos), 0):
                best[(g["doc_id"], pos)] = gain
    return sorted(best.values(), reverse=True)[:k]
