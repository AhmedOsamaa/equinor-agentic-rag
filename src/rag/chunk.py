"""Cleaned pages -> chunks.

Step 1 (this file so far): split pages into blocks (heading / paragraph / table) and work out,
for every block, which section it sits in: `section_id` and `heading_path`.
Packing blocks into size-limited chunks comes in the next step.
"""

import functools
import hashlib
import json
import re
from dataclasses import dataclass

from rag import config

CHAPTER = re.compile(r"^CHAPTER\s+[IVXLC]+\b", re.IGNORECASE)
SECTION = re.compile(r"^Section\s+\d+[a-z]?\b", re.IGNORECASE)  # "Section 59a" exists
CAPTION = re.compile(config.CHUNK_CAPTION_PATTERN, re.IGNORECASE)
LIST_ITEM = re.compile(r"^[a-z]\)|^[a-z]\.\s|^\d+\.\s")  # "a) ...", "f. operator,", "1. ..."


@dataclass
class Block:
    text: str
    page: int
    kind: str  # heading | para | table
    section_id: str = ""
    heading_path: tuple[str, ...] = ()


def heading_text(line: str) -> str:
    return line.lstrip("#").strip()


def classify(text: str, doc_id: str) -> str:
    lines = text.splitlines()
    if all(x.startswith("|") for x in lines):
        return "table"
    if len(lines) == 1 and text.startswith("#"):
        # In the Havtil documents a list item such as "a) The responsible party:" is body text.
        if doc_id in config.CHUNK_PATTERN_DOCS and LIST_ITEM.match(heading_text(text)):
            return "para"
        return "heading"
    return "para"


def load_blocks(doc_id: str) -> list[Block]:
    blocks = []
    with open(config.CLEANED_PAGES_DIR / f"{doc_id}.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for raw in re.split(r"\n\s*\n", rec["markdown"]):
                text = raw.strip()
                if text:
                    blocks.append(Block(text, rec["page"], classify(text, doc_id)))
    return blocks


def heading_level(text: str, doc_id: str) -> int | None:
    """Level of a heading, or None if it continues the previous heading (a section title
    that sits on its own line after "Section 2")."""
    title = heading_text(text)
    if doc_id in config.CHUNK_PATTERN_DOCS:
        if CHAPTER.match(title):
            return 1
        if SECTION.match(title):
            return 2
        return None  # any other Havtil heading: handled by the caller (title or subheading)
    return len(text) - len(text.lstrip("#"))


def assign_sections(blocks: list[Block], doc_id: str) -> list[Block]:
    """Set section_id and heading_path on every block, in place, and return the list.

    A heading opens a new section: the stack of open headings is cut back to its parents and
    the heading is pushed. A body block takes the current stack. A Havtil heading that comes
    right after a CHAPTER / Section heading (no body in between) is that heading's title, so it
    is appended to it instead of opening a new section. Any other Havtil heading, one that
    follows body text, is a sub-heading one level below the current section.
    """
    stack: list[tuple[int, str]] = []
    n_sections = 0
    just_opened_pattern = False  # the last block was a CHAPTER / Section heading
    for b in blocks:
        if b.kind == "heading":
            level = heading_level(b.text, doc_id)
            title = heading_text(b.text)
            if level is None and just_opened_pattern:
                stack[-1] = (stack[-1][0], f"{stack[-1][1]} {title}")
                just_opened_pattern = False
            else:
                if level is None:
                    level = (stack[-1][0] + 1) if stack else 1
                    just_opened_pattern = False
                else:
                    just_opened_pattern = doc_id in config.CHUNK_PATTERN_DOCS
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                n_sections += 1
        else:
            just_opened_pattern = False
        b.section_id = f"{doc_id}:{n_sections}"
        b.heading_path = tuple(t for _, t in stack)
    return blocks


# ------------------------------------------------------------------ step 2: packing

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_tokenizer = None


def n_tok(text: str) -> int:
    """Token count with the embedder's own tokenizer (loaded once)."""
    global _tokenizer
    if _tokenizer is None:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        _tokenizer = Tokenizer.from_file(hf_hub_download(config.EMBED_MODEL, "tokenizer.json"))
        _tokenizer.no_truncation()
    return len(_tokenizer.encode(text, add_special_tokens=False).ids)


@dataclass
class Chunk:
    doc_id: str
    page: int  # page of the first block
    text: str
    section_ids: list[str]  # more than one when small sections were merged
    heading_path: tuple[str, ...]  # path of the first block (of the table, for heading + table)
    chunk_id: str = ""  # "<doc_id>:<0-based index>", set by chunk_document


def split_sentences(text: str, max_tok: int, count) -> list[str]:
    """Pack whole sentences into pieces of at most max_tok tokens. Each new piece starts with
    the last sentence of the previous one, so a sentence cut at the boundary is still whole
    in one of them. (A single sentence longer than max_tok stays as one piece.)"""
    pieces, cur = [], []
    for s in SENT_SPLIT.split(text):
        if cur and count(" ".join(cur + [s])) > max_tok:
            pieces.append(" ".join(cur))
            cur = [cur[-1], s] if count(cur[-1] + " " + s) <= max_tok else [s]
        else:
            cur.append(s)
    if cur:
        pieces.append(" ".join(cur))
    return pieces


TABLE_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


def split_table(text: str, max_tok: int, count) -> list[str]:
    """Cut a markdown table between rows into pieces of at most max_tok tokens. The header
    (column names + the |---| line) is repeated at the top of every piece. A single row longer
    than the cap stays whole."""
    lines = text.splitlines()
    n_header = 2 if len(lines) > 2 and TABLE_SEPARATOR.match(lines[1].strip()) else 0
    header, rows = lines[:n_header], lines[n_header:]
    pieces, cur = [], []
    for row in rows:
        if cur and count("\n".join(header + cur + [row])) > max_tok:
            pieces.append("\n".join(header + cur))
            cur = []
        cur.append(row)
    if cur:
        pieces.append("\n".join(header + cur))
    return pieces


def pack(blocks: list[Block], doc_id: str, max_tok: int | None = None, min_tok: int | None = None,
         count=n_tok) -> list[Chunk]:
    """Group blocks (already carrying section_id / heading_path) into chunks.

    A chunk closes when
      * a heading arrives, the chunk has body text, and it has at least min_tok tokens
        (heading-only fragments like "CHAPTER I" always stay with the text that follows), or
      * the next block would push it past max_tok (and it already has body text).
    A paragraph over max_tok is split at sentence boundaries. A table is always its own chunk,
    together with the headings just before it; over the cap it is split by rows (split_table).
    """
    max_tok = max_tok or config.CHUNK_MAX_TOKENS
    min_tok = config.CHUNK_MIN_TOKENS if min_tok is None else min_tok
    chunks: list[Chunk] = []
    cur: list[Block] = []

    def tokens(items: list[Block]) -> int:
        return count("\n\n".join(b.text for b in items)) if items else 0

    def flush() -> None:
        nonlocal cur
        if cur:
            ids = list(dict.fromkeys(b.section_id for b in cur))
            chunks.append(Chunk(doc_id, cur[0].page, "\n\n".join(b.text for b in cur), ids, cur[0].heading_path))
        cur = []

    def emit(b: Block, text: str) -> None:
        chunks.append(Chunk(doc_id, b.page, text, [b.section_id], b.heading_path))

    for b in blocks:
        has_body = any(x.kind != "heading" for x in cur)
        if b.kind == "table":
            # Headings right before a table are its title ("# GHG emissions"). They travel with
            # the table; left behind they became 82 headings-only chunks on Equinor.
            # A caption paragraph ("Table 3.2 Capacity factors for solar PV, 2010-2024") sits
            # between the headings and the table and goes with them.
            caption = None
            if (config.CHUNK_CAPTION_WITH_TABLE and cur and cur[-1].kind == "para"
                    and CAPTION.match(cur[-1].text) and count(cur[-1].text) <= config.CHUNK_CAPTION_MAX_TOKENS):
                caption = cur.pop()
            titles: list[Block] = []
            while cur and cur[-1].kind == "heading":
                titles.insert(0, cur.pop())
            if caption:
                titles.append(caption)
            flush()
            title_text = "\n\n".join(t.text for t in titles)
            ids = list(dict.fromkeys([t.section_id for t in titles] + [b.section_id]))
            first = titles[0] if titles else b
            # A table over the cap is cut between rows; every piece repeats the title headings
            # and the table header, so it still says what its numbers are.
            budget = max_tok - count(title_text) if titles else max_tok
            pieces = split_table(b.text, budget, count) if count(b.text) > budget else [b.text]
            for piece in pieces:
                text = "\n\n".join(filter(None, [title_text, piece]))
                chunks.append(Chunk(doc_id, first.page, text, ids, b.heading_path))
        elif b.kind == "heading":
            if has_body and tokens(cur) >= min_tok:
                flush()
            cur.append(b)
        elif count(b.text) > max_tok:
            flush()
            for piece in split_sentences(b.text, max_tok, count):
                emit(b, piece)
        else:
            if has_body and tokens(cur) + count(b.text) > max_tok:
                flush()
            cur.append(b)
    flush()
    return chunks


# ------------------------------------------------------------------ step 4: ids, embed text, output

def chunk_document(doc_id: str) -> list[Chunk]:
    chunks = pack(assign_sections(load_blocks(doc_id), doc_id), doc_id)
    for i, c in enumerate(chunks):
        c.chunk_id = f"{doc_id}:{i:04d}"  # only stable while the chunking rules stay the same
    return chunks


def table_context(text: str) -> str:
    """One readable line naming a table's columns and rows, or "" if the text has no table.

    A table chunk starts with "|---|" and digits, which says little to an embedding model. This line
    puts the column headers and the row labels (first cell of each data row) up front in words.
    The first table of the chunk is described. Header = the header row and the row after the
    separator; data rows = everything after those.
    """
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("|")), None)
    if start is None:
        return ""
    run = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        run.append(line)
    if len(run) < 3:
        return ""

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip("|").split("|") if c.strip()]

    def unique(items: list[str], limit: int) -> list[str]:
        return list(dict.fromkeys(items))[:limit]

    header = unique(cells(run[0]) + cells(run[2]), config.CHUNK_TABLE_CONTEXT_MAX_ITEMS)
    labels = []
    for line in run[3:]:
        row = cells(line)
        if row and any(ch.isalpha() for ch in row[0]):  # a row label, not a bare number
            labels.append(row[0])
    labels = unique(labels, config.CHUNK_TABLE_CONTEXT_MAX_ITEMS)
    out = "Table with columns: " + "; ".join(header) + "."
    return out + (" Rows: " + "; ".join(labels) + "." if labels else "")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=1)
def load_table_summaries() -> dict[str, str]:
    """LLM summaries of table chunks, {text_hash: summary}, made by rag.table_summary. Empty if the file is missing."""
    if not config.TABLE_SUMMARY_PATH.exists():
        return {}
    return json.loads(config.TABLE_SUMMARY_PATH.read_text(encoding="utf-8"))


def embed_text(chunk: Chunk, prefix: bool | None = None) -> str:
    """The text that goes to the embedder: the heading path, the table context, then the chunk.

    Path elements that already appear in the chunk's own text are left out, so a chunk that
    starts with "# GHG emissions" does not repeat it. prefix=False gives the plain text."""
    prefix = config.CHUNK_PREFIX_HEADING_PATH if prefix is None else prefix
    if not prefix:
        return chunk.text
    missing = [h for h in chunk.heading_path if h not in chunk.text]
    head = " > ".join(missing)
    context = table_context(chunk.text) if config.CHUNK_TABLE_CONTEXT else ""
    summary = load_table_summaries().get(text_hash(chunk.text), "") if config.CHUNK_TABLE_SUMMARIES else ""
    return "\n\n".join(part for part in (head, summary, context, chunk.text) if part)


def write_chunks() -> None:
    import yaml

    corpus = yaml.safe_load(config.CORPUS_YAML.read_text(encoding="utf-8"))["documents"]
    config.CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with open(config.CHUNKS_PATH, "w", encoding="utf-8") as f:
        for entry in corpus:
            chunks = chunk_document(entry["doc_id"])
            for c in chunks:
                record = {"chunk_id": c.chunk_id, "doc_id": c.doc_id, "page": c.page,
                          "section_ids": c.section_ids, "heading_path": list(c.heading_path),
                          "n_tokens": n_tok(c.text), "text": c.text}
                f.write(json.dumps(record, ensure_ascii=False) + chr(10))
            print(f"{entry['doc_id']}: {len(chunks)} chunks")
            total += len(chunks)
    print(f"{total} chunks -> {config.CHUNKS_PATH}")


if __name__ == "__main__":
    write_chunks()
