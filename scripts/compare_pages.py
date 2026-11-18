"""Compare two folders of per-page jsonl files (e.g. an old and a new parse).

For every document and page it reports whether the markdown is identical. For pages that
differ it says whether only the ORDER of lines changed (same lines, same count) or the
content changed, and how large the change is.

Run: uv run python scripts/compare_pages.py OLD_DIR NEW_DIR [--show N]
"""

import argparse
import difflib
import json
from collections import Counter
from pathlib import Path


def load(path: Path) -> dict[int, str]:
    with open(path, encoding="utf-8") as f:
        return {r["page"]: r["markdown"] for r in map(json.loads, f)}


def lines_of(md: str) -> list[str]:
    return [line.strip() for line in md.splitlines() if line.strip()]


def classify(old: str, new: str) -> str:
    if old == new:
        return "identical"
    if Counter(lines_of(old)) == Counter(lines_of(new)):
        return "order_only"  # same lines, different order (or only blank lines changed)
    return "content_changed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("old_dir", type=Path)
    parser.add_argument("new_dir", type=Path)
    parser.add_argument("--show", type=int, default=5, help="max differing pages to detail per document")
    args = parser.parse_args()

    grand = Counter()
    for old_path in sorted(args.old_dir.glob("*.jsonl")):
        new_path = args.new_dir / old_path.name
        if not new_path.exists():
            print(f"{old_path.stem}: MISSING in {args.new_dir}")
            continue
        old, new = load(old_path), load(new_path)
        counts = Counter()
        details = []
        for page in sorted(set(old) | set(new)):
            if page not in new:
                counts["only_in_old"] += 1
                details.append((page, "only_in_old", 0, 0))
            elif page not in old:
                counts["only_in_new"] += 1
                details.append((page, "only_in_new", 0, 0))
            else:
                kind = classify(old[page], new[page])
                counts[kind] += 1
                if kind != "identical":
                    details.append((page, kind, len(old[page]), len(new[page])))
        grand.update(counts)
        summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        print(f"\n{old_path.stem}: {len(old)} old pages, {len(new)} new pages -> {summary}")
        for page, kind, n_old, n_new in details[: args.show]:
            ratio = difflib.SequenceMatcher(None, lines_of(old.get(page, "")), lines_of(new.get(page, ""))).ratio()
            print(f"    p{page}: {kind}, chars {n_old} -> {n_new} ({n_new - n_old:+d}), line-sequence similarity {ratio:.2f}")
        if len(details) > args.show:
            print(f"    ... and {len(details) - args.show} more differing pages: {[d[0] for d in details[args.show:]]}")
    print("\nTOTAL:", dict(grand))


if __name__ == "__main__":
    main()
