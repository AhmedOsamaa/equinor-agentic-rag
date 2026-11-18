"""Measure, for every page of one document, what re-sorting the layout boxes by PDF stream
order would change.

For each page the layout model is run once; the markdown is produced before and after
rag.parse.reorder_boxes_by_stream. A page is "changed" if the markdown differs. Both
versions of every changed page are kept so they can be read next to the page image.

This only measures disagreement between the two orders; it does not say which is right.

Run: uv run python scripts/reorder_impact.py DOC_ID
Writes data/reorder_impact/<doc_id>.jsonl (gitignored). About 1 s per page.
"""

import copy
import difflib
import json
import sys
import time

import pymupdf
import yaml
from pymupdf4llm.helpers import document_layout

from rag import config
from rag.parse import reorder_boxes_by_stream


def main() -> None:
    doc_id = sys.argv[1]
    corpus = {e["doc_id"]: e for e in yaml.safe_load(config.CORPUS_YAML.read_text(encoding="utf-8"))["documents"]}
    doc = pymupdf.open(config.RAW_PDF_DIR / corpus[doc_id]["filename"])
    drop = config.PARSE_DROP_HEADERS_FOOTERS
    out_dir = config.DATA_DIR / "reorder_impact"
    out_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    changed = 0
    with open(out_dir / f"{doc_id}.jsonl", "w", encoding="utf-8") as out:
        for i in range(len(doc)):
            parsed = document_layout.parse_document(doc, pages=[i], force_text=True, use_ocr=config.PARSE_USE_OCR)
            # to_markdown consumes parts of the boxes (a second call on the same object raises
            # IndexError on list items), so each version gets its own copy.
            reordered = copy.deepcopy(parsed)
            before = parsed.to_markdown(header=not drop, footer=not drop)
            page = reordered.pages[0]
            original = list(page.boxes)
            page.boxes = reorder_boxes_by_stream(page.boxes, doc[i].get_text("words"))
            after = reordered.to_markdown(header=not drop, footer=not drop)
            moved = sum(1 for a, b in zip(original, page.boxes) if a is not b)
            lines_before = [x.strip() for x in before.splitlines() if x.strip()]
            lines_after = [x.strip() for x in after.splitlines() if x.strip()]
            record = {
                "page": i + 1,
                "changed": before != after,
                "moved_boxes": moved,
                "n_boxes": len(original),
                "line_similarity": round(difflib.SequenceMatcher(None, lines_before, lines_after).ratio(), 3),
                "same_lines": sorted(lines_before) == sorted(lines_after),
            }
            if record["changed"]:
                changed += 1
                record["before"], record["after"] = before, after
            out.write(json.dumps(record, ensure_ascii=False) + chr(10))
            out.flush()
            if (i + 1) % 50 == 0:
                print(f"{doc_id}: {i + 1}/{len(doc)} pages, {changed} changed, {time.time() - start:.0f}s", flush=True)
    print(f"RESULT {doc_id}: {changed} of {len(doc)} pages change under stream-order sorting", flush=True)


if __name__ == "__main__":
    main()
