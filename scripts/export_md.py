"""Export parsed pages to markdown files for reading by eye.

Default: data/pages/<doc_id>.jsonl (raw parser output) -> data/review/<doc_id>.md
--clean: data/pages_clean/<doc_id>.jsonl (after rag.clean run) -> data/review_clean/<doc_id>.md

Each page starts with a separator line `##### PAGE N (doc_id) #####`, so a page number
in the review file is the same `page` used in the jsonl and in gold labels. Pages dropped
by the cleaning step are simply absent from the --clean files.

Run: uv run python scripts/export_md.py [--clean] [--doc DOC_ID ...]
"""

import argparse
import json

from rag import config


def export(doc_id: str, clean: bool) -> tuple[int, int]:
    src_dir = config.CLEANED_PAGES_DIR if clean else config.PAGES_DIR
    review_dir = config.DATA_DIR / ("review_clean" if clean else "review")
    src = src_dir / f"{doc_id}.jsonl"
    if not src.exists():
        raise SystemExit(f"{src} not found: run rag.parse (or `rag.clean run` for --clean) first")
    review_dir.mkdir(parents=True, exist_ok=True)
    out_path = review_dir / f"{doc_id}.md"
    n = 0
    with open(src, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            rec = json.loads(line)
            out.write(f"\n\n##### PAGE {rec['page']} ({rec['doc_id']}) #####\n\n")
            out.write(rec["markdown"])
            n += 1
    return n, out_path.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--clean", action="store_true", help="export the cleaned pages")
    parser.add_argument("--doc", nargs="*", help="doc_ids (default: every jsonl in the source folder)")
    args = parser.parse_args()
    src_dir = config.CLEANED_PAGES_DIR if args.clean else config.PAGES_DIR
    doc_ids = args.doc or sorted(p.stem for p in src_dir.glob("*.jsonl"))
    for doc_id in doc_ids:
        pages, size = export(doc_id, args.clean)
        folder = "review_clean" if args.clean else "review"
        print(f"{doc_id}: {pages} pages, {size / 1024:.0f} KiB -> data/{folder}/{doc_id}.md")


if __name__ == "__main__":
    main()
