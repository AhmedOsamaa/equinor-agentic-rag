from rag.chunk import Block, assign_sections, classify


def blocks(*items):
    return [Block(text, 1, classify(text, "havtil_framework")) for text in items]


def paths(bl):
    return [(b.section_id, " > ".join(b.heading_path)) for b in bl]


def test_havtil_chapter_section_and_title_lines():
    bl = assign_sections(blocks(
        "# CHAPTER I", "# Introductory provisions",
        "# Section 1 Purpose", "Body one.",
        "# Section 2", "# Scope of application", "Body two.",
    ), "havtil_framework")
    assert paths(bl) == [
        ("havtil_framework:1", "CHAPTER I"),                       # the chapter heading itself
        ("havtil_framework:1", "CHAPTER I Introductory provisions"),  # its title joins it, same section
        ("havtil_framework:2", "CHAPTER I Introductory provisions > Section 1 Purpose"),
        ("havtil_framework:2", "CHAPTER I Introductory provisions > Section 1 Purpose"),
        ("havtil_framework:3", "CHAPTER I Introductory provisions > Section 2"),
        ("havtil_framework:3", "CHAPTER I Introductory provisions > Section 2 Scope of application"),
        ("havtil_framework:3", "CHAPTER I Introductory provisions > Section 2 Scope of application"),
    ]


def test_havtil_list_item_is_body_not_heading():
    assert classify("# a) The responsible party:", "havtil_framework") == "para"
    assert classify("# Section 6 Definitions", "havtil_framework") == "heading"


def test_new_chapter_closes_previous_section():
    bl = assign_sections(blocks("# CHAPTER I", "# Section 1", "Text.", "# CHAPTER II", "More."), "havtil_framework")
    assert bl[-1].heading_path == ("CHAPTER II",)


def test_markdown_level_for_reports():
    bl = [Block("# A", 1, "heading"), Block("## B", 1, "heading"), Block("text", 1, "para"),
          Block("## C", 2, "heading"), Block("text", 2, "para"), Block("# D", 3, "heading")]
    assign_sections(bl, "irena_x")
    assert bl[2].heading_path == ("A", "B")
    assert bl[4].heading_path == ("A", "C")  # C replaces its sibling B
    assert bl[5].heading_path == ("D",)


def test_text_before_any_heading_has_empty_path():
    bl = assign_sections([Block("intro", 1, "para")], "irena_x")
    assert bl[0].heading_path == () and bl[0].section_id == "irena_x:0"


def test_section_number_with_letter_is_a_section():
    bl = assign_sections(blocks("# CHAPTER X", "# Section 59", "Text.", "# Section 59a", "More."), "havtil_activities")
    assert bl[-1].heading_path == ("CHAPTER X", "Section 59a")
