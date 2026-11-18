"""Does query rewriting find gold evidence that the plain question misses? Retrieval only, no answering.

    uv run python eval/rewrite_probe.py --split dev --tag rw1

For each answerable, non-holistic question of the split: baseline = hybrid search on the question (k = 10), rewrite =
the question plus the model's rewritten queries, merged by RRF (k = 10). Scored with the same matcher and metrics as
`retrieval_eval.py`; reported per tier with n, bootstrap intervals and the paired difference (rewrite minus baseline).
Key `rewrite_<split>_<tag>` in results/results.json, per-question dump results/rewrite_<split>_<tag>_per_question.json
(the queries and the metrics, so any number can be traced). Dev is for choosing; a test run needs its own tag.
"""

import hashlib
import json
import sys
from collections import defaultdict

from retrieval_eval import K, SPLITS, load_questions, score  # same eligible questions and metrics as the retrieval eval

from rag import config
from rag.llm import spent_usd
from rag.matcher import index_chunks
from rag.retrieve import search
from rag.rewrite import PROMPTS, multi_search, rewrite_queries
from rag.runstate import git_sha
from rag.splits import round_of
from rag.stats import bootstrap_ci, paired_bootstrap_diff

METRICS = ["hit@10", "coverage@10", "mrr@10", "ndcg@10"]


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> None:
    split, tag = option("--split", "dev"), option("--tag", "rw1")
    model = option("--model", config.GENERATION_MODEL)
    prompt = option("--prompt", "v1")
    questions = load_questions(split, SPLITS.parent / "questions.jsonl")
    with open(config.CHUNKS_PATH, encoding="utf-8") as f:
        index = index_chunks([json.loads(line) for line in f])
    before = spent_usd()

    per_q: dict[str, dict] = {}
    for q in questions:
        queries = rewrite_queries(q["question"], model=model, prompt=prompt)
        base = score(search(q["question"], "hybrid", K).hits, q["gold"], index)
        new = score(multi_search(queries, K), q["gold"], index)
        per_q[q["id"]] = {"queries": queries, "baseline": base, "rewrite": new}

    out: dict = {"split": split, "model": model, "prompt": prompt, "prompt_sha": hashlib.sha256(PROMPTS[prompt].encode("utf-8")).hexdigest()[:12], "git": git_sha(), "k": K, "n_queries_mean": 0.0, "per_tier": {}, "paired_diff": {}}
    out["n_queries_mean"] = round(sum(len(v["queries"]) for v in per_q.values()) / len(per_q), 2)
    by_tier: dict[int, list[str]] = defaultdict(list)
    for qid in per_q:
        by_tier[round_of({"id": qid})].append(qid)
    for tier in (1, 2, 3):
        ids = by_tier[tier]
        for name in ("baseline", "rewrite"):
            out["per_tier"].setdefault(f"round_{tier}", {})[name] = {"n": len(ids)} | {
                m: dict(zip(("mean", "ci_low", "ci_high"), (round(x, 4) for x in bootstrap_ci([per_q[i][name][m] for i in ids])), strict=True))
                for m in METRICS}
        for m in ("hit@10", "coverage@10", "mrr@10"):
            mean, lo, hi = paired_bootstrap_diff([per_q[i]["rewrite"][m] for i in ids], [per_q[i]["baseline"][m] for i in ids])
            out["paired_diff"][f"round_{tier}_{m}_rewrite_minus_baseline"] = {
                "n": len(ids), "mean": round(mean, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4)}

    path = config.RESULTS_DIR / "results.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    results[f"rewrite_{split}_{tag}"] = out
    path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    (config.RESULTS_DIR / f"rewrite_{split}_{tag}_per_question.json").write_text(
        json.dumps(per_q, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"rewrite_{split}_{tag}: {len(per_q)} questions, {out['n_queries_mean']} queries per question on average, spent ${spent_usd() - before:.4f}")
    for tier, per in out["per_tier"].items():
        for name, m in per.items():
            print(f"  {tier} {name:<8} n={m['n']:<3} hit@10 {m['hit@10']['mean']:.2f} [{m['hit@10']['ci_low']:.2f}, {m['hit@10']['ci_high']:.2f}]"
                  f"  coverage@10 {m['coverage@10']['mean']:.2f}  mrr@10 {m['mrr@10']['mean']:.2f}")
    for name, d in out["paired_diff"].items():
        print(f"  {name}: {d['mean']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] n={d['n']}")


if __name__ == "__main__":
    main()
