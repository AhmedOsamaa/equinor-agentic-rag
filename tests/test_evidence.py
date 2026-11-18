from rag.evidence import contains_quote, n_words, normalize, question_overlap


def test_normalize_drops_markdown_and_collapses_space():
    assert normalize("|Tjeldbergodden|Methanol plant|2,600 ton/day|") == "tjeldbergodden methanol plant 2,600 ton/day"
    assert normalize("# Heading\n\n**bold**   text") == "heading bold text"


def test_normalize_folds_ligatures_and_nbsp():
    assert normalize("eﬃcient use") == "efficient use"


def test_quote_matches_table_row_with_pipes():
    page = "| Plant | Type | Capacity |\n|---|---|---|\n|Tjeldbergodden|Methanol plant|2,600 ton/day|82%|"
    assert contains_quote(page, "Tjeldbergodden Methanol plant 2,600 ton/day 82%")
    assert contains_quote(page, "|Tjeldbergodden|Methanol plant|2,600 ton/day|82%|")


def test_quote_is_case_and_line_break_insensitive():
    assert contains_quote("The corporate assembly\nconsists of 18 members", "the Corporate Assembly consists of 18 members")


def test_changed_number_does_not_match():
    assert not contains_quote("consists of 18 members and three observers", "consists of 19 members")


def test_empty_quote_never_matches():
    assert not contains_quote("anything", "")
    assert not contains_quote("anything", " | # ")


def test_n_words():
    assert n_words("one two  three") == 3


def test_question_overlap_worked_example():
    q = "How many members does the corporate assembly have?"
    quote = "The corporate assembly consists of 18 members and three observers"
    # question content words: many, members, corporate, assembly, have (5);
    # the quote contains members, corporate, assembly but not 'many' or 'have' -> 3/5
    assert question_overlap(q, [quote]) == 3 / 5


def test_question_overlap_extremes():
    assert question_overlap("completely different words", ["nothing shared here"]) == 0.0
    assert question_overlap("solar tower costs", ["Solar tower costs"]) == 1.0
    assert question_overlap("the of and", ["anything"]) == 0.0  # no content words
    assert question_overlap("solar", []) == 0.0


def test_numbers_in_drops_thousands_commas_and_keeps_decimals():
    from rag.evidence import numbers_in

    assert numbers_in("USD 7,366 million, up 34% from 0.043 in 2024.") == {"7366", "34", "0.043", "2024"}


def test_unsupported_numbers_ignores_question_and_quote_numbers():
    from rag.evidence import unsupported_numbers

    answer = "Sales rose from 7,366 to 8,224 in 2025, a gain of 858."
    # 7366 is in the quote, 2025 in the question; 8224 and 858 are in neither
    assert unsupported_numbers(answer, "What happened in 2025?", ["|Additions|7,366|"]) == ["8224", "858"]


def test_unsupported_numbers_is_empty_when_everything_is_quoted():
    from rag.evidence import unsupported_numbers

    assert unsupported_numbers("It is 24 hours.", "How long?", ["within 24 hours"]) == []


def test_unsupported_numbers_ignores_single_digit_list_markers():
    from rag.evidence import unsupported_numbers

    assert unsupported_numbers("(1) first, (2) second, 12 units", "Q?", ["nothing"]) == ["12"]
