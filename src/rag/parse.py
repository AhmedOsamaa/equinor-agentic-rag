"""PDF -> one markdown string per page, written as data/pages/<doc_id>.jsonl.

Each line is {"doc_id", "page", "markdown", "n_chars"}. `page` is the 1-based PDF page
index, which equals the printed page number in the documents checked so far (Equinor
p181, IRENA p71, Havtil p6). Gold labels use this number.

This step only converts. Cleaning (bold markers, <br>, number formats) is a separate
step so the raw output can be inspected first.

Run: uv run python -m rag.parse [--doc DOC_ID ...]
"""

import argparse
import hashlib
import json
import sys
import time

import pymupdf
import pymupdf4llm
import yaml
from pymupdf4llm.helpers import document_layout

from rag import config


class HashMismatch(RuntimeError):
    """The PDF on disk is not the file pinned in corpus.yaml."""


def load_corpus() -> list[dict]:
    return yaml.safe_load(config.CORPUS_YAML.read_text(encoding="utf-8"))["documents"]


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        # Read in 1 MiB blocks so a large PDF is never loaded into memory at once.
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_pdf(entry: dict) -> None:
    """Fail loudly if the file is missing or differs from the pinned SHA-256."""
    path = config.RAW_PDF_DIR / entry["filename"]
    if not path.exists():
        raise FileNotFoundError(f"{entry['doc_id']}: {path} not found")
    actual = sha256_of(path)
    if actual != entry["sha256"]:
        raise HashMismatch(
            f"{entry['doc_id']}: sha256 mismatch\n  pinned: {entry['sha256']}\n  actual: {actual}"
        )


def reorder_boxes_by_stream(boxes: list, words: list) -> list:
    """Sort layout boxes by where their words appear in the PDF's own text order.

    `words` is page.get_text("words"): tuples (x0, y0, x1, y1, text, ...) in stream order.
    Each word is assigned to the smallest box that contains its centre (so a big picture box
    does not steal the words of text boxes inside it). A box's key is the earliest stream
    index among its words. A box with no words (e.g. a picture) takes the key of the box
    before it, so it stays where the model put it. The sort is stable.
    """
    keys: list[int | None] = [None] * len(boxes)
    for index, word in enumerate(words):
        cx, cy = (word[0] + word[2]) / 2, (word[1] + word[3]) / 2
        best, best_area = None, None
        for b, box in enumerate(boxes):
            if box.x0 <= cx <= box.x1 and box.y0 <= cy <= box.y1:
                area = (box.x1 - box.x0) * (box.y1 - box.y0)
                if best is None or area < best_area:
                    best, best_area = b, area
        if best is not None and keys[best] is None:
            keys[best] = index  # words come in stream order, so the first hit is the minimum
    previous = -1
    filled = []
    for key in keys:
        previous = key if key is not None else previous
        filled.append(previous)
    order = sorted(range(len(boxes)), key=lambda b: filled[b])
    return [boxes[b] for b in order]


def page_to_markdown(doc: pymupdf.Document, page_index: int, doc_id: str = "") -> str:
    """Markdown for one page (0-based index), tables as markdown tables.

    One page per call, not the whole document at once: a native crash then points at
    one page, and progress can be written to disk as we go.
    """
    drop = config.PARSE_DROP_HEADERS_FOOTERS
    if doc_id in config.PARSE_REORDER_BY_STREAM_DOCS:
        return _markdown_in_stream_order(doc, page_index)
    return pymupdf4llm.to_markdown(
        doc,
        pages=[page_index],
        header=not drop,
        footer=not drop,
        use_ocr=config.PARSE_USE_OCR,
    )


def _markdown_in_stream_order(doc: pymupdf.Document, page_index: int, reorder: bool = True) -> str:
    """Same as pymupdf4llm.to_markdown (same parse_document / to_markdown settings), but the
    layout boxes are re-sorted by the PDF's text order first. reorder=False is for testing
    that this path alone changes nothing."""
    drop = config.PARSE_DROP_HEADERS_FOOTERS
    parsed = document_layout.parse_document(
        doc, pages=[page_index], force_text=True, use_ocr=config.PARSE_USE_OCR
    )
    page = parsed.pages[0]
    if reorder:
        page.boxes = reorder_boxes_by_stream(page.boxes, doc[page_index].get_text("words"))
    return parsed.to_markdown(header=not drop, footer=not drop)


def parse_document(entry: dict, only_pages: list[int] | None = None) -> int:
    """Parse one corpus document to data/pages/<doc_id>.jsonl; return the page count.

    With `only_pages` (1-based), only those pages are re-parsed and the other records of the
    existing file are kept, so a rule change for a few pages does not cost a full run.
    """
    verify_pdf(entry)
    doc = pymupdf.open(config.RAW_PDF_DIR / entry["filename"])
    config.PAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.PAGES_DIR / f"{entry['doc_id']}.jsonl"
    start = time.time()

    if only_pages:
        if not out_path.exists():
            raise SystemExit(f"{out_path} not found: run a full parse of {entry['doc_id']} first")
        records = {r["page"]: r for r in map(json.loads, out_path.read_text(encoding="utf-8").splitlines())}
        for page in only_pages:
            md = page_to_markdown(doc, page - 1, entry["doc_id"])
            records[page] = {"doc_id": entry["doc_id"], "page": page, "markdown": md, "n_chars": len(md)}
        with open(out_path, "w", encoding="utf-8") as out:
            for page in sorted(records):
                out.write(json.dumps(records[page], ensure_ascii=False) + "\n")
        return len(doc)

    # Written and flushed page by page: if a native crash kills the process, the file
    # shows exactly which page was last completed.
    with open(out_path, "w", encoding="utf-8") as out:
        for i in range(len(doc)):
            md = page_to_markdown(doc, i, entry["doc_id"])
            record = {"doc_id": entry["doc_id"], "page": i + 1, "markdown": md, "n_chars": len(md)}
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            if (i + 1) % 25 == 0 or i + 1 == len(doc):
                print(f"  {entry['doc_id']}: {i + 1}/{len(doc)} pages, {time.time() - start:.0f}s",
                      file=sys.stderr, flush=True)
    return len(doc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--doc", nargs="*", help="doc_ids to parse (default: all in corpus.yaml)")
    parser.add_argument("--pages", nargs="*", type=int,
                        help="re-parse only these pages (needs exactly one --doc and an existing parse)")
    args = parser.parse_args()

    corpus = load_corpus()
    wanted = set(args.doc) if args.doc else {e["doc_id"] for e in corpus}
    unknown = wanted - {e["doc_id"] for e in corpus}
    if unknown:
        raise SystemExit(f"unknown doc_id(s): {sorted(unknown)}")

    if args.pages and len(wanted) != 1:
        raise SystemExit("--pages needs exactly one --doc")
    for entry in corpus:
        if entry["doc_id"] in wanted:
            n = parse_document(entry, args.pages)
            print(f"{entry['doc_id']}: {n} pages -> {config.PAGES_DIR / (entry['doc_id'] + '.jsonl')}")


if __name__ == "__main__":
    main()
