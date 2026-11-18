"""All tunable values live here (models, k, chunk sizes, thresholds).

Only the paths exist so far; the rest is added together with the component that uses it.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Raw publisher PDFs, downloaded by hand for now and gitignored (docs/*.pdf).
RAW_PDF_DIR = ROOT / "docs"
CORPUS_YAML = ROOT / "corpus.yaml"

# Derived artefacts, all gitignored.
DATA_DIR = ROOT / "data"
INDEX_DIR = ROOT / "index"

# Eval outputs.
RESULTS_DIR = ROOT / "results"
SMOKE_DIR = RESULTS_DIR / "smoke"

# --- parse.py -------------------------------------------------------------------
PAGES_DIR = DATA_DIR / "pages"  # one <doc_id>.jsonl per document, one line per page
# Let pymupdf4llm's layout model drop blocks it classifies as page header / footer
# (running titles, navigation strips, page numbers). Checked on 4 pages only.
PARSE_DROP_HEADERS_FOOTERS = True
# All six PDFs have a real text layer (smoke test), so OCR is off: faster, deterministic.
PARSE_USE_OCR = False
# The ML layout model emits headings/labels that top a later column (e.g. "Q1 Q2 Q3 Q4" on
# Equinor p8, "Basis for preparation" on p83) before the column bodies, detaching them, and
# can interleave columns around a table (p108). For these documents the layout model's blocks
# are re-sorted by the PDF's own text order; tables and formatting stay the model's. Applied to
# every page of the document: on 134 of 324 Equinor pages the two orders differ, all
# order-only (same lines). Of 9 changed pages judged (3 from text only), 7 were better
# (headings or split sentences reattached) and 2 neutral (whole boxes swapped, headings
# attached either way); none was worse.
# Not applied to other documents: no evidence for them (IRENA: scan flagged 2 of 216 pages).
PARSE_REORDER_BY_STREAM_DOCS = {"equinor_ar2025"}

# --- clean.py: page flagging (thresholds picked by looking at the parsed pages) ----
PAGES_TO_DROP_YAML = ROOT / "pages_to_drop.yaml"  # tracked; entries are approved by hand
FLAG_EMPTY_CHARS = 10  # fewer real characters than this -> "empty"
FLAG_SHORT_CHARS = 200  # fewer than this -> "short" (cover / divider / lone heading)
FLAG_LEADER_RUNS = 3  # at least this many dot-leader runs ("....." or ". . . .") -> "toc_leaders"

# --- clean.py: cleaning rules (each one chosen from measurements on the parsed pages) ---
CLEANED_PAGES_DIR = DATA_DIR / "pages_clean"  # data/pages minus approved drops, cleaned
# <!-- Start of picture text --> blocks hold text found inside figures. Measured on kept pages:
# IRENA 48,077 chars (about 12% of the document), almost all chart legends, axis ticks and photo
# credits ("Africa Asia Europe 0.120 0.100 ..."), which would match numeric queries wrongly, so
# they are dropped whole (figure text is lost: a README limitation). Equinor has 11,251 chars
# (about 1%), partly real content (p21/p22 "at a glance" prose, p41 production by field, p60
# results by country), so there only the comment markers are removed and the text is kept.
CLEAN_DROP_PICTURE_TEXT_DOCS = {"irena_rpgc2024"}
# Equinor's side navigation strip leaks into 7+ pages as lines made only of these words.
CLEAN_NAV_DOCS = {"equinor_ar2025"}
CLEAN_NAV_WORDS = {"INTRODUCTION", "CONTENTS", "ABOUT", "US", "OUR", "PERFORMANCE",
                   "SUSTAINABILITY", "STATEMENT", "FINANCIAL", "STATEMENTS", "ADDITIONAL", "INFORMATION"}
# Havtil Framework: a font ligature glyph is extracted as U+FFFD. It is "ti" in 97% of the
# 1,189 occurrences (checked against a vocabulary); these whole words are the exceptions found.
CLEAN_FFFD_DOCS = {"havtil_framework"}
CLEAN_FFFD_WORD_FIXES = {"a�er": "after", "a�erwards": "afterwards", "aircra�": "aircraft",
                         "fi�h": "fifth", "shi�ing": "shifting", "ou�i�ng": "outfitting"}
# --- chunk.py -------------------------------------------------------------------
# Havtil headings are all "#" in the markdown, so their level comes from the wording instead:
# CHAPTER <roman> = level 1, Section <n> = level 2. A heading line directly after one of these
# (the section title) is part of it. Lines like "a) The responsible party:" are list items.
# Equinor / IRENA: the markdown "#" count is used as it is; the layout model also labels some
# infographic text as headings ("# 0.21"), so their heading paths are noisy (README limitation).
# Packing (strategy D of scripts/chunk_probe.py). Embedder reads at most 512 tokens, so 400
# leaves room for a heading-path prefix. A chunk closes at a heading only once it holds at
# least CHUNK_MIN_TOKENS, so tiny sections merge into their neighbour.
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
# Put the heading path in front of the text that is embedded (the stored chunk text is
# unchanged). To be compared on / off in the retrieval eval.
CHUNK_PREFIX_HEADING_PATH = True
# For a chunk with a table, also put one line in front that names the columns and the row labels
# (chunk.table_context). Dev misses were table chunks that embed as digits and cell separators.
CHUNK_TABLE_CONTEXT = False  # tried on dev 17 Nov (retrieval_dev_tablectx): no supported gain, table questions slightly worse
CHUNK_TABLE_CONTEXT_MAX_ITEMS = 30
EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # bge-base tried on dev 17 Nov (retrieval_dev_bgebase): no supported gain for vector, 4.6x slower to embed
CHUNK_MAX_TOKENS = 400
CHUNK_MIN_TOKENS = 100
# A short paragraph right before a table that starts "Table 3.2", "Figure 4.1" or "Box 2" is the
# table's caption and travels with it (like a heading does). Found on the dev pilot: 27 of 30
# IRENA tables sit under such a caption, and without it the chunk never says what the numbers
# are (solar PV? offshore wind?). Only short paragraphs, so a sentence like "Table 4.4 shows ..."
# followed by a long passage is not pulled in. Set False to compare in the eval.
CHUNK_CAPTION_WITH_TABLE = True
CHUNK_CAPTION_PATTERN = r"^\s*(table|figure|box)\s+[A-Za-z]?\d"
CHUNK_CAPTION_MAX_TOKENS = 60
CHUNK_PATTERN_DOCS = {"havtil_framework", "havtil_management", "havtil_activities", "havtil_co2"}

# --- index.py ---------------------------------------------------------------------
VECTOR_INDEX_DIR = INDEX_DIR / "chroma"
VECTOR_BUILD_INFO = INDEX_DIR / "vector_build.json"  # build time, sizes, settings (for the README)
# BGE models want this instruction in front of the QUERY only, never in front of the chunks.
EMBED_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
EMBED_BATCH_SIZE = 32
DEFAULT_K = 10

# --- retrieve.py / rerank.py ------------------------------------------------------
RETRIEVE_MODES = ("vector", "hybrid", "hybrid_rerank")
RETRIEVE_CANDIDATES = 50  # each of vector and BM25 contributes its top 50 to the fusion
RRF_K = 60  # the constant in 1 / (k + rank); 60 is the value from the original RRF paper
# After fusion, the 1st-ranked chunk of either retriever is kept inside the returned top k (hybrid) or the
# reranker's pool. Plain RRF buries a chunk that only one retriever finds (dev: equinor_ar2025-114).
PIN_TOP_RANKED = True
# rewrite.multi_search: the original query's top N chunks stay first; rewrites only fill the remaining slots
# (dev, 18 Nov: plain RRF over original + rewrites pushed out chunks the plain search had found).
REWRITE_KEEP_TOP = 5
# Cross-encoder. Switched 16 Nov from "BAAI/bge-reranker-base" (5.7 s per query on CPU) to MiniLM (0.84 s):
# on 52 dev questions 11 of 12 paired intervals (tier x metric) include 0; the one that excludes it
# is round 3 nDCG@10, -0.083 [-0.171, -0.006] after the nDCG ideal-ranking fix of 16 Nov (it was reported as
# -0.074 [-0.152, -0.001] with the buggy metric; results key retrieval_dev_minilm holds the old value).
# Try bge again with --rerank-model.
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# The top 30 of the fused list go to the reranker (plan: 30 to 50). 50 was tried on dev on 17 Nov
# (results key retrieval_dev_rerank50): hit@10 and MRR unchanged in every tier, latency 0.83 s -> 1.24 s, so it was reverted.
RERANK_CANDIDATES = 30

# --- stats.py (bootstrap confidence intervals) -------------------------------------
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 42  # fixed, so a rerun prints identical intervals
BOOTSTRAP_CI = 0.95

# BM25 (bm25s). The default tokenizer pattern drops one-character tokens and splits on every
# punctuation mark, so "1,041" became "041", "2,137" became "137", "0.043" became "043" and
# clause references like "1-3" vanished (scripts/tokenizer_probe.py). This pattern keeps a
# number with its internal "," or "." whole, keeps "1-3" style references (hyphen between
# numbers of at most 2 digits, so year ranges still split), drops single letters and keeps
# single digits ("Scope 1").
BM25_TOKEN_PATTERN = r"(?u)\d+(?:[.,]\d+)+|\d{1,2}(?:-\d{1,2})+|\w\w+|\d"
BM25_STOPWORDS = "en"
BM25_K1 = 1.5  # how fast repeated words saturate
BM25_B = 0.75  # how strongly long chunks are penalised
# Index the heading-path text (embed_text) or the plain chunk text; to be compared in the eval.
BM25_USE_EMBED_TEXT = True
BM25_INDEX_DIR = INDEX_DIR / "bm25"
BM25_BUILD_INFO = INDEX_DIR / "bm25_build.json"

# IRENA writes thousands with a plain space ("1 041"). Only a single group is joined (407 cases,
# 0 multi-group cases on kept pages); "110 110 109" may be three separate table values.
CLEAN_SPACE_THOUSANDS_DOCS = {"irena_rpgc2024"}
# The parser cuts a header cell that spans several columns at character positions ("Levelise|d cost of e|lectricity").
# Rejoined in the first lines of a table, only where the glued word is a word the corpus itself uses.
CLEAN_REJOIN_HEADER_DOCS = {"equinor_ar2025", "irena_rpgc2024"}
CLEAN_REJOIN_HEADER_LINES = 3      # table lines treated as header: header row, separator, one more row
CLEAN_REJOIN_VOCAB_MIN_COUNT = 3   # a word counts as known if it occurs this often in the prose of the corpus

# --- llm.py -------------------------------------------------------------------------
LLM_MODEL = "openai:gpt-4o-mini"   # LangChain "provider:model". Chosen 17 Nov: cheap, accepts temperature 0.
LLM_TEMPERATURE = 0
# Model used to answer questions from retrieved chunks (generation.py). Started with nano and compared it with mini on the
# same questions (mini is better in every tier, see the README).
GENERATION_MODEL = "openai:gpt-5-nano"
# Per-model call parameters that replace the default {"temperature": LLM_TEMPERATURE}. Checked 17 Nov with real calls: gpt-5-nano
# rejects temperature 0 (400, only 1 is allowed) and reasoning_effort "none" (allowed: minimal, low, medium, high). So its answers
# are NOT deterministic; the response cache is what makes a rerun repeat the same text.
LLM_MODEL_PARAMS = {"openai:gpt-5-nano": {"reasoning_effort": "minimal"},
                    "openai:gpt-5-mini": {"reasoning_effort": "minimal"}}   # mini: same settings as nano so only the model differs
LLM_CACHE_DIR = DATA_DIR / "llm_cache"            # one json file per prompt hash; gitignored with data/
LLM_LOG_PATH = RESULTS_DIR / "llm_calls.jsonl"    # one line per call: tokens, latency, cost, cached or not
LLM_BUDGET_USD = 1.00       # hard stop: a call is refused once the logged spend reaches this. Raise it on purpose.
# USD per 1 million tokens (input, output): OpenAI's published list prices, checked 18 Nov 2026 (nano on OpenAI's model page; mini against
# third-party trackers). Batch prices are half. Used only for the budget cap and cost estimates.
LLM_PRICES = {"openai:gpt-4o-mini": (0.15, 0.60),
              "openai:gpt-5-nano": (0.05, 0.40), 
              "openai:gpt-5-mini": (0.25, 2.00)}
LLM_RETRY_ATTEMPTS = 5

# --- agent.py ---------------------------------------------------------------------------
AGENT_MODEL = "openai:gpt-5-mini"   # mini beat nano in every tier (test, 17 Nov); nano refuses answerable questions too often
AGENT_K = 10                        # passages returned per search call
AGENT_MAX_SEARCHES = 3              # after this the model has no tool and must answer: bounds cost and steps
AGENT_MAX_QUESTION_CHARS = 600      # guardrail: longer input is refused before any model call (abuse and cost)

# --- table_summary.py -----------------------------------------------------------------
TABLE_SUMMARY_PATH = DATA_DIR / "table_summaries_v2.json"   # {sha256-of-chunk-text: summary}; gitignored with data/. v1 = description only.
# Put the LLM summary of a table chunk in front of the text that is embedded and indexed (chunk.embed_text).
# Off until the dev run has shown that it helps.
CHUNK_TABLE_SUMMARIES = True
TABLE_SUMMARY_CONCURRENCY = 8
