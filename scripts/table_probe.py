"""Compare three ways of extracting tables, on real tables only.

For Equinor and IRENA: find tables with PyMuPDF's find_tables(), keep the ones that are
big and mostly numeric (so contents pages and prose are excluded), and dump for each
the plain text, the find_tables markdown and the pymupdf4llm page markdown to
results/smoke/tables/ so they can be compared by eye.

Run: uv run python -X utf8 scripts/table_probe.py
"""

import re
import sys
from pathlib import Path

import pymupdf
import pymupdf4llm
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag import config

DOCS = ["equinor_ar2025", "irena_rpgc2024"]
TOP_N = 3
MIN_ROWS, MIN_COLS = 5, 3
NUMERIC_CELL = re.compile(r"^\(?-?\d[\d,.\s]*%?\)?$")
# Pages we want to see regardless of ranking (1-based). IRENA p71 is Table 2.1.
FORCE_PAGES = {"irena_rpgc2024": [71]}
OUT = config.SMOKE_DIR / "tables"


def numeric_fraction(rows: list[list]) -> float:
    cells = [str(c).strip() for r in rows for c in r if c and str(c).strip()]
    return sum(bool(NUMERIC_CELL.match(c)) for c in cells) / len(cells) if cells else 0.0


def est_tokens(text: str) -> int:
    # Rough: ~3 chars per token for number-heavy text. An estimate, not a tokenizer count.
    return len(text) // 3


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    corpus = {d["doc_id"]: d for d in yaml.safe_load(config.CORPUS_YAML.read_text("utf-8"))["documents"]}

    for doc_id in DOCS:
        doc = pymupdf.open(config.RAW_PDF_DIR / corpus[doc_id]["filename"])
        candidates = []  # (score, page_index, table_index)
        # use_layout=False: the default ML layout path (pymupdf-layout, ONNX) segfaults
        # on IRENA page 7 (access violation, not catchable in Python). The classic
        # line/text-based algorithm completes on all 216 + 324 pages.
        # Results are cached so each page is processed once.
        cache: dict[tuple[int, int], tuple[str, list]] = {}
        found_total = 0
        for i, page in enumerate(doc):
            for t_i, table in enumerate(page.find_tables(use_layout=False).tables):
                found_total += 1
                rows = table.extract()
                cache[(i, t_i)] = (table.to_markdown(), rows)
                if len(rows) < MIN_ROWS or (rows and len(rows[0]) < MIN_COLS):
                    continue
                frac = numeric_fraction(rows)
                if frac >= 0.3:
                    candidates.append((frac * len(rows), i, t_i))
        print(f"\n=== {doc_id}: find_tables found {found_total} tables, "
              f"{len(candidates)} big numeric ones (>= {MIN_ROWS} rows, >= {MIN_COLS} cols)")

        picks = [(i, t_i) for _, i, t_i in sorted(candidates, reverse=True)[:TOP_N]]
        for p in FORCE_PAGES.get(doc_id, []):
            if not any(i == p - 1 for i, _ in picks):
                picks.append((p - 1, 0))

        for i, t_i in picks:
            page = doc[i]
            if (i, t_i) not in cache:
                print(f"page {i + 1}: find_tables found no table here")
            md_table, rows = cache.get((i, t_i), ("(none found)", []))
            plain = page.get_text()
            page_md = pymupdf4llm.to_markdown(doc, pages=[i])

            out = OUT / f"{doc_id}_p{i + 1}.md"
            out.write_text(
                f"# {doc_id} page {i + 1}, table {t_i}\n\n"
                f"## A. find_tables() markdown  ({len(rows)} rows)\n\n{md_table}\n\n"
                f"## B. pymupdf4llm page markdown\n\n{page_md}\n\n"
                f"## C. plain get_text()\n\n{plain}\n",
                encoding="utf-8",
            )
            print(f"page {i + 1}: rows={len(rows)} cols={len(rows[0]) if rows else 0}  "
                  f"find_tables md ~{est_tokens(md_table)} tok, page md ~{est_tokens(page_md)} tok"
                  f"  -> {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
