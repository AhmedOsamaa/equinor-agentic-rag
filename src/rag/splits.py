"""Assign eval questions to `dev` and `test`.

Rules (evaluation design):
- Stratified by (tier, answerable or not, document), so both splits have the same mix.
- Questions about the same passage stay together (same document and page, and evidence quotes
  that overlap), so tuning on `dev` cannot leak into `test` through a shared sentence. Sharing
  a page alone is not enough to link: the Havtil documents have 8 to 39 pages each, so linking
  on page would chain almost all their questions into one group.
- Deterministic: the same ids and seed always give the same split.
"""

import random
import re
from collections import defaultdict

from rag.evidence import normalize

QUOTE_OVERLAP = 0.5  # word-set Jaccard on the same page at or above which two quotes count as one passage


def round_of(item: dict) -> int:
    """Tier from the id number: 001-099 round 1, 101-299 round 2, 301 and up round 3 (Claude subagent)."""
    m = re.search(r"(\d+)$", item.get("id", ""))
    n = int(m.group(1)) if m else 0
    return 3 if n >= 300 else 2 if n >= 100 else 1


def primary_doc(item: dict) -> str:
    """First gold document, or the id prefix for items without gold (unanswerable, ambiguous)."""
    if item.get("gold"):
        return item["gold"][0]["doc_id"]
    return item["id"].rsplit("-", 1)[0]


def stratum(item: dict) -> tuple[int, bool, str]:
    return round_of(item), item.get("behaviour") == "answerable", primary_doc(item)


def _words(quote: str) -> set[str]:
    return set(normalize(quote).split())


def _same_passage(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= QUOTE_OVERLAP


def group_by_shared_passage(items: list[dict]) -> list[list[dict]]:
    """Union-find: two items are linked if they cite overlapping quotes on the same (doc, page)."""
    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen: dict[tuple[str, int], list[tuple[int, str]]] = defaultdict(list)  # (doc, page) -> [(item idx, quote)]
    for idx, item in enumerate(items):
        for g in item.get("gold", []):
            key = (g["doc_id"], g["page"])
            for other_idx, other_quote in seen[key]:
                if _same_passage(g["evidence_quote"], other_quote):
                    parent[find(idx)] = find(other_idx)
            seen[key].append((idx, g["evidence_quote"]))
    groups: dict[int, list[dict]] = defaultdict(list)
    for idx, item in enumerate(items):
        groups[find(idx)].append(item)
    return list(groups.values())


def assign_splits(items: list[dict], dev_ratio: float = 0.3, seed: int = 42) -> dict[str, str]:
    """Return {question id: "dev" | "test"}."""
    by_stratum: dict[tuple, list[list[dict]]] = defaultdict(list)
    for group in group_by_shared_passage(items):
        by_stratum[stratum(group[0])].append(group)

    rng = random.Random(seed)
    result: dict[str, str] = {}
    carry = 0.0  # fractional dev quota carried to the next stratum, so small strata do not all round down
    for key in sorted(by_stratum):
        groups = sorted(by_stratum[key], key=lambda g: g[0]["id"])  # fixed order before the seeded shuffle
        rng.shuffle(groups)
        n_items = sum(len(g) for g in groups)
        exact = dev_ratio * n_items + carry
        target = max(0, round(exact))
        carry = exact - target
        dev_count = 0
        for group in groups:
            to_dev = dev_count < target
            for item in group:
                result[item["id"]] = "dev" if to_dev else "test"
            if to_dev:
                dev_count += len(group)
    return result
