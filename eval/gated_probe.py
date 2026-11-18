"""Rewrite only when needed: grade the plain top 10, and only if it is judged insufficient, rewrite and merge. Retrieval only.

    uv run python eval/gated_probe.py --split dev --tag gate1 [--prompt v2]

Per answerable, non-holistic question: baseline = hybrid k = 10; the grader (rag.grade, sees no gold) says sufficient or not;
if not, `rewrite_queries(question, missing=...)` and `multi_search` give the final top 10; if yes, final = baseline.
Reported per tier: hit@10 / coverage@10 / MRR for baseline and gated, paired difference, and how often the grader fired,
split by whether the baseline was in fact complete (coverage@10 = 1) or not. Key `gated_<split>_<tag>` in results.json.
"""

import hashlib
import json
import sys
from collections import defaultdict

from retrieval_eval import K, SPLITS, load_questions, score

from rag import config
from rag.grade import GRADER_SYSTEM_PROMPT, grade_retrieval
from rag.llm import spent_usd
from rag.matcher import index_chunks
from rag.retrieve import search
from rag.rewrite import PROMPTS, multi_search, rewrite_queries
from rag.runstate import git_sha
from rag.splits import round_of
from rag.stats import bootstrap_ci, paired_bootstrap_diff

METRICS = ["hit@10", "coverage@10", "mrr@10"]


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> None:
    split, tag, prompt = option("--split", "dev"), option("--tag", "gate1"), option("--prompt", "v2")
    model = option("--model", config.GENERATION_MODEL)
    questions = load_questions(split, SPLITS.parent / "questions.jsonl")
    with open(config.CHUNKS_PATH, encoding="utf-8") as f:
        index = index_chunks([json.loads(line) for line in f])
    before = spent_usd()

    per_q: dict[str, dict] = {}
    for q in questions:
        base_hits = search(q["question"], "hybrid", K).hits
        base = score(base_hits, q["gold"], index)
        grade = grade_retrieval(q["question"], base_hits, model=model)
        queries, final = [q["question"]], base
        if not grade.sufficient:
            queries = rewrite_queries(q["question"], model=model, prompt=prompt, missing=grade.missing or None)
            final = score(multi_search(queries, K), q["gold"], index)
        per_q[q["id"]] = {"sufficient": grade.sufficient, "grade_parsed": grade.parsed, "missing": grade.missing,
                          "queries": queries, "baseline": base, "gated": final}

    out: dict = {"split": split, "model": model, "prompt": prompt, "git": git_sha(), "k": K,
                 "prompt_sha": hashlib.sha256(PROMPTS[prompt].encode("utf-8")).hexdigest()[:12],
                 "grader_sha": hashlib.sha256(GRADER_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12],
                 "unparsed_grades": sum(not v["grade_parsed"] for v in per_q.values()), "per_tier": {}, "paired_diff": {}, "trigger": {}}
    by_tier: dict[int, list[str]] = defaultdict(list)
    for qid in per_q:
        by_tier[round_of({"id": qid})].append(qid)
    for tier in (1, 2, 3):
        ids = by_tier[tier]
        for name in ("baseline", "gated"):
            out["per_tier"].setdefault(f"round_{tier}", {})[name] = {"n": len(ids)} | {
                m: dict(zip(("mean", "ci_low", "ci_high"), (round(x, 4) for x in bootstrap_ci([per_q[i][name][m] for i in ids])), strict=True))
                for m in METRICS}
        for m in METRICS:
            mean, lo, hi = paired_bootstrap_diff([per_q[i]["gated"][m] for i in ids], [per_q[i]["baseline"][m] for i in ids])
            out["paired_diff"][f"round_{tier}_{m}_gated_minus_baseline"] = {
                "n": len(ids), "mean": round(mean, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4)}
        complete_ids = [i for i in ids if per_q[i]["baseline"]["coverage@10"] >= 1.0]
        out["trigger"][f"round_{tier}"] = {
            "n": len(ids), "baseline_complete": len(complete_ids),
            "fired_on_complete": sum(not per_q[i]["sufficient"] for i in complete_ids),
            "baseline_incomplete": len(ids) - len(complete_ids),
            "fired_on_incomplete": sum(not per_q[i]["sufficient"] for i in ids if i not in complete_ids)}

    path = config.RESULTS_DIR / "results.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    results[f"gated_{split}_{tag}"] = out
    path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    (config.RESULTS_DIR / f"gated_{split}_{tag}_per_question.json").write_text(json.dumps(per_q, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"gated_{split}_{tag}: {len(per_q)} questions, unparsed grades {out['unparsed_grades']}, spent ${spent_usd() - before:.4f}")
    for tier, t in out["trigger"].items():
        print(f"  {tier}: grader fired on {t['fired_on_complete']} of {t['baseline_complete']} complete baselines and "
              f"{t['fired_on_incomplete']} of {t['baseline_incomplete']} incomplete ones")
    for tier, per in out["per_tier"].items():
        for name, m in per.items():
            print(f"  {tier} {name:<8} n={m['n']:<3} hit@10 {m['hit@10']['mean']:.2f}  coverage@10 {m['coverage@10']['mean']:.2f}  mrr@10 {m['mrr@10']['mean']:.2f}")
    for name, d in out["paired_diff"].items():
        print(f"  {name}: {d['mean']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] n={d['n']}")


if __name__ == "__main__":
    main()
