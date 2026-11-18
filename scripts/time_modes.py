"""Warm latency of each retrieval mode on a few queries (the first call per mode is a warm-up
and is discarded, as the project plan requires). A smoke check, not the eval.
Run: uv run python scripts/time_modes.py"""

import statistics

from rag.retrieve import search

QUERIES = ["How does the regulator restrict flaring of gas?", "Section 59a",
           "TRIF total recordable injury frequency", "What was the global weighted average LCOE of solar PV in 2024?",
           "How much oil and gas did Equinor produce in 2025?"]

for mode in ["vector", "hybrid", "hybrid_rerank"]:
    search(QUERIES[0], mode, 5)  # warm-up: loads models
    runs = [search(q, mode, 5).timings for q in QUERIES]
    stages = [s for s in runs[0] if s != "total"]
    print(f"{mode:14} total median {statistics.median(r['total'] for r in runs):.3f}s  max {max(r['total'] for r in runs):.3f}s   "
          + "  ".join(f"{s} {statistics.median(r[s] for r in runs):.3f}" for s in stages))
