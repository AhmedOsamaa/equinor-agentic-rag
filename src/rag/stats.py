"""Bootstrap confidence intervals for per-question metric scores.

We only have ~60 dev questions, so a mean alone says nothing about whether two configurations
really differ. The bootstrap resamples the questions we have (with replacement) many times and
looks at how much the mean moves.
"""

import numpy as np

from rag import config


def _percentile_interval(values: np.ndarray, ci: float) -> tuple[float, float]:
    tail = (1 - ci) / 2 * 100
    lo, hi = np.percentile(values, [tail, 100 - tail])
    return float(lo), float(hi)


def bootstrap_ci(
    scores: list[float],
    n_resamples: int = config.BOOTSTRAP_RESAMPLES,
    ci: float = config.BOOTSTRAP_CI,
    seed: int = config.BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Return (mean, low, high): the mean score and its percentile bootstrap interval."""
    x = np.asarray(scores, dtype=float)
    if x.size == 0:
        raise ValueError("no scores")
    rng = np.random.default_rng(seed)
    # One row per resample, each row is n question indices drawn with replacement.
    idx = rng.integers(0, x.size, size=(n_resamples, x.size))
    lo, hi = _percentile_interval(x[idx].mean(axis=1), ci)
    return float(x.mean()), lo, hi


def paired_bootstrap_diff(
    scores_a: list[float],
    scores_b: list[float],
    n_resamples: int = config.BOOTSTRAP_RESAMPLES,
    ci: float = config.BOOTSTRAP_CI,
    seed: int = config.BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Return (mean of a - b, low, high) for two configurations run on the same questions.

    The same resampled question indices are used for both, because a hard question is hard for
    both configurations; resampling them independently would add noise that is not there.
    If the interval contains 0, do not claim a difference.
    """
    a = np.asarray(scores_a, dtype=float)
    b = np.asarray(scores_b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("paired scores must have the same length (same questions, same order)")
    if a.size == 0:
        raise ValueError("no scores")
    diff = a - b
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, diff.size, size=(n_resamples, diff.size))
    lo, hi = _percentile_interval(diff[idx].mean(axis=1), ci)
    return float(diff.mean()), lo, hi
