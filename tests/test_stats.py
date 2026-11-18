import pytest

from rag.stats import bootstrap_ci, paired_bootstrap_diff


def test_mean_is_the_plain_mean():
    mean, _, _ = bootstrap_ci([1, 0, 0.5, 0, 1])
    assert mean == pytest.approx(0.5)


def test_identical_scores_give_zero_width_interval():
    mean, lo, hi = bootstrap_ci([0.7] * 20)
    assert (mean, lo, hi) == pytest.approx((0.7, 0.7, 0.7))


def test_interval_contains_the_mean_and_stays_in_the_data_range():
    scores = [0, 1, 0, 1, 1, 0, 0.5, 1]
    mean, lo, hi = bootstrap_ci(scores)
    assert lo <= mean <= hi
    assert 0 <= lo and hi <= 1


def test_more_questions_give_a_narrower_interval():
    small = [0, 1] * 5
    large = [0, 1] * 50
    _, lo_s, hi_s = bootstrap_ci(small)
    _, lo_l, hi_l = bootstrap_ci(large)
    assert (hi_l - lo_l) < (hi_s - lo_s)


def test_same_seed_gives_the_same_interval():
    scores = [0, 1, 0.5, 0.25, 1, 0]
    assert bootstrap_ci(scores) == bootstrap_ci(scores)


def test_clear_paired_difference_excludes_zero():
    b = [0.1, 0.2, 0.0, 0.3, 0.1, 0.2, 0.1, 0.0, 0.2, 0.1]
    a = [x + 0.3 for x in b]  # a is better on every question
    diff, lo, _hi = paired_bootstrap_diff(a, b)
    assert diff == pytest.approx(0.3)
    assert lo > 0


def test_mixed_difference_includes_zero():
    a = [1, 0, 1, 0, 1, 0, 1, 0]
    b = [0, 1, 0, 1, 0, 1, 0, 1]  # a wins half the questions, b the other half
    diff, lo, hi = paired_bootstrap_diff(a, b)
    assert diff == pytest.approx(0.0)
    assert lo < 0 < hi


def test_paired_rejects_different_lengths():
    with pytest.raises(ValueError):
        paired_bootstrap_diff([1, 0], [1])
