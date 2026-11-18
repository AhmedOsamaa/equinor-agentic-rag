"""Compare two retrieval eval runs question by question (paired bootstrap per tier and mode).

Run: uv run python eval/compare_runs.py <baseline_dump.json> <new_dump.json>

Both files are results/retrieval_<split>_per_question.json from retrieval_eval.py, run on the
same questions. For each tier and mode it prints the mean difference (new - baseline) with a
95% paired bootstrap interval and the number of questions that got better or worse. A
difference is only a finding if the interval excludes 0; with this few questions most will not.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from rag.splits import round_of
from rag.stats import paired_bootstrap_diff

METRICS = ["hit@10", "coverage@10", "mrr@10", "ndcg@10"]


def main() -> None:
    base = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["per_question"]
    new = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["per_question"]
    modes = [m for m in new if m in base]
    for mode in modes:
        assert set(base[mode]) == set(new[mode]), "the two runs must cover the same questions"
    tiers: dict[int, list[str]] = defaultdict(list)
    for qid in base[modes[0]]:
        tiers[round_of({"id": qid})].append(qid)

    print("new - baseline, mean [95% paired bootstrap CI]; up/down = questions that rose/fell")
    for tier, ids in sorted(tiers.items()):
        print(f"\nround_{tier} (n = {len(ids)})")
        for mode in modes:
            for metric in METRICS:
                a = [new[mode][i][metric] for i in ids]
                b = [base[mode][i][metric] for i in ids]
                d, lo, hi = paired_bootstrap_diff(a, b)
                up = sum(x > y for x, y in zip(a, b, strict=True))
                down = sum(x < y for x, y in zip(a, b, strict=True))
                flag = "interval excludes 0" if lo > 0 or hi < 0 else ""
                print(f"  {mode:<14}{metric:<13}{d:>+7.3f} [{lo:+.3f}, {hi:+.3f}]  up {up:>2} down {down:>2}  {flag}")


if __name__ == "__main__":
    main()
