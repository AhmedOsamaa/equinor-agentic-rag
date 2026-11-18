"""Write the chunks under a token limit for one document to data/review_chunks/<doc>_tiny.md
so they can be read. Run: uv run python scripts/review_tiny_chunks.py DOC_ID [LIMIT]"""

import sys
from collections import Counter

from rag import config
from rag.chunk import assign_sections, load_blocks, n_tok, pack

doc_id = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
chunks = pack(assign_sections(load_blocks(doc_id), doc_id), doc_id)
tiny = [(i, c, n_tok(c.text)) for i, c in enumerate(chunks) if n_tok(c.text) < limit]


def kind(c):
    if c.text.startswith("|"):
        return "table"
    lines = c.text.splitlines()
    return "headings only" if all(x.startswith("#") for x in lines if x.strip()) else "text"


out_dir = config.DATA_DIR / "review_chunks"
out_dir.mkdir(parents=True, exist_ok=True)
nl = chr(10)
with open(out_dir / f"{doc_id}_tiny.md", "w", encoding="utf-8") as f:
    f.write(f"# {doc_id}: {len(tiny)} of {len(chunks)} chunks under {limit} tokens{nl}{nl}")
    for i, c, n in tiny:
        f.write(f"## chunk {i}: page {c.page}, {n} tokens, {kind(c)}{nl}")
        f.write(f"path: {' > '.join(c.heading_path)}{nl}")
        if i > 0:
            f.write(f"previous chunk: {n_tok(chunks[i-1].text)} tokens, page {chunks[i-1].page}{nl}")
        f.write(f"{nl}{c.text}{nl}{nl}---{nl}{nl}")
print(len(tiny), "of", len(chunks), "chunks under", limit, "tokens")
print(Counter(kind(c) for _, c, _ in tiny))
print("sizes:", sorted(n for _, _, n in tiny)[::10])
print("pages with most:", Counter(c.page for _, c, _ in tiny).most_common(8))
