"""Assign every candidate question to dev or test and write eval/splits.json.

Run: uv run python eval/make_splits.py [candidates_dir] [--force]

The file maps question id -> "dev" | "test", with the seed and ratio used. It is separate from
the question files so that editing or rejecting questions during review never reshuffles the
split. The script refuses to overwrite an existing file without --force.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from rag.splits import assign_splits, group_by_shared_passage, primary_doc, round_of

SEED = 42
DEV_RATIO = 0.3
OUT = Path("eval/splits.json")


def load(folder: Path) -> list[dict]:
    items = []
    for path in sorted(folder.glob("*.jsonl")):
        items += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return items


def show(items: list[dict], split: dict[str, str]) -> None:
    n = Counter(split.values())
    print(f"{len(items)} questions: dev {n['dev']} ({n['dev'] / len(items):.0%}), test {n['test']}")
    axes = {
        "tier": lambda i: f"round {round_of(i)}",
        "behaviour": lambda i: i["behaviour"],
        "document": primary_doc,
        "type": lambda i: i["type"],
    }
    for name, key in axes.items():
        counts = Counter((key(i), split[i["id"]]) for i in items)
        print(f"\n  by {name:<10}{'dev':>5}{'test':>6}")
        for value in sorted({k for k, _ in counts}):
            print(f"  {value:<20}{counts[(value, 'dev')]:>5}{counts[(value, 'test')]:>6}")
    straddle = sum(1 for g in group_by_shared_passage(items) if len({split[i["id"]] for i in g}) > 1)
    print(f"\npassage groups split across dev and test: {straddle} (must be 0)")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = Path(args[0] if args else "eval/candidates")
    if OUT.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} exists; the split must not change once decided. Use --force to overwrite.")
    items = load(folder)
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    split = assign_splits(items, DEV_RATIO, SEED)
    show(items, split)
    OUT.write_text(json.dumps({"seed": SEED, "dev_ratio": DEV_RATIO, "split": split}, indent=1, sort_keys=True),
                   encoding="utf-8")
    print(f"\nwritten {OUT}")


if __name__ == "__main__":
    main()
