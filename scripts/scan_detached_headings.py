"""Scan: does the layout model emit a heading/label before a body block from another column?

Reads the layout model's block list (class, position, text, in the model's own order) for
every page and flags a label (a section-header/title, or a text block of at most 3 words)
whose next body block starts more than GAP points to the left or right. Equinor p8
("Q1 Q2 Q3 Q4") and p83 ("Basis for preparation") are the two pages found by hand; both
are flagged.

Known limits (measured on 2026-11-14, notes in the project build log):
  * It is a rough detector for ONE pattern. Interleaved columns around a table (Equinor p108)
    are not detected.
  * It has false positives: covers, navigation labels, signature pages, side-margin tags.
    It flags almost every page of the single-column Havtil regulations (probably centred
    headings), so its Havtil numbers are meaningless.
  * It calls parse_document with the default force_text=False, while the pipeline's
    pymupdf4llm.to_markdown uses force_text=True, so the box lists may differ slightly.

Run: uv run python scripts/scan_detached_headings.py DOC_ID [DOC_ID ...]
Writes results/smoke/detached_headings.json (gitignored). Takes about 1 s per page.
"""

import json
import sys
import time

import pymupdf
import yaml
from pymupdf4llm.helpers import document_layout as dl

from rag import config

GAP = 150  # points; columns start about 240 pt apart on the landscape Equinor pages
HEAD = {"section-header", "title"}
SKIP = {"page-header", "page-footer", "picture"}


def text_of(box) -> str:
    text = " ".join(str(getattr(box, "text", "") or "").split())
    if not text and getattr(box, "textlines", None):
        text = " ".join(" ".join(s["text"] for s in tl["spans"]) for tl in box.textlines)
    return text


def is_label(box) -> bool:
    text = text_of(box)
    return box.boxclass in HEAD or (box.boxclass == "text" and len(text.split()) <= 3 and len(text) <= 20)


def scan_document(doc: pymupdf.Document, doc_id: str) -> dict[int, list]:
    hits: dict[int, list] = {}
    start = time.time()
    for i in range(len(doc)):
        page = dl.parse_document(doc, pages=[i], use_ocr=False).pages[0]
        boxes = [b for b in page.boxes if b.boxclass not in SKIP]
        for k, box in enumerate(boxes):
            if not is_label(box):
                continue
            following = next((c for c in boxes[k + 1:] if not is_label(c)), None)
            if following is not None and abs(following.x0 - box.x0) > GAP and following.y0 > box.y0 - 5:
                hits.setdefault(i + 1, []).append(
                    (text_of(box)[:40], round(box.x0), text_of(following)[:40], round(following.x0))
                )
        if (i + 1) % 50 == 0:
            print(f"{doc_id}: {i + 1}/{len(doc)} pages, {time.time() - start:.0f}s", flush=True)
    return hits


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    corpus = {e["doc_id"]: e for e in yaml.safe_load(config.CORPUS_YAML.read_text(encoding="utf-8"))["documents"]}
    results = {}
    for doc_id in sys.argv[1:]:
        doc = pymupdf.open(config.RAW_PDF_DIR / corpus[doc_id]["filename"])
        results[doc_id] = scan_document(doc, doc_id)
        print(f"RESULT {doc_id}: {len(results[doc_id])} of {len(doc)} pages flagged", flush=True)
    config.SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    out = config.SMOKE_DIR / "detached_headings.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
