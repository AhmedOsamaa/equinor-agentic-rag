"""Query rewriting: turn one question into several search queries, search with all of them, merge the results.

    queries = rewrite_queries(question)               # [original, rewrite 1, ...]
    hits = multi_search(queries, k=10)

Why: a question can be worded differently from the document (round 2 swaps synonyms on purpose) or can need several
pieces of evidence (multi-page, cross-document questions). A language model can rewrite the question into the document's
own vocabulary and split a multi-part question into one query per part. The original question is always kept as the
first query, and its top results are kept first (`multi_search`), so a bad rewrite can only add candidates.

The remaining slots are filled by our own RRF (`rag.retrieve.rrf`) over the per-query ranked lists, so a chunk that several queries find rises.
"""

import json
import re
from dataclasses import replace

from rag import config
from rag.index import Hit
from rag.llm import complete
from rag.retrieve import rrf, search

MAX_REWRITES = 3

REWRITE_SYSTEM_PROMPT = f"""You help a search system find passages in six public energy documents: the Equinor Annual Report 2025, four Havtil regulations (Framework, Management, Activities, CO2 Safety) and the IRENA report "Renewable Power Generation Costs in 2024".

Given a user question, write up to {MAX_REWRITES} search queries that would find the passages needed to answer it.
- Use the wording the documents themselves would use (regulation terms such as "section", "operator", "consent"; report terms such as "levelised cost of electricity", "weighted average", "entitlement production"), not the question's paraphrase.
- If the question needs several separate facts, write one query per fact.
- If the question is simple and already well worded, write one query or none.
- Do not answer the question and do not invent numbers.

Reply with one JSON object and nothing else: {{"queries": ["<query>", ...]}}"""


# Variant 2 (18 Nov, after the first dev run): v1 listed the six documents and mini put guessed document names into the queries,
# which pulled in off-topic chunks. v2 does not list the documents and forbids naming one unless the question does.
REWRITE_SYSTEM_PROMPT_V2 = f"""You help a search system find passages in a collection of public energy documents (an annual report, safety regulations and a cost report).

Given a user question, write up to {MAX_REWRITES} search queries that would find the passages needed to answer it.
- Keep the question's own key terms. You may add the technical wording the documents would use for the same thing.
- Do not name a document, regulation or company unless the question itself names it.
- If the question needs several separate facts, write one query per fact.
- If the question is simple and already well worded, write one query or none.
- Do not answer the question and do not invent numbers.

Reply with one JSON object and nothing else: {{"queries": ["<query>", ...]}}"""

PROMPTS = {"v1": REWRITE_SYSTEM_PROMPT, "v2": REWRITE_SYSTEM_PROMPT_V2}


def parse_queries(raw: str) -> list[str]:
    """The rewritten queries from the model's reply, at most MAX_REWRITES, blanks and duplicates dropped.
    A malformed reply gives [] (the search then runs on the original question alone)."""
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        queries = json.loads(text)["queries"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    if not isinstance(queries, list):
        return []
    out: list[str] = []
    for q in queries:
        if isinstance(q, str) and q.strip() and q.strip() not in out:
            out.append(q.strip())
    return out[:MAX_REWRITES]


def rewrite_queries(question: str, model: str | None = None, prompt: str = "v1", missing: str | None = None) -> list[str]:
    """[question, rewrite 1, ...]: the original first, then the model's rewrites (without a copy of the original).
    `missing` (from the grader) says what the first search did not find; the rewrites then aim at that gap."""
    user = f"Question: {question}"
    if missing:
        user += f"\n\nA first search did not find enough. What is missing: {missing}"
    reply = complete(user, system=PROMPTS[prompt], model=model or config.GENERATION_MODEL,
                     purpose="rewrite")
    return [question] + [q for q in parse_queries(reply.text) if q != question]


def multi_search(queries: list[str], k: int, mode: str = "hybrid", pool: int | None = None,
                 keep: int | None = None) -> list[Hit]:
    """Search with every query (each returns its `pool` best chunks) and return k chunks.

    The first query is the original question. Its top `keep` chunks always come first, in its own order; the other
    slots are filled from the RRF merge of all queries. So a rewrite can add chunks but cannot push out what the plain
    search had ranked highest. (Plain RRF over all lists did that on dev: equinor_ar2025-114 was lost.)
    The score of every returned chunk is its RRF score; the kept chunks are not sorted by it.
    """
    pool = pool or config.RETRIEVE_CANDIDATES
    keep = config.REWRITE_KEEP_TOP if keep is None else keep
    by_id: dict[str, Hit] = {}
    rankings: list[list[str]] = []
    for q in queries:
        hits = search(q, mode, pool).hits
        by_id.update({h.chunk_id: h for h in hits})
        rankings.append([h.chunk_id for h in hits])
    fused = rrf(rankings)
    scores = dict(fused)
    first = rankings[0][:min(keep, k)]
    rest = [cid for cid, _ in fused if cid not in first]
    ids = first + rest[:k - len(first)]
    return [replace(by_id[cid], score=scores[cid]) for cid in ids]
