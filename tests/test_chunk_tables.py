from rag.chunk import Block, pack, split_table

words = lambda text: len(text.split())  # one word = one token


def table(n_rows, cells=3):
    """A markdown table: header row, separator, n_rows rows of `cells` words each."""
    head = "|" + "|".join(f"col{i}" for i in range(cells)) + "|"
    sep = "|" + "|".join("---" for _ in range(cells)) + "|"
    rows = ["|" + "|".join(f"r{r}c{i}" for i in range(cells)) + "|" for r in range(n_rows)]
    return "\n".join([head, sep] + rows)


def test_every_piece_repeats_the_header_and_fits():
    pieces = split_table(table(20), 8, words)
    assert len(pieces) > 1
    for p in pieces:
        assert p.splitlines()[:2] == ["|col0|col1|col2|", "|---|---|---|"]
        assert words(p) <= 8


def test_rows_are_neither_lost_nor_duplicated():
    pieces = split_table(table(20), 8, words)
    rows = [line for p in pieces for line in p.splitlines()[2:]]
    assert rows == table(20).splitlines()[2:]


def test_row_longer_than_the_cap_stays_whole():
    text = "|a|b|\n|---|---|\n|" + "|".join(["x " * 30, "y"]) + "|"
    pieces = split_table(text, 5, words)
    assert len(pieces) == 1 and "x x x" in pieces[0]


def test_small_table_is_not_split():
    t = table(2)
    assert split_table(t, 400, words) == [t]


def test_title_headings_repeat_in_every_piece_of_a_big_table():
    blocks = [Block("# GHG emissions", 5, "heading", "d:1", ("GHG emissions",)),
              Block(table(60), 5, "table", "d:1", ("GHG emissions",))]
    chunks = pack(blocks, "d", 40, 10, count=words)
    assert len(chunks) > 1
    for c in chunks:
        assert c.text.startswith("# GHG emissions")
        assert "|col0|col1|col2|" in c.text
        assert words(c.text) <= 40
    assert all(c.page == 5 and c.section_ids == ["d:1"] for c in chunks)


def test_table_without_separator_line_is_split_without_header():
    text = "\n".join(f"|r{i}|v{i}|" for i in range(10))
    pieces = split_table(text, 4, words)
    assert [line for p in pieces for line in p.splitlines()] == text.splitlines()


def test_caption_paragraph_travels_with_its_table():
    blocks = [Block("Some earlier text about costs.", 5, "para", "d:1", ("Costs",)),
              Block("Table 3.2 Capacity factors for solar PV, 2010-2024", 5, "para", "d:1", ("Costs",)),
              Block(table(2), 5, "table", "d:1", ("Costs",))]
    chunks = pack(blocks, "d", 400, 10, count=words)
    assert len(chunks) == 2
    assert chunks[0].text == "Some earlier text about costs."  # the caption is no longer left behind
    assert chunks[1].text.startswith("Table 3.2 Capacity factors for solar PV")
    assert "|col0|col1|col2|" in chunks[1].text


def test_caption_goes_after_the_headings_in_the_title():
    blocks = [Block("# Capacity factors", 5, "heading", "d:1", ("Capacity factors",)),
              Block("Table 3.2 Capacity factors for solar PV", 5, "para", "d:1", ("Capacity factors",)),
              Block(table(2), 5, "table", "d:1", ("Capacity factors",))]
    chunks = pack(blocks, "d", 400, 10, count=words)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("# Capacity factors\n\nTable 3.2 Capacity factors for solar PV\n\n|col0")


def test_long_caption_like_paragraph_is_not_pulled_in():
    long_para = "Table 4.4 presents the regional results. " + "word " * 100
    blocks = [Block(long_para, 5, "para", "d:1", ("X",)), Block(table(2), 5, "table", "d:1", ("X",))]
    chunks = pack(blocks, "d", 400, 10, count=words)
    assert chunks[0].text == long_para and chunks[1].text == table(2)


def test_ordinary_paragraph_before_a_table_stays_behind():
    # An Equinor-style footnote of the previous table must not become the next table's title.
    blocks = [Block("Methodologies: Sourced from SAP HR.", 5, "para", "d:1", ("X",)),
              Block(table(2), 5, "table", "d:1", ("X",))]
    chunks = pack(blocks, "d", 400, 10, count=words)
    assert chunks[0].text == "Methodologies: Sourced from SAP HR." and chunks[1].text == table(2)
