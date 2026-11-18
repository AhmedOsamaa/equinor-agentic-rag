from rag.splits import assign_splits, group_by_shared_passage, round_of


def item(id_, doc="doc_a", page=1, behaviour="answerable", quote=None):
    # each item gets its own distinct quote unless one is given, so sharing a page does not link items
    quote = quote or f"{id_}-alpha {id_}-beta {id_}-gamma {id_}-delta"  # no words shared with other items
    gold = [{"doc_id": doc, "page": page, "evidence_quote": quote}] if behaviour == "answerable" else []
    return {"id": id_, "behaviour": behaviour, "gold": gold}


def test_round_of():
    assert [round_of({"id": i}) for i in ("a-001", "a-099", "a-101", "a-299", "a-301", "cross-305")] == [1, 1, 2, 2, 3, 3]


def test_same_page_different_quotes_are_not_linked():
    items = [item("a-001", page=5), item("a-002", page=5), item("a-003", page=5)]
    assert len(group_by_shared_passage(items)) == 3


def test_same_quote_on_same_page_is_linked():
    q = "The first version of the plan shall be available no later than two hours"
    items = [item("a-001", page=5, quote=q), item("a-002", page=5, quote=q), item("a-003", page=9, quote=q)]
    groups = sorted(sorted(i["id"] for i in g) for g in group_by_shared_passage(items))
    assert groups == [["a-001", "a-002"], ["a-003"]]  # a-003 is on another page, so not linked


def test_overlapping_quotes_link_but_disjoint_ones_do_not():
    items = [
        item("a-001", quote="shall be available no later than two hours after the action management"),
        item("a-002", quote="no later than two hours after the action management has been established"),
        item("a-003", quote="completely different sentence about waste tonnes"),
    ]
    groups = sorted(sorted(i["id"] for i in g) for g in group_by_shared_passage(items))
    assert groups == [["a-001", "a-002"], ["a-003"]]


def test_chained_links_merge_transitively():
    shared = "alpha beta gamma delta epsilon"
    two = item("a-002", page=1, quote=shared)
    two["gold"].append({"doc_id": "doc_a", "page": 2, "evidence_quote": "zeta eta theta iota kappa"})
    items = [item("a-001", page=1, quote=shared), two, item("a-003", page=2, quote="zeta eta theta iota kappa")]
    assert len(group_by_shared_passage(items)) == 1


def test_same_page_number_in_different_documents_is_not_shared():
    q = "identical words in two documents"
    groups = group_by_shared_passage([item("a-001", doc="doc_a", page=3, quote=q), item("b-001", doc="doc_b", page=3, quote=q)])
    assert len(groups) == 2


def test_items_without_gold_are_their_own_group():
    items = [item("a-001", behaviour="unanswerable_near"), item("a-002", behaviour="ambiguous")]
    assert len(group_by_shared_passage(items)) == 2


def test_no_group_straddles_the_split():
    q = ["linked sentence one", "linked sentence two", "linked sentence three"]
    items = [item(f"a-{n:03d}", page=n % 7, quote=q[n % 3] if n % 4 == 0 else None) for n in range(1, 60)]
    split = assign_splits(items, 0.3, seed=1)
    for group in group_by_shared_passage(items):
        assert len({split[i["id"]] for i in group}) == 1


def test_deterministic_and_seed_dependent():
    items = [item(f"a-{n:03d}", page=n) for n in range(1, 50)]
    assert assign_splits(items, 0.3, seed=7) == assign_splits(items, 0.3, seed=7)
    assert assign_splits(items, 0.3, seed=7) != assign_splits(items, 0.3, seed=8)


def test_ratio_is_close_to_target_overall():
    items = [item(f"a-{n:03d}", page=n) for n in range(1, 101)]
    split = assign_splits(items, 0.3, seed=3)
    assert sum(v == "dev" for v in split.values()) == 30


def test_every_stratum_with_enough_items_appears_in_both_splits():
    items = [item(f"a-{n:03d}", page=n) for n in range(1, 21)]  # tier 1 answerable doc_a
    items += [item(f"a-{n:03d}", behaviour="unanswerable_near") for n in range(21, 31)]
    items += [item(f"a-{n:03d}", doc="doc_b", page=n) for n in range(31, 41)]
    split = assign_splits(items, 0.3, seed=0)
    for pred in (lambda i: i["behaviour"] != "answerable", lambda i: i["gold"] and i["gold"][0]["doc_id"] == "doc_b"):
        values = {split[i["id"]] for i in items if pred(i)}
        assert values == {"dev", "test"}


def test_small_strata_do_not_all_round_down():
    # 10 strata of 3 items each: plain rounding of 0.9 would give 1 dev item each (10), the carry keeps 9
    items = []
    for s in range(10):
        items += [item(f"d{s}-{n:03d}", doc=f"doc_{s}", page=n) for n in range(1, 4)]
    split = assign_splits(items, 0.3, seed=2)
    assert sum(v == "dev" for v in split.values()) == 9
