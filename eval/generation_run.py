"""Answer questions from retrieved chunks and save everything needed to judge the answers by hand.

    uv run python eval/generation_run.py --split dev --tag pilot1 --ids equinor_ar2025-028,irena_rpgc2024-020
    uv run python eval/generation_run.py --split dev --tag pilot1 --limit 5
    uv run python eval/generation_run.py --split dev --tag pilot1          # the whole dev split

For each question: retrieve (hybrid, k = 10), build the prompt, call config.GENERATION_MODEL, parse the JSON reply. One line per
question goes to results/generation_<split>_<tag>.jsonl. This is a pilot tool: it measures nothing, it collects answers. The
only checks it makes by itself are mechanical ones (did the reply parse, were the cited numbers real, does a cited chunk
contain a gold quote); whether an answer is correct and faithful is judged separately (see generation_report.py).

All behaviours are included (answerable, unanswerable, ambiguous), because the point is to see what the model does when the
evidence is missing. Holistic questions are included too; they have no gold quotes.
"""

import hashlib
import json
import sys
from pathlib import Path

from rag import config
from rag.evidence import contains_quote
from rag.generation import CLOSED_BOOK_SYSTEM_PROMPT, SYSTEM_PROMPT, build_prompt, parse_answer
from rag.llm import complete_many, model_params, spent_usd
from rag.retrieve import search
from rag.runstate import git_sha

SPLITS = Path("eval/splits.json")
QUESTIONS = Path("eval/questions.jsonl")
K = 10
RETRIEVAL_MODE = "hybrid"


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load_split(split: str) -> list[dict]:
    assignment = json.loads(SPLITS.read_text(encoding="utf-8"))["split"]
    items = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [q for q in items if assignment[q["id"]] == split]


def cited_checks(answer, hits, gold) -> dict:
    """Mechanical checks on the citations. `cited_gold`: a cited chunk (right document) contains a gold quote.
    `retrieved_gold`: some chunk in the top k does, whether or not it was cited. Both are None without gold quotes."""
    if not gold:
        return {"bad_citation_numbers": [], "cited_gold": None, "retrieved_gold": None}
    holds = [any(h.doc_id == g["doc_id"] and contains_quote(h.text, g["evidence_quote"]) for g in gold) for h in hits]
    if answer is None:
        return {"bad_citation_numbers": [], "cited_gold": None, "retrieved_gold": any(holds)}
    valid = [n for n in answer.citations if 1 <= n <= len(hits)]
    return {"bad_citation_numbers": [n for n in answer.citations if n not in valid],
            "cited_gold": any(holds[n - 1] for n in valid), "retrieved_gold": any(holds)}


def main() -> None:
    split, tag = option("--split", "dev"), option("--tag", "")
    model = option("--model", config.GENERATION_MODEL)   # same prompt and retrieval, only the model changes
    questions = load_split(split)
    if option("--ids", ""):
        wanted = option("--ids", "").split(",")
        questions = [q for q in questions if q["id"] in wanted]
        missing = set(wanted) - {q["id"] for q in questions}
        if missing:
            raise SystemExit(f"not in the {split} split: {sorted(missing)}")
    if option("--limit", ""):
        questions = questions[: int(option("--limit", ""))]
    closed_book = "--closed-book" in sys.argv   # no retrieval, no passages: what the model knows on its own
    system = CLOSED_BOOK_SYSTEM_PROMPT if closed_book else SYSTEM_PROMPT
    print(f"{len(questions)} {split} questions, model {model}, " + ("closed book" if closed_book else f"{RETRIEVAL_MODE} k={K}"))

    retrieved = [[] if closed_book else search(q["question"], RETRIEVAL_MODE, K).hits for q in questions]
    prompts = [f"Question: {q['question']}" if closed_book else build_prompt(q["question"], hits)
               for q, hits in zip(questions, retrieved, strict=True)]
    before = spent_usd()
    results = complete_many(prompts, system=system, model=model, purpose="generation")

    out = config.RESULTS_DIR / f"generation_{split}{'_' + tag if tag else ''}.jsonl"
    out.parent.mkdir(exist_ok=True)
    if split == "test" and out.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{out} exists. A test run gets its own tag; overwrite only on purpose with --force.")
    stamp = {"git": git_sha(), "prompt_sha": hashlib.sha256(system.encode("utf-8")).hexdigest()[:12],
             "chunks_sha": hashlib.sha256(config.CHUNKS_PATH.read_bytes()).hexdigest()[:12],
             "retrieval": "none (closed book)" if closed_book else RETRIEVAL_MODE, "k": 0 if closed_book else K,
             "model_params": model_params(model)}
    unparsed = 0
    with open(out, "w", encoding="utf-8") as f:
        for q, hits, res in zip(questions, retrieved, results, strict=True):
            answer = parse_answer(res.text)
            unparsed += answer is None
            record = {
                "id": q["id"], "question": q["question"], "behaviour": q["behaviour"], "type": q["type"], "format": q["format"],
                "reference_answer": q["reference_answer"], "gold": q["gold"],
                "model": model, "stamp": stamp, "raw_reply": res.text,
                "status": answer.status if answer else None, "answer": answer.answer if answer else None,
                "citations": answer.citations if answer else None,
                **cited_checks(answer, hits, q["gold"]),
                "retrieved": [{"n": i, "chunk_id": h.chunk_id, "doc_id": h.doc_id, "page": h.page} for i, h in enumerate(hits, 1)],
                "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
                "latency_s": round(res.latency_s, 2), "cached": res.cached,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for line in out.read_text(encoding="utf-8").splitlines():
        s = json.loads(line)["status"] or "UNPARSED"
        counts[s] = counts.get(s, 0) + 1
    print(f"wrote {out}\nstatus counts: {counts}  (unparsed replies: {unparsed})")
    print(f"spent this run ${spent_usd() - before:.4f}; total logged ${spent_usd():.4f} of the ${config.LLM_BUDGET_USD:.2f} cap")


if __name__ == "__main__":
    main()
