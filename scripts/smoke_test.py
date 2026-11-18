"""Smoke test: can PyMuPDF get usable text out of each corpus PDF?

Prints per-document page count and characters per page, flags near-empty pages
(scanned / image-only), and dumps the most table-like pages of the Equinor and IRENA
PDFs to results/smoke/ so the table parsing can be judged by eye.

Run: uv run python scripts/smoke_test.py
"""

import re
import statistics
import sys
from pathlib import Path

import pymupdf
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag import config

LOW_TEXT_CHARS = 50  # below this a page is treated as "almost no text"
TABLE_DUMP_DOCS = {"equinor_ar2025", "irena_rpgc2024"}
TABLE_DUMP_N = 3

# A token like 1,234.5  -12  45%  (3.2)  counts as a number.
NUMBER = re.compile(r"^\(?-?\d[\d,.\s]*%?\)?$")


def table_score(text: str) -> int:
    """Number of lines that look like table rows: at least 3 numeric tokens.

    In a flattened PDF table each row usually comes out as one line (or several short
    lines), so many numeric-heavy lines on one page is a cheap proxy for "this page is
    a table". It is a heuristic, not a table detector: it will also rank
    number-heavy lists and financial statements high, which is what we want to see.
    """
    score = 0
    for line in text.splitlines():
        tokens = line.split()
        if sum(1 for t in tokens if NUMBER.match(t)) >= 3:
            score += 1
    return score


def analyse(doc_id: str, path: Path) -> None:
    doc = pymupdf.open(path)
    chars, texts = [], []
    for page in doc:
        text = page.get_text()
        texts.append(text)
        chars.append(len(text.strip()))

    low = [i + 1 for i, c in enumerate(chars) if c < LOW_TEXT_CHARS]
    print(f"\n=== {doc_id}  ({path.name})")
    print(f"pages: {len(doc)}   total chars: {sum(chars):,}")
    print(
        f"chars/page  min: {min(chars)}   median: {int(statistics.median(chars))}   "
        f"max: {max(chars)}"
    )
    shown = ", ".join(map(str, low[:40])) + (" ..." if len(low) > 40 else "")
    print(f"pages with < {LOW_TEXT_CHARS} chars: {len(low)}" + (f"  -> {shown}" if low else ""))

    if doc_id in TABLE_DUMP_DOCS:
        ranked = sorted(range(len(texts)), key=lambda i: table_score(texts[i]), reverse=True)
        config.SMOKE_DIR.mkdir(parents=True, exist_ok=True)
        for i in ranked[:TABLE_DUMP_N]:
            out = config.SMOKE_DIR / f"{doc_id}_p{i + 1}.txt"
            out.write_text(
                f"# {doc_id} page {i + 1} (table score {table_score(texts[i])})\n\n{texts[i]}",
                encoding="utf-8",
            )
            print(f"table-like page {i + 1} (score {table_score(texts[i])}) -> {out.relative_to(config.ROOT)}")


def main() -> None:
    corpus = yaml.safe_load(config.CORPUS_YAML.read_text(encoding="utf-8"))["documents"]
    listed = set()
    for entry in corpus:
        listed.add(entry["filename"])
        analyse(entry["doc_id"], config.RAW_PDF_DIR / entry["filename"])

    # Anything in docs/ that corpus.yaml does not know about is reported, not ignored.
    for extra in sorted(config.RAW_PDF_DIR.glob("*.pdf")):
        if extra.name not in listed:
            analyse(f"NOT IN CORPUS: {extra.stem}", extra)


if __name__ == "__main__":
    main()
