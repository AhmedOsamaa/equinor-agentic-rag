"""Compare bm25s tokenizer settings on strings taken from our chunks.
Run: uv run python scripts/tokenizer_probe.py"""

import json
from collections import Counter

import bm25s

from rag import config

DEFAULT = r"(?u)\b\w\w+\b"
# A number written with internal separators stays one token ("1,041", "0.043", "1-3",
# "50001:2018", "2025-2030"); everything else is a run of word characters (so "59a", "co2").
NUMBERS = r"(?u)\d+(?:[.,]\d+)+|\d{1,2}(?:-\d{1,2})+|\w\w+|\d"

STRINGS = ["Section 59a", "TRIF 1,041 MBOE/D", "CO2 emissions 2-2", "Sections 1-3, 1-4 and 2-2",
           "2,137 mboe/day", "LCOE USD 0.043/kWh", "Scope 1 GHG emissions1", "NS ISO 50001:2018",
           "2025–2030 targets", "2025-2030 plan", "12-34 and 2,137,000", "Equinor’s production in 2025.", "Figure 2.15 Weighted average LCOE"]


def tok(text: str, pattern: str):
    return bm25s.tokenize([text], token_pattern=pattern, stopwords="en", return_ids=False,
                          show_progress=False)[0]


for s in STRINGS:
    print(repr(s))
    print("   default:", tok(s, DEFAULT))
    print("   numbers:", tok(s, NUMBERS))

with open(config.CHUNKS_PATH, encoding="utf-8") as f:
    texts = [json.loads(line)["text"] for line in f]
for name, pattern in [("default", DEFAULT), ("numbers", NUMBERS)]:
    tokens = bm25s.tokenize(texts, token_pattern=pattern, stopwords="en", return_ids=False, show_progress=False)
    counts = Counter(t for doc in tokens for t in doc)
    digits = [t for t in counts if any(ch.isdigit() for ch in t)]
    one_char = [t for t in counts if len(t) == 1]
    print(f"\n{name}: {len(counts):,} distinct tokens, {sum(counts.values()):,} in total, "
          f"{len(digits):,} contain a digit, {len(one_char)} are one character")
    print("   most common one-character tokens:", [(t, counts[t]) for t in sorted(one_char, key=counts.get, reverse=True)[:8]])
