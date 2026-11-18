"""Unit tests for the cleaning rules. Each case is a small example of a real problem seen
in the parsed pages."""

from collections import Counter

from rag.clean import clean_markdown, flag_page, real_text


def test_bold_markers_and_split_digits_are_removed_and_thousands_joined():
    # IRENA p71 shape: bold splits "1 333" into two bold pieces.
    md = "|Africa|1 834|**1** **333**|1 435|"
    assert clean_markdown(md, "irena_rpgc2024") == "|Africa|1834|1333|1435|"


def test_thousands_only_joined_for_configured_document():
    # Equinor uses commas; a space-separated pair there is not a number.
    assert clean_markdown("Table 3 100 projects", "equinor_ar2025") == "Table 3 100 projects"


def test_multi_group_runs_are_left_alone_because_they_may_be_separate_values():
    stats = Counter()
    out = clean_markdown("110 110 109", "irena_rpgc2024", stats)
    assert out == "110 110 109"
    assert stats["thousands_skipped_ambiguous"] == 1


def test_decimals_and_years_are_not_joined():
    assert clean_markdown("0.450 0.417 and 2010 2024", "irena_rpgc2024") == "0.450 0.417 and 2010 2024"
    assert clean_markdown("USD 2.5 100", "irena_rpgc2024") == "USD 2.5 100"


def test_sup_and_br_tags_removed_text_kept():
    assert clean_markdown("Interest paid<sup>3)</sup>", "equinor_ar2025") == "Interest paid3)"
    assert clean_markdown("|a<br>b|c|", "equinor_ar2025") == "|a b|c|"


def test_picture_text_dropped_for_irena_but_kept_for_equinor():
    md = "Intro\n<!-- Start of picture text -->\n0.450<br>0.417<br>\n<!-- End of picture text -->\nOutro"
    assert "0.450" not in clean_markdown(md, "irena_rpgc2024")
    kept = clean_markdown(md, "equinor_ar2025")
    assert "0.450 0.417" in kept and "<!--" not in kept


def test_nav_lines_removed_but_headings_and_tables_survive():
    md = "ABOUT US\n# ABOUT US\nOUR PERFORMANCE\n|OUR|PERFORMANCE|\nReal text"
    assert clean_markdown(md, "equinor_ar2025") == "# ABOUT US\n|OUR|PERFORMANCE|\nReal text"


def test_nav_rule_not_applied_to_other_documents():
    assert clean_markdown("CONTENTS", "havtil_activities") == "CONTENTS"


def test_ligature_glyph_becomes_ti_with_exceptions():
    md = "Sec�on 7 a�er the facili�es. A�erwards, aircra� and fi�h."
    out = clean_markdown(md, "havtil_framework")
    assert out == "Section 7 after the facilities. Afterwards, aircraft and fifth."


def test_replacement_char_left_alone_in_other_documents():
    assert "�" in clean_markdown("a�b", "irena_rpgc2024")


def test_blank_line_runs_collapse_but_paragraph_break_stays():
    assert clean_markdown("one  \n\n\n\n\ntwo\n\nthree", "havtil_activities") == "one\n\ntwo\n\nthree"


def test_headings_and_table_pipes_are_kept_for_the_chunker():
    md = "# **Section 7**\n|a|b|\n|---|---|\n|1|2|"
    assert clean_markdown(md, "havtil_management") == "# Section 7\n|a|b|\n|---|---|\n|1|2|"


# ---- flag detector -----------------------------------------------------------------

def test_flags_cover_empty_short_and_leader_pages():
    assert "cover" in flag_page("Some cover " * 50, page=1)[0]
    assert flag_page("", page=13)[0] == ["empty"]
    assert flag_page("# 02<sup>**ONSHORE**</sup> **WIND**", page=62)[0] == ["short"]
    toc = "\n".join(f"Section {i} Scope ........ {i}" for i in range(6)) + "\n" + "text " * 100
    assert "toc_leaders" in flag_page(toc, page=2)[0]
    spaced = "|Figure 5.6|Reduction . . . . . . . . . . 138|\n" * 4 + "text " * 100
    assert "toc_leaders" in flag_page(spaced, page=9)[0]


def test_real_page_without_markers_is_not_flagged():
    assert flag_page("A normal paragraph of regulations text. " * 20, page=5)[0] == []


def test_real_text_strips_markup():
    assert real_text("# **Hi**<sup>1</sup> <!-- x --> there |") == "Hi 1 there"


# ---- header rejoin: the parser cuts a spanning header cell at character positions ----
from rag.clean import build_vocab, rejoin_header_row, rejoin_split_headers  # noqa: E402

VOCAB = {"levelised", "electricity", "capacity", "december", "people", "total", "installed", "costs", "factor"}


def test_a_word_cut_in_two_is_rejoined_and_the_column_count_is_kept():
    row = "||Total|installed|costs|Ca|pacity fac|tor|Levelise|d cost of e|lectricity|"
    out = rejoin_header_row(row, VOCAB, Counter())
    assert "Levelised cost of electricity" in out and "Capacity factor" in out
    assert out.count("|") == row.count("|")   # absorbed cells became empty, nothing was removed


def test_whole_words_in_neighbouring_cells_are_left_alone():
    # "Total|installed|costs" are three real words from one merged cell: gluing them would break the search match.
    row = "||Total|installed|costs|"
    assert rejoin_header_row(row, VOCAB, Counter()) == row


def test_two_whole_words_are_not_glued_even_if_the_result_is_a_word():
    assert rejoin_header_row("|Net|work|", {"network", "net", "work"}, Counter()) == "|Net|work|"


def test_an_open_bracket_pulls_in_the_cells_that_close_it():
    row = "||(20|24 USD/k|W)||(%)|"
    out = rejoin_header_row(row, VOCAB, Counter())
    assert out == "||(2024 USD/kW)||||(%)|"
    assert out.count("|") == row.count("|")


def test_only_the_first_lines_of_a_table_are_touched_never_the_data_rows():
    md = "|Pe|ople|\n|---|---|\n|x|y|\n|Pe|ople|\n\ntext"
    out = rejoin_split_headers(md, VOCAB, Counter())
    lines = out.split("\n")
    assert lines[0] == "|People||"          # header row repaired
    assert lines[3] == "|Pe|ople|"          # fourth table line is a data row: unchanged


def test_vocab_counts_prose_words_only_not_table_cells():
    md = "Levelised cost of electricity. Levelised again, levelised once more.\n|Zzz|Zzz|Zzz|Zzz|"
    v = build_vocab([md])
    assert "levelised" in v and "zzz" not in v
