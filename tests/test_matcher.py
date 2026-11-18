from rag.index import Hit
from rag.matcher import gain, gains, ideal_gains, index_chunks

GOLD = [{"doc_id": "d1", "page": 5, "evidence_quote": "Operators shall report within 24 hours"}]


def hit(doc="d1", page=5, text="x"):
    return Hit(chunk_id="c", score=0.0, doc_id=doc, page=page, heading_path="", text=text)


def test_quote_in_chunk_is_2():
    assert gain(hit(text="## Sec 3\n\nOperators shall report  within 24 HOURS to the authority."), GOLD) == 2


def test_same_page_without_quote_is_1():
    assert gain(hit(text="unrelated text"), GOLD) == 1


def test_other_page_is_0():
    assert gain(hit(page=6), GOLD) == 0


def test_other_document_is_0_even_with_quote_and_page():
    assert gain(hit(doc="d2", text="Operators shall report within 24 hours"), GOLD) == 0


def test_best_over_several_gold_entries():
    gold = GOLD + [{"doc_id": "d2", "page": 9, "evidence_quote": "second fact"}]
    assert gain(hit(doc="d2", page=9, text="the second fact is here"), gold) == 2


def test_gains_keeps_rank_order():
    hits = [hit(page=6), hit(text="Operators shall report within 24 hours"), hit(text="other")]
    assert gains(hits, GOLD) == [0, 2, 1]


def _chunk(doc, page, text):
    return {"doc_id": doc, "page": page, "text": text}


CORPUS = index_chunks([
    _chunk("d1", 5, "Operators shall report within 24 hours."),   # holds the quote: gain 2
    _chunk("d1", 5, "Unrelated text on the same page."),           # same page, no quote: gain 1
    _chunk("d1", 6, "Operators shall report elsewhere."),          # other page: gain 0
    _chunk("d2", 5, "Operators shall report within 24 hours."),   # other document: gain 0
])


def test_ideal_gains_lists_every_relevant_chunk_best_first():
    assert ideal_gains(GOLD, CORPUS, 10) == [2, 1]


def test_ideal_gains_counts_a_quote_held_by_two_chunks_twice_and_cuts_at_k():
    twice = index_chunks([_chunk("d1", 5, "Operators shall report within 24 hours."),
                          _chunk("d1", 5, "Again: operators shall report within 24 hours."),
                          _chunk("d1", 5, "Other text on the page.")])
    assert ideal_gains(GOLD, twice, 10) == [2, 2, 1]
    assert ideal_gains(GOLD, twice, 2) == [2, 2]


def test_ideal_gains_takes_the_best_gain_over_gold_entries_without_double_counting():
    gold = GOLD + [{"doc_id": "d1", "page": 5, "evidence_quote": "unrelated text on the same page"}]
    assert ideal_gains(gold, CORPUS, 10) == [2, 2]   # the second chunk is now a quote chunk for the second entry


def test_ideal_gains_is_empty_when_nothing_in_the_corpus_is_relevant():
    assert ideal_gains([{"doc_id": "d9", "page": 1, "evidence_quote": "nothing"}], CORPUS, 10) == []


def test_every_ranking_of_corpus_chunks_scores_at_most_the_ideal():
    # the ideal list is at least as good as the gains of any chunks we can retrieve
    from rag.matcher import gain as one_gain

    hits = [Hit("c", 0.0, "d1", 5, "", t) for t in ("Operators shall report within 24 hours.", "Unrelated text on the same page.")]
    assert sorted((one_gain(h, GOLD) for h in hits), reverse=True) == ideal_gains(GOLD, CORPUS, 10)
