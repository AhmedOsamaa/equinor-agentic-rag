import pytest

from rag.review import (
    SHEET_COLUMNS,
    append_log,
    apply_edit,
    build_questions,
    decision_from_row,
    draw_sample,
    drop_gold,
    latest_decisions,
    read_log,
    review_order,
    sheet_rows,
    summary,
    unsaved_input,
)


def item(id_, **kw):
    return {"id": id_, "question": "Q?", "reference_answer": "A", "gold": [{"doc_id": "d", "page": 1, "evidence_quote": "x y z w"}],
            **kw}


SPLITS = {"a-001": "dev", "a-002": "dev", "a-003": "test", "a-101": "dev", "a-301": "dev"}
ITEMS = [item(i) for i in SPLITS]


def test_latest_decision_wins():
    log = [{"id": "a-001", "decision": "reject", "reason": "bad"}, {"id": "a-001", "decision": "accept"}]
    assert latest_decisions(log)["a-001"]["decision"] == "accept"


def test_order_puts_defects_then_flagged_then_rest_and_filters_split():
    out = review_order(ITEMS, SPLITS, "dev", flagged={"a-002"}, defects={"a-301"})
    assert [i["id"] for i in out] == ["a-301", "a-002", "a-001", "a-101"]  # a-003 is test
    assert len(review_order(ITEMS, SPLITS, "all", set(), set())) == 5


def test_apply_edit_changes_a_copy_only():
    original = item("a-001")
    edited = apply_edit(original, "question", "New?")
    assert edited["question"] == "New?" and original["question"] == "Q?"
    with pytest.raises(ValueError):
        apply_edit(original, "gold", "x")


def test_drop_gold_removes_one_entry_from_a_copy():
    original = item("a-001")
    original["gold"].append({"doc_id": "e", "page": 2, "evidence_quote": "p q r s"})
    out = drop_gold(original, 0)
    assert [g["doc_id"] for g in out["gold"]] == ["e"] and len(original["gold"]) == 2
    with pytest.raises(ValueError):
        drop_gold(original, 5)


def test_build_questions_keeps_accepted_and_edited_only_with_split_and_status():
    edited = apply_edit(item("a-002"), "question", "Edited?")
    decisions = {
        "a-001": {"id": "a-001", "decision": "accept"},
        "a-002": {"id": "a-002", "decision": "edit", "item": edited},
        "a-003": {"id": "a-003", "decision": "reject", "reason": "defect"},
    }  # a-101 and a-301 are not decided yet
    out = build_questions(ITEMS, decisions, SPLITS)
    assert [q["id"] for q in out] == ["a-001", "a-002"]
    assert out[1]["question"] == "Edited?" and out[1]["review"]["status"] == "edited"
    assert out[0]["split"] == "dev" and out[0]["review"]["status"] == "accepted"


def test_summary_counts_per_tier_and_rate():
    decisions = {
        "a-001": {"id": "a-001", "decision": "accept"},
        "a-002": {"id": "a-002", "decision": "reject", "reason": "false premise"},
        "a-101": {"id": "a-101", "decision": "edit"},
        "a-301": {"id": "a-301", "decision": "reject", "reason": "false premise"},
    }
    s = summary(ITEMS, decisions)
    assert s["tiers"]["round_1"] == {"reviewed": 2, "accept": 1, "edit": 0, "reject": 1, "rejection_rate": 0.5}
    assert s["tiers"]["round_2"]["edit"] == 1 and s["tiers"]["round_3"]["rejection_rate"] == 1.0
    assert s["tiers"]["all"]["reviewed"] == 4 and s["tiers"]["all"]["rejection_rate"] == 0.5
    assert s["reject_reasons"] == {"false premise": 2}


def test_log_round_trip_appends(tmp_path):
    path = tmp_path / "log.jsonl"
    assert read_log(path) == []
    append_log(path, {"id": "a-001", "decision": "accept"})
    append_log(path, {"id": "a-002", "decision": "reject", "reason": "ü"})
    log = read_log(path)
    assert [r["id"] for r in log] == ["a-001", "a-002"] and "time" in log[0] and log[1]["reason"] == "ü"


# ---- spreadsheet round trip


def full_item():
    return {"id": "a-001", "question": "Q?", "reference_answer": "A", "type": "numerical", "format": "text",
            "behaviour": "answerable",
            "gold": [{"doc_id": "d1", "page": 3, "evidence_quote": "first quote here ok"},
                     {"doc_id": "d2", "page": 9, "evidence_quote": "second quote here ok"}]}


def test_sheet_rows_have_all_columns_and_show_gold_defect_flags_and_prior_decision():
    rows = sheet_rows([full_item()], {"a-001": "dev"}, {"a-001": "known problem"}, {"a-001": ["short quote: x"]},
                      {"a-001": {"id": "a-001", "decision": "reject", "reason": "bad"}})
    r = rows[0]
    assert set(r) == set(SHEET_COLUMNS)
    assert r["gold_1"] == "d1 p3: first quote here ok" and r["gold_3"] == ""
    assert r["known_defect"] == "known problem" and r["flags"] == "short quote: x" and r["tier"] == 1
    assert (r["decision"], r["reason"]) == ("reject", "bad")


def test_blank_decision_is_undecided():
    assert decision_from_row({"decision": "  "}, full_item()) is None


def test_accept_and_reject_rows():
    assert decision_from_row({"decision": "A"}, full_item()) == {"id": "a-001", "decision": "accept"}
    assert decision_from_row({"decision": "reject", "reason": "false premise"}, full_item())["reason"] == "false premise"
    with pytest.raises(ValueError, match="needs a reason"):
        decision_from_row({"decision": "reject", "reason": ""}, full_item())


def test_unknown_decision_word_is_an_error():
    with pytest.raises(ValueError, match="not accept"):
        decision_from_row({"decision": "maybe"}, full_item())


def test_edit_applies_new_fields_and_drops_gold_counted_from_one():
    row = {"decision": "edit", "new_question": "New?", "new_type": "comparative", "drop_gold": "1"}
    rec = decision_from_row(row, full_item())
    assert rec["decision"] == "edit" and rec["item"]["question"] == "New?" and rec["item"]["type"] == "comparative"
    assert [g["doc_id"] for g in rec["item"]["gold"]] == ["d2"]
    assert rec["reason"] == "edited in the sheet"


def test_edit_can_drop_several_gold_entries_in_any_order():
    row = {"decision": "edit", "drop_gold": "2, 1"}
    assert decision_from_row(row, full_item())["item"]["gold"] == []


def test_edit_without_any_change_or_with_a_missing_gold_number_is_an_error():
    with pytest.raises(ValueError, match="no new_"):
        decision_from_row({"decision": "edit"}, full_item())
    with pytest.raises(ValueError, match="drop_gold 5: this question has 2 gold entries"):
        decision_from_row({"decision": "edit", "drop_gold": "5"}, full_item())


def test_prescreen_is_shown_but_never_fills_the_decision():
    ps = {"a-001": {"suggestion": "reject", "category": "false-premise", "reason": "four wells include Argentina"}}
    r = sheet_rows([full_item()], {"a-001": "dev"}, {}, {}, {}, ps)[0]
    assert r["prescreen"] == "reject: false-premise" and r["prescreen_reason"] == "four wells include Argentina"
    assert r["decision"] == "" and r["reason"] == ""
    assert sheet_rows([full_item()], {"a-001": "dev"}, {}, {}, {})[0]["prescreen"] == ""


def test_unsaved_input_finds_work_a_reexport_would_destroy():
    new = [{"id": "a-001", "decision": "", "reason": ""}, {"id": "a-002", "decision": "accept", "reason": ""}]
    existing = [{"id": "a-001", "decision": "reject", "reason": "x"},   # typed, not in the log: would be lost
                {"id": "a-002", "decision": "accept", "reason": ""}]    # same as the log: fine
    assert unsaved_input(existing, new) == ["a-001"]
    assert unsaved_input([{"id": "a-001", "decision": "", "reason": ""}], new) == []


def test_draw_sample_is_reproducible_sorted_and_the_right_size():
    ids = [f"q-{n:03d}" for n in range(50)]
    a, b = draw_sample(ids, 10, 42), draw_sample(list(reversed(ids)), 10, 42)
    assert a == b and a == sorted(a) and len(set(a)) == 10 and set(a) <= set(ids)
    assert draw_sample(ids, 10, 7) != a
    with pytest.raises(ValueError):
        draw_sample(ids, 51, 42)


def test_review_order_puts_the_audit_sample_after_flagged_and_before_the_rest():
    out = review_order(ITEMS, SPLITS, "dev", flagged={"a-002"}, defects={"a-301"}, sample={"a-101"})
    assert [i["id"] for i in out] == ["a-301", "a-002", "a-101", "a-001"]


def test_sheet_marks_the_audit_sample():
    rows = sheet_rows([full_item()], {"a-001": "dev"}, {}, {}, {}, None, {"a-001"})
    assert rows[0]["sample"].startswith("READ THIS ONE")
    assert sheet_rows([full_item()], {"a-001": "dev"}, {}, {}, {})[0]["sample"] == ""
