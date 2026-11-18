"""Draw the audit sample: accepted-by-the-pre-screen questions that a human reviewer reads.

Run: uv run python eval/draw_sample.py [--n 20] [--seed 42] [--force]

Why: the advisory pre-screen (a language model) accepted most questions, and a model checking
model-written questions is not independent. Reading a random sample of its accepts measures how
often it misses a problem, which is the only evidence for accepting the rest. The sample is drawn
once, with a fixed seed, from the pre-screen accepts that have no decision in the log yet, and
saved to eval/accept_sample.json; the script refuses to redraw without --force, because redrawing
after seeing results would let us pick a convenient sample.

What the sample can show: with n reads and k problems found, k/n is the pre-screen's miss rate
among its accepts. With n = 20 the interval is wide (0 problems in 20 still allows a true rate of
about 15%, the "rule of three": 3/n at 95%), so report n and k, never "the pre-screen is reliable".
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

from rag.review import draw_sample, latest_decisions, read_log
from rag.splits import round_of

OUT = Path("eval/accept_sample.json")


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} exists; the sample must not be redrawn after results are known. Use --force to overwrite.")
    n, seed = int(option("--n", "20")), int(option("--seed", "42"))
    with open("eval/prescreen_suggestions.csv", encoding="utf-8-sig", newline="") as f:
        accepts = [r["id"] for r in csv.DictReader(f) if r["suggestion"] == "accept"]
    decided = latest_decisions(read_log(Path("eval/review_log.jsonl")))
    population = [i for i in accepts if i not in decided]
    ids = draw_sample(population, n, seed)
    OUT.write_text(json.dumps({"seed": seed, "n": n, "population_size": len(population),
                               "population": "pre-screen accepts with no decision in the log when drawn",
                               "ids": ids}, indent=1), encoding="utf-8")
    mix = Counter(round_of({"id": i}) for i in ids)
    print(f"drew {n} of {len(population)} (seed {seed}); by round: {dict(sorted(mix.items()))}")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
