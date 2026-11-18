"""Run the tool-calling agent (`rag.agent.ask`) on a split and save the answers for judging.

    uv run python eval/agent_run.py --split dev --tag agent_tool --limit 5
    uv run python eval/agent_run.py --split dev --tag agent_tool            # the whole dev split

The output has the same format as `generation_run.py` (file `results/generation_<split>_<tag>.jsonl`), so the same judging and
`generation_report.py` apply, plus the agent's own fields: `n_searches` and the `trace` (one entry per model call). Compare the
judged result with the fixed pipeline's run on the same questions, paired (the mini dev run is tag `pilot1_mini`).

Test split: refused unless `--test-ok` is given. Each run on test is a further look at it that the README must disclose.
"""

import hashlib
import json
import sys
from dataclasses import asdict

from generation_run import cited_checks, load_split, option

from rag import agent, config
from rag.llm import model_params, spent_usd
from rag.runstate import git_sha


def main() -> None:
    split, tag = option("--split", "dev"), option("--tag", "")
    model = option("--model", config.AGENT_MODEL)
    if split == "test" and "--test-ok" not in sys.argv:
        raise SystemExit("test split: pass --test-ok on purpose (a further look at test; disclose it).")
    questions = load_split(split)
    if option("--ids", ""):
        wanted = option("--ids", "").split(",")
        questions = [q for q in questions if q["id"] in wanted]
        missing = set(wanted) - {q["id"] for q in questions}
        if missing:
            raise SystemExit(f"not in the {split} split: {sorted(missing)}")
    if option("--limit", ""):
        questions = questions[: int(option("--limit", ""))]
    out = config.RESULTS_DIR / f"generation_{split}{'_' + tag if tag else ''}.jsonl"
    if out.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{out} exists; use a new tag, or --force on purpose.")
    print(f"{len(questions)} {split} questions, model {model}, hybrid k={config.AGENT_K}, max searches {config.AGENT_MAX_SEARCHES}")

    stamp = {"git": git_sha(), "prompt_sha": hashlib.sha256(agent.SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12],
             "chunks_sha": hashlib.sha256(config.CHUNKS_PATH.read_bytes()).hexdigest()[:12],
             "retrieval": agent.RETRIEVAL_MODE, "k": config.AGENT_K, "model_params": model_params(model),
             "agent": {"max_searches": config.AGENT_MAX_SEARCHES, "tool": "search_documents"}}
    before = spent_usd()
    counts: dict[str, int] = {}
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for i, q in enumerate(questions, start=1):
            res = agent.ask(q["question"], model=model)
            ok = res.status != "error"
            counts[res.status] = counts.get(res.status, 0) + 1
            parsed = type("A", (), {"citations": res.citations})() if ok else None   # cited_checks wants `.citations`, or None
            record = {
                "id": q["id"], "question": q["question"], "behaviour": q["behaviour"], "type": q["type"], "format": q["format"],
                "reference_answer": q["reference_answer"], "gold": q["gold"],
                "model": model, "stamp": stamp, "raw_reply": None,
                "status": res.status if ok else None, "answer": res.answer, "citations": res.citations if ok else None,
                **cited_checks(parsed, res.hits, q["gold"]),
                "retrieved": [{"n": n, "chunk_id": h.chunk_id, "doc_id": h.doc_id, "page": h.page} for n, h in enumerate(res.hits, 1)],
                "n_searches": res.n_searches, "trace": [asdict(s) for s in res.trace],
                "prompt_tokens": sum(s.prompt_tokens for s in res.trace),
                "completion_tokens": sum(s.completion_tokens for s in res.trace),
                "latency_s": round(sum(s.latency_s for s in res.trace), 2), "cached": None,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(questions)}] {q['id']}: {res.status} ({res.n_searches} searches)")

    print(f"wrote {out}\nstatus counts: {counts}")
    print(f"spent this run ${spent_usd() - before:.4f}; total logged ${spent_usd():.4f} of the ${config.LLM_BUDGET_USD:.2f} cap")


if __name__ == "__main__":
    main()
