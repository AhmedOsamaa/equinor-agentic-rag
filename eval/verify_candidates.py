"""Check generated question candidates against the cleaned pages.

For every gold item: is the quote on the cited page (normalized substring)? If not, is it on
another page of the same document (the model got the page wrong) or nowhere (it altered or
invented the quote)? Also checks the schema and the 25-word cap.

This is the ONLY thing the script proves: the quotes are on the cited pages. The generators
copied from the same text, so it says nothing about whether a question is good or its answer is
right; that is the human review's job. Never call an item "verified" or "passed" because of it.

It also raises review flags (not failures) that point the reviewer at likely problems: a quote
under 4 words, a quote that occurs on several pages, and answer numbers that no quote contains.

Run: uv run python eval/verify_candidates.py [candidates_dir]
Output: a summary, the review flags, a difficulty table, and the failing items printed in full.
"""

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rag import config
from rag.evidence import (
    contains_quote,
    n_words,
    normalize,
    question_overlap,
    unsupported_numbers,
)
from rag.splits import round_of

TYPES = {"direct_fact", "numerical", "temporal", "comparative", "spanning", "relationship", "holistic"}
BEHAVIOURS = {"answerable", "unanswerable_out", "unanswerable_near", "ambiguous"}
FORMATS = {"text", "table"}
MAX_QUOTE_WORDS = 25
MIN_QUOTE_WORDS = 4  # shorter quotes match too many places to prove anything
MIN_UNSUPPORTED_NUMBERS = 2  # answer numbers in no quote before an item is flagged (1 is too noisy)
# Phrasings the generation prompt forbids; reported as warnings, they do not fail an item.
BANNED = re.compile(r"according to|in this document|the text|the table|above|below|on page|"
                    r"this report|the report states|the document|summary table|based on the", re.IGNORECASE)
TEMPLATE_OPENING = re.compile(r"^(under|according to) the [\w ]+ regulations", re.IGNORECASE)


def load_pages(doc_id: str) -> dict[int, str]:
    path = config.CLEANED_PAGES_DIR / f"{doc_id}.jsonl"
    with open(path, encoding="utf-8") as f:
        return {r["page"]: r["markdown"] for r in map(json.loads, f)}


def check_item(item: dict, pages_by_doc: dict[str, dict[int, str]]) -> list[str]:
    """Return a list of problems (empty = passed)."""
    problems = []
    if item.get("type") not in TYPES:
        problems.append(f"bad type {item.get('type')!r}")
    if item.get("behaviour") not in BEHAVIOURS:
        problems.append(f"bad behaviour {item.get('behaviour')!r}")
    if item.get("format") not in FORMATS:
        problems.append(f"bad format {item.get('format')!r}")
    gold = item.get("gold", [])
    if item.get("behaviour") == "answerable" and not gold:
        problems.append("answerable but no gold")
    if item.get("behaviour") != "answerable" and gold:
        problems.append("not answerable but has gold")
    for g in gold:
        doc, page, quote = g.get("doc_id"), g.get("page"), g.get("evidence_quote", "")
        if n_words(quote) > MAX_QUOTE_WORDS:
            problems.append(f"quote over {MAX_QUOTE_WORDS} words ({n_words(quote)}): p{page}")
        pages = pages_by_doc.get(doc)
        if pages is None:
            problems.append(f"unknown doc_id {doc!r}")
        elif page not in pages:
            problems.append(f"page {page} not in cleaned pages of {doc} (dropped or out of range)")
        elif not contains_quote(pages[page], quote):
            elsewhere = [p for p, t in pages.items() if contains_quote(t, quote)]
            where = f"found on page(s) {elsewhere}" if elsewhere else "not found anywhere in the document"
            problems.append(f"quote not on cited page {page}: {where}")
    return problems


def warnings_for(item: dict) -> list[str]:
    out = []
    if BANNED.search(item.get("question", "")):
        out.append("question uses a forbidden phrase (refers to the document or its layout)")
    if TEMPLATE_OPENING.search(item.get("question", "")):
        out.append("templated opening 'Under the ... Regulations'")
    return out


def review_flags(item: dict, pages_by_doc: dict[str, dict[int, str]]) -> list[tuple[str, str]]:
    """(kind, detail) pairs that tell the reviewer where to look. They are heuristics, not verdicts."""
    flags = []
    for g in item.get("gold", []):
        doc, page, quote = g.get("doc_id"), g.get("page"), g.get("evidence_quote", "")
        # Count on the normalized text: "|Europe|49.1|0.50|" is one word to split() but three values.
        n_tokens = len(normalize(quote).split())
        if n_tokens < MIN_QUOTE_WORDS:
            flags.append(("short quote", f"{n_tokens} words, p{page}: {quote!r}"))
        pages = pages_by_doc.get(doc, {})
        where = [p for p, t in pages.items() if contains_quote(t, quote)]
        if len(where) > 1:
            flags.append(("quote on several pages", f"{doc} pages {where}: {quote[:60]!r}"))
    if item.get("behaviour") == "answerable" and item.get("gold"):
        extra = unsupported_numbers(item.get("reference_answer", ""), item.get("question", ""),
                                    [g.get("evidence_quote", "") for g in item["gold"]])
        if len(extra) >= MIN_UNSUPPORTED_NUMBERS:
            flags.append(("answer numbers not in any quote", f"{extra} (a calculation, or invented?)"))
    return flags


def difficulty(item: dict) -> tuple[int, float] | None:
    """(number of distinct evidence pages, question/quote word overlap) for an answerable item."""
    gold = item.get("gold", [])
    if not gold:
        return None
    pages = len({(g["doc_id"], g["page"]) for g in gold})
    return pages, question_overlap(item["question"], [g["evidence_quote"] for g in gold])


def main() -> None:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/candidates")
    # File names vary (batches, cross-document files), so always load every corpus document.
    pages_by_doc = {d: load_pages(d) for d in ["equinor_ar2025", "havtil_framework", "havtil_management",
                                                "havtil_activities", "havtil_co2", "irena_rpgc2024"]}

    total = Counter()
    failures = []
    warned = []
    flagged = defaultdict(list)  # kind -> [(id, detail)]
    by_type = defaultdict(list)  # type -> [(pages, overlap)]
    for path in sorted(folder.glob("*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                failures.append((path.name, n, {"id": "?"}, [f"invalid JSON: {e}"]))
                total["items"] += 1
                total["failed"] += 1
                continue
            problems = check_item(item, pages_by_doc)
            for kind, detail in review_flags(item, pages_by_doc):
                flagged[kind].append((item.get("id"), detail))
            if w := warnings_for(item):
                warned.append((item.get("id"), item.get("question"), w))
            if d := difficulty(item):
                by_type[(round_of(item), item["type"])].append(d)
            total["items"] += 1
            total["gold_items"] += len(item.get("gold", []))
            if problems:
                total["failed"] += 1
                failures.append((path.name, n, item, problems))
            else:
                total["passed"] += 1

    print(f"items {total['items']}: quotes found on the cited page for {total['passed']}, "
          f"not for {total['failed']} (gold quotes checked: {total['gold_items']})")
    print("This proves only that quotes are on the cited pages, not that a question is good.")
    n_flagged = len({i for rows in flagged.values() for i, _ in rows})
    print(f"\nreview flags (heuristics, not failures): {n_flagged} items flagged")
    for kind, rows in sorted(flagged.items()):
        print(f"  {kind}: {len(rows)}")
        for id_, detail in rows:
            print(f"    {id_}: {detail}")
    print(f"\nwarnings (not failures): {len(warned)}")
    for id_, q, w in warned:
        print(f"  {id_}: {'; '.join(w)}\n    Q: {q}")
    print("\nDifficulty of answerable items (a property of the question, not a retrieval result):")
    def row(label: str, rows: list[tuple[int, float]]) -> None:
        one = sum(1 for p, _ in rows if p == 1)
        print(f"  {label:<13}{len(rows):>4}{one:>8}{len(rows) - one:>10}{statistics.mean(o for _, o in rows):>14.2f}")

    for rnd in (1, 2, 3):
        print(f"\n  round {rnd}\n  {'type':<13}{'n':>4}{'1 page':>8}{'2+ pages':>10}{'mean overlap':>14}")
        for (r, t), rows in sorted(by_type.items()):
            if r == rnd:
                row(t, rows)
        round_rows = [x for (r, _), rows in by_type.items() if r == rnd for x in rows]
        if round_rows:
            row("all", round_rows)
    for fname, n, item, problems in failures:
        print(f"\n{fname}:{n}  {item.get('id')}  [{item.get('type')}/{item.get('behaviour')}]")
        print(f"  Q: {item.get('question')}")
        for p in problems:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
