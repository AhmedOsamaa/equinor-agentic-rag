"""Compare chunking strategies on the cleaned corpus. No retrieval and no questions involved.

This measures how each strategy treats the TEXT, not how well search works:
  size        tokens per chunk (bge-small tokenizer); the embedder reads at most 512
  >512        share of chunks the embedder would truncate
  <50         share of tiny chunks
  mid-start   share of chunks that start in the middle of a sentence (first letter lowercase)
  sent-intact share of randomly sampled sentences that sit whole inside at least one chunk
  span-intact same for 3 consecutive sentences (evidence often spans more than one)
  tbl-intact  share of markdown tables that sit whole inside one chunk
  inflation   total chunk tokens / corpus tokens (overlap duplicates text)

Containment favours big chunks, so read it together with size and >512. Whether a strategy
retrieves better is for the retrieval eval to decide once the gold questions exist.

Run: uv run python scripts/chunk_probe.py
"""

import json
import random
import re
import statistics
from dataclasses import dataclass

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

from rag import config

TOK = Tokenizer.from_file(hf_hub_download("BAAI/bge-small-en-v1.5", "tokenizer.json"))
TOK.no_truncation()
GROUPS = {
    "regulations (Havtil x4)": ["havtil_framework", "havtil_management", "havtil_activities", "havtil_co2"],
    "reports (Equinor, IRENA)": ["equinor_ar2025", "irena_rpgc2024"],
}
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def n_tok(text: str) -> int:
    return len(TOK.encode(text, add_special_tokens=False).ids)


def norm(text: str) -> str:
    return " ".join(text.split())


@dataclass
class Block:
    text: str
    page: int
    kind: str  # heading | para | table


@dataclass
class Chunk:
    text: str
    page: int


def load_blocks(doc_id: str) -> list[Block]:
    blocks = []
    with open(config.CLEANED_PAGES_DIR / f"{doc_id}.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for raw in re.split(r"\n\s*\n", rec["markdown"]):
                text = raw.strip()
                if not text:
                    continue
                lines = text.splitlines()
                if all(x.startswith("|") for x in lines):
                    kind = "table"
                elif len(lines) == 1 and text.startswith("#"):
                    kind = "heading"
                else:
                    kind = "para"
                blocks.append(Block(text, rec["page"], kind))
    return blocks


# ------------------------------------------------------------------ strategies

def fixed_chars(blocks: list[Block], size: int = 1500, overlap: int = 200) -> list[Chunk]:
    """Windows of `size` characters over the whole document text, `overlap` characters shared."""
    text, starts = "", []
    for b in blocks:
        starts.append((len(text), b.page))
        text += b.text + "\n\n"
    page_at = lambda pos: max(p for s, p in starts if s <= pos)
    return [Chunk(text[i:i + size], page_at(i)) for i in range(0, len(text), size - overlap)]


def fixed_tokens(blocks: list[Block], size: int = 400, overlap: int = 60) -> list[Chunk]:
    """Windows of `size` tokens over the whole document, `overlap` tokens shared."""
    text, starts = "", []
    for b in blocks:
        starts.append((len(text), b.page))
        text += b.text + "\n\n"
    offsets = TOK.encode(text, add_special_tokens=False).offsets
    chunks = []
    for i in range(0, len(offsets), size - overlap):
        window = offsets[i:i + size]
        a, z = window[0][0], window[-1][1]
        chunks.append(Chunk(text[a:z], max(p for s, p in starts if s <= a)))
    return chunks


def split_sentences_to_windows(text: str, max_tok: int) -> list[str]:
    """Pack whole sentences into pieces of at most max_tok tokens, repeating the last sentence."""
    sentences = SENT_SPLIT.split(text)
    pieces, cur = [], []
    for s in sentences:
        if cur and n_tok(" ".join(cur + [s])) > max_tok:
            pieces.append(" ".join(cur))
            cur = [cur[-1], s] if n_tok(cur[-1] + " " + s) <= max_tok else [s]
        else:
            cur.append(s)
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def split_table(text: str, max_tok: int) -> list[str]:
    """Split a markdown table by rows, repeating its header (first two lines) in every piece."""
    lines = text.splitlines()
    header, rows = lines[:2], lines[2:]
    pieces, cur = [], []
    for row in rows:
        if cur and n_tok("\n".join(header + cur + [row])) > max_tok:
            pieces.append("\n".join(header + cur))
            cur = []
        cur.append(row)
    if cur:
        pieces.append("\n".join(header + cur))
    return pieces


def structured(blocks: list[Block], max_tok: int = 400, min_tok: int = 0) -> list[Chunk]:
    """Heading-aware packing.

    Blocks are added to the current chunk in order. The chunk is closed when
      * a heading arrives and the chunk already has body text and at least `min_tok` tokens
        (heading-only fragments such as "CHAPTER I" / "Section 1" / "Scope" always stay
        together with the text that follows), or
      * the next block would push it past `max_tok`.
    A paragraph over `max_tok` is split at sentence boundaries; a table over `max_tok` is split
    by rows with its header repeated. A table is never mixed with other text.
    """
    chunks: list[Chunk] = []
    cur: list[Block] = []

    def flush() -> None:
        nonlocal cur
        if cur:
            chunks.append(Chunk("\n\n".join(b.text for b in cur), cur[0].page))
        cur = []

    def cur_tokens() -> int:
        return n_tok("\n\n".join(b.text for b in cur)) if cur else 0

    for b in blocks:
        if b.kind == "table":
            flush()
            pieces = split_table(b.text, max_tok) if n_tok(b.text) > max_tok else [b.text]
            chunks.extend(Chunk(p, b.page) for p in pieces)
            continue
        if b.kind == "heading":
            has_body = any(x.kind != "heading" for x in cur)
            if has_body and cur_tokens() >= min_tok:
                flush()
            cur.append(b)
            continue
        if n_tok(b.text) > max_tok:
            flush()
            chunks.extend(Chunk(p, b.page) for p in split_sentences_to_windows(b.text, max_tok))
            continue
        if cur and cur_tokens() + n_tok(b.text) > max_tok and any(x.kind != "heading" for x in cur):
            flush()
        cur.append(b)
    flush()
    return chunks


STRATEGIES = {
    "A  fixed 1500 chars, overlap 200": lambda bl: fixed_chars(bl, 1500, 200),
    "B  fixed 400 tokens, overlap 60": lambda bl: fixed_tokens(bl, 400, 60),
    "C  heading-aware, max 400, min 0": lambda bl: structured(bl, 400, 0),
    "D  heading-aware, max 400, min 100": lambda bl: structured(bl, 400, 100),
    "E  heading-aware, max 480, min 150": lambda bl: structured(bl, 480, 150),
}


# ------------------------------------------------------------------ measurement

def sample_evidence(blocks_by_doc: dict[str, list[Block]], n: int, seed: int) -> tuple[list[str], list[str]]:
    """Random sentences (8-40 words) and random 3-sentence spans from body paragraphs."""
    sents, spans = [], []
    for blocks in blocks_by_doc.values():
        for b in blocks:
            if b.kind != "para" or "|" in b.text or b.text.startswith(("-", ">")):
                continue
            parts = [norm(s) for s in SENT_SPLIT.split(b.text)]
            sents += [s for s in parts if 8 <= len(s.split()) <= 40]
            for i in range(len(parts) - 2):
                span = " ".join(parts[i:i + 3])
                if len(span.split()) <= 80 and all(len(p.split()) >= 4 for p in parts[i:i + 3]):
                    spans.append(span)
    rng = random.Random(seed)
    return rng.sample(sents, min(n, len(sents))), rng.sample(spans, min(n, len(spans)))


def measure(chunks: list[Chunk], tables: list[str], sents: list[str], spans: list[str], corpus_tokens: int) -> dict:
    sizes = [n_tok(c.text) for c in chunks]
    texts = [norm(c.text) for c in chunks]
    joined = "\n".join(texts)  # a sentence cut by a chunk boundary cannot match across the newline
    intact = lambda items: 100 * sum(1 for s in items if s in joined) / len(items)
    return {
        "n": len(chunks),
        "median": int(statistics.median(sizes)),
        "p95": sorted(sizes)[int(0.95 * len(sizes)) - 1],
        "over512": 100 * sum(1 for s in sizes if s > 512) / len(sizes),
        "under50": 100 * sum(1 for s in sizes if s < 50) / len(sizes),
        "mid": 100 * sum(1 for c in chunks if c.text.lstrip()[:1].islower()) / len(chunks),
        "sent": intact(sents),
        "span": intact(spans),
        "tbl": 100 * sum(1 for t in tables if t in joined) / len(tables) if tables else float("nan"),
        "infl": sum(sizes) / corpus_tokens,
    }


def main() -> None:
    for group, doc_ids in GROUPS.items():
        blocks_by_doc = {d: load_blocks(d) for d in doc_ids}
        corpus_tokens = sum(n_tok(b.text) for bl in blocks_by_doc.values() for b in bl)
        tables = [norm(b.text) for bl in blocks_by_doc.values() for b in bl if b.kind == "table"]
        sents, spans = sample_evidence(blocks_by_doc, 1500, seed=0)
        print(f"\n=== {group}: {corpus_tokens:,} tokens, {len(tables)} tables, "
              f"{len(sents)} sampled sentences, {len(spans)} sampled 3-sentence spans")
        print(f"{'strategy':<36}{'chunks':>7}{'median':>8}{'p95':>6}{'>512%':>7}{'<50%':>6}"
              f"{'mid%':>6}{'sent%':>7}{'span%':>7}{'tbl%':>6}{'infl':>6}")
        for name, build in STRATEGIES.items():
            chunks = [c for bl in blocks_by_doc.values() for c in build(bl)]
            m = measure(chunks, tables, sents, spans, corpus_tokens)
            print(f"{name:<36}{m['n']:>7}{m['median']:>8}{m['p95']:>6}{m['over512']:>7.1f}{m['under50']:>6.1f}"
                  f"{m['mid']:>6.1f}{m['sent']:>7.1f}{m['span']:>7.1f}{m['tbl']:>6.0f}{m['infl']:>6.2f}")


if __name__ == "__main__":
    main()
