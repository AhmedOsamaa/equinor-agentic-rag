"""Cleaning stage, between parse and chunk.

Step 1, `flag`: flag pages that are probably not worth chunking and write them to
pages_to_drop.yaml for approval. Nothing is dropped by this step.

Step 2, `run`: drop the approved pages and clean the markdown of the rest, writing
data/pages_clean/<doc_id>.jsonl. Cleaning keeps headings (#) and table pipes (|), which
the chunker needs; it only removes noise. Page numbers are never renumbered.

Flags (a page can have several):
  empty        almost no real text (blank pages)
  cover        page 1 of a document (always listed: some covers have more text than `short`)
  short        little real text (covers, chapter dividers, a lone heading)
  toc_leaders  dot leaders "Section 1 Scope ...... 11" or ". . . . 11" (tables of contents,
               lists of figures / tables)
  toc_heading  the page starts with a "Contents" / "List of ..." heading

The detector favours recall: a false flag costs the reviewer one glance, a missed contents
page puts duplicated section titles into the index. The reviewer's `approved` answers are
kept when the detector is re-run.

Run: uv run python -m rag.clean flag   |   uv run python -m rag.clean run
"""

import argparse
import json
import re
from collections import Counter

import yaml

from rag import config

LEADER = re.compile(r"(?:\.\s?){5,}")
CONTENTS_HEADING = re.compile(r"^(table of contents|contents|list of (figures|tables|boxes)[a-z ,]*)$", re.IGNORECASE)


def real_text(markdown: str) -> str:
    """Only the words: markdown syntax, html tags and comments removed, whitespace collapsed."""
    text = re.sub(r"<!--.*?-->", " ", markdown, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_#>|`]|-{3,}", " ", text)
    return " ".join(text.split())


def first_heading_text(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = re.sub(r"[*_#>|`]", "", line).strip()
        if stripped:
            return stripped
    return ""


def flag_page(markdown: str, page: int) -> tuple[list[str], int, str]:
    """Return (flags, number of real characters, 60-character preview)."""
    text = real_text(markdown)
    flags = []
    if page == 1:
        flags.append("cover")
    if len(text) < config.FLAG_EMPTY_CHARS:
        flags.append("empty")
    elif len(text) < config.FLAG_SHORT_CHARS:
        flags.append("short")
    if len(LEADER.findall(markdown)) >= config.FLAG_LEADER_RUNS:
        flags.append("toc_leaders")
    if CONTENTS_HEADING.match(first_heading_text(markdown)):
        flags.append("toc_heading")
    return flags, len(text), text[:60]


def flag_all() -> dict[str, list[dict]]:
    flagged: dict[str, list[dict]] = {}
    for path in sorted(config.PAGES_DIR.glob("*.jsonl")):
        entries = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                flags, n_real, preview = flag_page(rec["markdown"], rec["page"])
                if flags:
                    entries.append({"page": rec["page"], "flags": flags, "real_chars": n_real,
                                    "preview": preview, "approved": False, "note": ""})
        flagged[path.stem] = entries
    return flagged


def merge_previous(flagged: dict[str, list[dict]]) -> list[str]:
    """Keep the reviewer's `approved` / `note` from an existing yaml. Returns messages."""
    messages = []
    path = config.PAGES_TO_DROP_YAML
    if not path.exists():
        return messages
    old = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for doc_id, entries in flagged.items():
        previous = {e["page"]: e for e in old.get(doc_id) or []}
        for e in entries:
            if e["page"] in previous:
                e["approved"] = previous[e["page"]].get("approved", False)
                e["note"] = previous[e["page"]].get("note", "")
        gone = set(previous) - {e["page"] for e in entries}
        for page in sorted(gone):
            if previous[page].get("approved"):
                messages.append(f"WARNING {doc_id} p{page} was approved but is no longer flagged (kept out of file)")
    return messages


HEADER = """\
# Pages proposed for removal before chunking. Written by `python -m rag.clean flag`.
# Review each entry, then set `approved: true` to drop that page. Add a `note` if useful.
# Re-running the detector keeps your approved / note values. Nothing is dropped until approved.
# Page numbers are PDF pages (1-based), the same as in data/pages and in gold labels.
"""


def write_yaml(flagged: dict[str, list[dict]]) -> None:
    body = yaml.safe_dump(flagged, sort_keys=False, allow_unicode=True, width=120)
    config.PAGES_TO_DROP_YAML.write_text(HEADER + "\n" + body, encoding="utf-8")


# ---------------------------------------------------------------- cleaning (step 2)

PICTURE_TEXT = re.compile(r"<!-- Start of picture text -->.*?<!-- End of picture text -->", re.DOTALL)
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
# 1-3 digits then one or more groups of three digits; not inside a longer number or a decimal.
THOUSANDS = re.compile(r"(?<![\d.,])\d{1,3}(?: \d{3})+(?!\d|[.,]\d)")


def handle_picture_text(md: str, doc_id: str, stats: Counter) -> str:
    """Drop whole picture-text blocks for the documents in config, else keep the text
    and remove only the two comment markers."""
    if doc_id in config.CLEAN_DROP_PICTURE_TEXT_DOCS:
        stats["picture_text_blocks_dropped"] += len(PICTURE_TEXT.findall(md))
        return PICTURE_TEXT.sub("", md)
    stats["picture_text_markers_removed"] += md.count("<!-- Start of picture text -->")
    return md.replace("<!-- Start of picture text -->", "").replace("<!-- End of picture text -->", "")


def strip_nav_lines(md: str, stats: Counter) -> str:
    """Remove lines made only of side-navigation words (never headings or table rows)."""
    kept = []
    for line in md.splitlines():
        tokens = line.split()
        is_nav = tokens and all(t in config.CLEAN_NAV_WORDS for t in tokens)
        if is_nav and not line.lstrip().startswith(("#", "|")):
            stats["nav_lines_removed"] += 1
            continue
        kept.append(line)
    return "\n".join(kept)


def fix_ligature_glyph(md: str, stats: Counter) -> str:
    """U+FFFD -> "ti", except whole words known to be a different ligature (after, aircraft...)."""

    def fix_word(match: re.Match) -> str:
        word = match.group(0)
        stats["fffd_replaced"] += word.count("�")
        fixed = config.CLEAN_FFFD_WORD_FIXES.get(word.lower())
        if fixed:
            return fixed.capitalize() if word[0].isupper() else fixed
        return word.replace("�", "ti")

    return re.sub(r"[A-Za-z�]*�[A-Za-z�]*", fix_word, md)


def join_thousands(md: str, stats: Counter) -> str:
    """"1 041" -> "1041". Only a single group of three digits is joined: "110 110 109" may be
    three table values, and a wrongly joined number is a silent error."""

    def join(match: re.Match) -> str:
        if match.group(0).count(" ") > 1:
            stats["thousands_skipped_ambiguous"] += 1
            return match.group(0)
        stats["thousands_joined"] += 1
        return match.group(0).replace(" ", "")

    return THOUSANDS.sub(join, md)


WORD = re.compile(r"[a-z]{2,}")
SEPARATOR_ROW = re.compile(r"^\|[\s:|-]+\|$")


def build_vocab(markdowns) -> set[str]:
    """Lower-case words that occur often in the prose (non-table lines) of the given pages.

    Used to tell "Levelise|d" (a word cut in two) from "Total|installed" (two whole words).
    """
    counts: Counter = Counter()
    for md in markdowns:
        for line in md.splitlines():
            if not line.startswith("|"):
                counts.update(WORD.findall(line.replace("**", "").lower()))
    return {w for w, n in counts.items() if n >= config.CLEAN_REJOIN_VOCAB_MIN_COUNT}


def _is_cut_word(left: str, right: str, vocab: set[str]) -> bool:
    """True if `left` ends and `right` starts with the two halves of one word.

    The glued word must be known, and at least one half must not be a word on its own:
    "Total" + "installed" gives no known word; "Net" + "work" has two whole words, so it is left alone.
    """
    if not left or not right or not left[-1].isalpha() or not right[0].islower():
        return False
    tail = left.split(" ")[-1].lower()
    head = right.split(" ")[0].lower()
    return (tail + head) in vocab and (tail not in vocab or head not in vocab)


def rejoin_header_row(line: str, vocab: set[str], stats: Counter) -> str:
    """Glue the pieces of a header cell that the parser cut apart; keep the number of columns.

    Two cases: a word cut in two ("Levelise|d cost of e|lectricity"), and an open bracket that the
    next cells close ("(20|24 USD/k|W)"). The cells that were absorbed become empty, so the row still
    lines up with the separator row.
    """
    parts = line.split("|")
    cells = parts[1:-1]
    i = 0
    while i < len(cells):
        j = i + 1
        while j < len(cells):
            cur = cells[i]
            if not cur:
                break
            open_bracket = cur.count("(") > cur.count(")")
            if not cells[j] or not (open_bracket or _is_cut_word(cur, cells[j], vocab)):
                break
            cells[i] = cur + cells[j]
            cells[j] = ""
            stats["header_cells_rejoined"] += 1
            j += 1
        i = j if j > i + 1 else i + 1
    return "|".join([parts[0], *cells, parts[-1]])


def rejoin_split_headers(md: str, vocab: set[str], stats: Counter) -> str:
    """Apply `rejoin_header_row` to the first few lines of every table, never to the data rows."""
    out, position = [], 0
    for line in md.split("\n"):
        if line.startswith("|") and line.endswith("|"):
            position += 1
            if position <= config.CLEAN_REJOIN_HEADER_LINES and not SEPARATOR_ROW.match(line):
                line = rejoin_header_row(line, vocab, stats)
        else:
            position = 0
        out.append(line)
    return "\n".join(out)


def clean_markdown(md: str, doc_id: str, stats: Counter | None = None, vocab: set[str] | None = None) -> str:
    """Clean one page of markdown. `stats` counts how often each rule fired.

    `vocab` (see build_vocab) switches on the header rejoin for the documents in config.
    """
    stats = stats if stats is not None else Counter()
    md = handle_picture_text(md, doc_id, stats)
    if doc_id in config.CLEAN_NAV_DOCS:
        md = strip_nav_lines(md, stats)
    if doc_id in config.CLEAN_FFFD_DOCS:
        md = fix_ligature_glyph(md, stats)
    md = md.replace("<br>", " ")
    md = HTML_TAG.sub("", md)  # <sup>, <mark>, ... (the text inside stays)
    md = md.replace("**", "")
    if vocab is not None and doc_id in config.CLEAN_REJOIN_HEADER_DOCS:
        md = rejoin_split_headers(md, vocab, stats)
    if doc_id in config.CLEAN_SPACE_THOUSANDS_DOCS:
        md = join_thousands(md, stats)
    md = "\n".join(line.rstrip() for line in md.splitlines())
    md = re.sub(r"\n{3,}", "\n\n", md)  # one blank line between paragraphs
    return md.strip()


def approved_drops() -> set[tuple[str, int]]:
    if not config.PAGES_TO_DROP_YAML.exists():
        raise SystemExit("pages_to_drop.yaml not found: run `python -m rag.clean flag` and approve pages first")
    data = yaml.safe_load(config.PAGES_TO_DROP_YAML.read_text(encoding="utf-8")) or {}
    return {(doc_id, e["page"]) for doc_id, entries in data.items() for e in entries if e.get("approved")}


def clean_all() -> dict[str, Counter]:
    drops = approved_drops()
    config.CLEANED_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    vocab = build_vocab(
        json.loads(line)["markdown"]
        for path in sorted(config.PAGES_DIR.glob("*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    report = {}
    for path in sorted(config.PAGES_DIR.glob("*.jsonl")):
        stats: Counter = Counter()
        out_path = config.CLEANED_PAGES_DIR / path.name
        with open(path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
            for line in f:
                rec = json.loads(line)
                stats["pages_in"] += 1
                stats["chars_in"] += len(rec["markdown"])
                if (rec["doc_id"], rec["page"]) in drops:
                    stats["pages_dropped"] += 1
                    continue
                md = clean_markdown(rec["markdown"], rec["doc_id"], stats, vocab)
                if len(real_text(md)) < config.FLAG_EMPTY_CHARS:
                    # Nothing left to chunk. Reported, not written.
                    stats["pages_empty_after_cleaning"] += 1
                    continue
                stats["pages_kept"] += 1
                stats["chars_out"] += len(md)
                record = {"doc_id": rec["doc_id"], "page": rec["page"], "markdown": md, "n_chars": len(md)}
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        report[path.stem] = stats
    return report


def run_report(report: dict[str, Counter]) -> None:
    totals = ("pages_in", "pages_kept", "pages_dropped", "chars_in", "chars_out")
    for doc_id, st in report.items():
        print(f"{doc_id}: pages {st['pages_in']} -> {st['pages_kept']} (dropped {st['pages_dropped']}), "
              f"chars {st['chars_in']:,} -> {st['chars_out']:,}")
        fired = {k: v for k, v in st.items() if k not in totals}
        if fired:
            print("    rules fired:", fired)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["flag", "run"])
    args = parser.parse_args()

    if args.command == "run":
        run_report(clean_all())
        return

    flagged = flag_all()
    for message in merge_previous(flagged):
        print(message)
    write_yaml(flagged)

    for doc_id, entries in flagged.items():
        print(f"\n== {doc_id}: {len(entries)} flagged")
        for e in entries:
            mark = "x" if e["approved"] else " "
            print(f"  [{mark}] p{e['page']:>3}  {','.join(e['flags']):<22} real={e['real_chars']:>4}  {e['preview']!r}")
    print(f"\nwritten: {config.PAGES_TO_DROP_YAML.name}  (all entries start as approved: false)")


if __name__ == "__main__":
    main()
