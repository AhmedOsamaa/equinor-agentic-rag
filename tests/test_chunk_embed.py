from rag.chunk import Chunk, embed_text


def chunk(text, path):
    return Chunk("d", 1, text, ["d:1"], path)


def test_prefix_adds_the_heading_path():
    c = chunk("Body text.", ("CHAPTER II", "Section 9 Principles"))
    assert embed_text(c, prefix=True) == "CHAPTER II > Section 9 Principles\n\nBody text."


def test_prefix_off_gives_the_plain_text():
    c = chunk("Body text.", ("A", "B"))
    assert embed_text(c, prefix=False) == "Body text."


def test_path_elements_already_in_the_text_are_not_repeated():
    c = chunk("# GHG emissions\n\n|a|b|", ("Environment", "GHG emissions"))
    assert embed_text(c, prefix=True) == "Environment\n\n# GHG emissions\n\n|a|b|"


def test_no_prefix_when_everything_is_already_in_the_text():
    c = chunk("# Only heading\n\ntext", ("Only heading",))
    assert embed_text(c, prefix=True) == c.text


def test_empty_path_gives_the_plain_text():
    assert embed_text(chunk("text", ()), prefix=True) == "text"
