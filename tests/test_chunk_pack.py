from rag.chunk import Block, Chunk, pack, split_sentences

words = lambda text: len(text.split())  # token counter for tests: one word = one token


def doc(*items):
    """items: ("h", "Title") or ("p", n_words) or ("t", n_words); sections numbered by headings."""
    out, sec = [], 0
    for kind, value in items:
        if kind == "h":
            sec += 1
            out.append(Block(f"# {value}", 1, "heading", f"d:{sec}", (value,)))
        elif kind == "p":
            out.append(Block(" ".join(["w"] * value), 1, "para", f"d:{sec}", ()))
        else:
            out.append(Block("| " + " ".join(["c"] * value) + " |", 1, "table", f"d:{sec}", ()))
    return out


def run(items, max_tok=400, min_tok=100):
    return pack(doc(*items), "d", max_tok, min_tok, count=words)


def test_exercise_250_60_300_gives_two_chunks():
    # the example from the explanation: the small middle section merges forward
    chunks = run([("h", "A"), ("p", 250), ("h", "B"), ("p", 60), ("h", "C"), ("p", 300)])
    assert len(chunks) == 2
    assert chunks[0].section_ids == ["d:1"]
    assert chunks[1].section_ids == ["d:2", "d:3"]
    assert chunks[1].heading_path == ("B",)  # path of the first block


def test_heading_only_fragments_stay_with_the_next_text():
    chunks = run([("h", "CHAPTER I"), ("h", "Scope"), ("p", 50)])
    assert len(chunks) == 1
    assert chunks[0].text.startswith("# CHAPTER I")


def test_size_cap_closes_a_chunk():
    chunks = run([("h", "A"), ("p", 300), ("p", 200)])
    assert [words(c.text) for c in chunks] == [302, 200]  # heading "# A" is 2 words


def test_no_chunk_over_max_when_blocks_are_small():
    chunks = run([("h", "A")] + [("p", 90)] * 20)
    assert all(words(c.text) <= 400 for c in chunks)


def test_long_paragraph_is_split_at_sentences_with_one_sentence_repeated():
    text = " ".join(f"Sentence number {i} has five words." for i in range(10))  # 6 words each
    pieces = split_sentences(text, 20, words)
    assert all(words(p) <= 20 for p in pieces)
    assert pieces[0].split(". ")[-1] in pieces[1]  # last sentence of piece 1 opens piece 2


def test_table_is_its_own_chunk():
    chunks = run([("h", "A"), ("p", 50), ("t", 30), ("p", 50)])
    assert [c.text.startswith("|") for c in chunks] == [False, True, False]


def test_every_word_survives_except_deliberate_repeats():
    items = [("h", "A"), ("p", 120), ("h", "B"), ("p", 70), ("t", 40), ("h", "C"), ("p", 380)]
    blocks = doc(*items)
    total = sum(words(b.text) for b in blocks)
    chunks = pack(blocks, "d", 400, 100, count=words)
    assert sum(words(c.text) for c in chunks) == total  # no overlap in this example
    assert isinstance(chunks[0], Chunk)


def test_headings_before_a_table_travel_with_it():
    chunks = run([("h", "Energy production"), ("t", 30)])
    assert len(chunks) == 1
    assert chunks[0].text.startswith("# Energy production") and "| c" in chunks[0].text


def test_body_before_the_title_is_closed_separately():
    chunks = run([("h", "A"), ("p", 50), ("h", "Table title"), ("t", 30), ("p", 20)])
    assert [c.text.startswith("#") for c in chunks] == [True, True, False]
    assert "Table title" not in chunks[0].text and "Table title" in chunks[1].text
    assert chunks[1].section_ids == ["d:2"]  # title and table share one section id


def test_several_stacked_headings_all_go_with_the_table():
    chunks = run([("h", "CHAPTER"), ("h", "Sub"), ("t", 10)])
    assert len(chunks) == 1 and chunks[0].text.count("#") == 2


# ---- table_context: a readable line for the embedder ----
from rag.chunk import table_context  # noqa: E402

TABLE = "|2025 (in USD million)|E&P Norway|REN|\n|---|---|---|\n|x|y|z|\n|Net impairment|(173)|(1,355)|\n|Exploration expenses|(567)|—|\n|(12)|1|2|"


def test_table_context_names_the_columns_and_the_row_labels():
    out = table_context(TABLE)
    assert out == ("Table with columns: 2025 (in USD million); E&P Norway; REN; x; y; z."
                   " Rows: Net impairment; Exploration expenses.")   # "(12)" is a number, not a label


def test_table_context_is_empty_for_prose_and_for_a_one_row_table():
    assert table_context("Just a paragraph.\nAnother line.") == ""
    assert table_context("|a|b|\n|---|---|") == ""


def test_table_context_describes_the_first_table_and_ignores_text_before_it():
    out = table_context("Table 4.4 Capacity factors\n\n" + TABLE + "\n\nLater text.")
    assert out.startswith("Table with columns: 2025") and "Later" not in out


# ---- table summaries in embed_text ----
def test_a_table_summary_is_put_in_front_of_the_chunk_only_when_switched_on(monkeypatch):
    from rag import chunk as ch

    c = ch.Chunk(doc_id="d", page=1, section_ids=(), heading_path=("Note 5",), text=TABLE)
    monkeypatch.setattr(ch, "load_table_summaries", lambda: {ch.text_hash(TABLE): "Segment results for 2025."})
    monkeypatch.setattr(ch.config, "CHUNK_TABLE_SUMMARIES", False)
    assert "Segment results" not in ch.embed_text(c)
    monkeypatch.setattr(ch.config, "CHUNK_TABLE_SUMMARIES", True)
    out = ch.embed_text(c)
    assert out.index("Note 5") < out.index("Segment results") < out.index("|2025")     # heading, summary, then the table
    assert c.text == TABLE                                                              # the stored text is untouched


def test_a_chunk_with_no_summary_is_embedded_as_before(monkeypatch):
    from rag import chunk as ch

    c = ch.Chunk(doc_id="d", page=1, section_ids=(), heading_path=(), text="Plain prose.")
    monkeypatch.setattr(ch, "load_table_summaries", lambda: {"unrelated-hash": "x"})
    monkeypatch.setattr(ch.config, "CHUNK_TABLE_SUMMARIES", True)
    assert ch.embed_text(c) == "Plain prose."
