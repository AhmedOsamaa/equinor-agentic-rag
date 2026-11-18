"""Run queries against the vector and the BM25 index and print the top hits side by side, to read them.
Run: uv run python scripts/try_search.py [--k 5] "query one" "query two" ..."""

import argparse

from rag.index import search_bm25, search_vector

parser = argparse.ArgumentParser()
parser.add_argument("queries", nargs="+")
parser.add_argument("--k", type=int, default=5)
args = parser.parse_args()

for q in args.queries:
    print(f"\n=== {q}")
    for name, search in [("VECTOR", search_vector), ("BM25", search_bm25)]:
        print(f" -- {name}")
        for h in search(q, k=args.k):
            print(f"  {h.score:7.3f}  {h.chunk_id}  p{h.page:<4} {h.heading_path[:60]}")
            print(f"           {h.text[:100].replace(chr(10), ' ')}")
