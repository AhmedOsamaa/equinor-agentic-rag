"""Retrieval evaluation: vector vs hybrid vs hybrid_rerank, no LLM involved.

Run: uv run python eval/retrieval_eval.py [--split dev|test] [--tag NAME]

For every eligible question (behaviour == "answerable", type != "holistic", in the chosen
split) it runs `search`, scores the ranking against the gold evidence with `rag.matcher` and
`rag.metrics`, and reports per tier (never one blended number) with bootstrap intervals and n.
`dev` runs are pilots. A run with the same split and tag overwrites its key in results.json, so use --tag
to keep an earlier run (the committed retrieval_test_final is overwritten by --split test --tag final).

Writes results/results.json (key retrieval_<split>) and a per-question dump with the chunk ids
and gains, so any number can be traced back to a ranking.
"""

import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from tqdm import tqdm

from rag import config
from rag.matcher import gains as gains_of
from rag.matcher import ideal_gains, index_chunks
from rag.metrics import coverage_at_k, hit_at_k, mrr_at_k, ndcg_at_k
from rag.retrieve import search
from rag.runstate import (
    STATUS_PATH,
    git_sha,
    progress_fields,
    write_status,
)
from rag.splits import primary_doc, round_of
from rag.stats import bootstrap_ci, paired_bootstrap_diff

SPLITS = Path("eval/splits.json")
K = 10
METRICS = ["hit@5", "hit@10", "coverage@10", "mrr@10", "ndcg@10"]
DIFFS = [("hybrid", "vector"), ("hybrid_rerank", "hybrid")]  # (a, b): a minus b
DIFF_METRICS = ["hit@10", "mrr@10", "ndcg@10"]


def load_questions(split: str, path: Path) -> list[dict]:
    """Eligible questions of one split: answerable and not holistic.

    The default source is eval/questions.jsonl (the reviewed set, which carries its split). A
    candidates folder (--questions eval/candidates) is still accepted for comparisons with earlier pilots.
    """
    assignment = json.loads(SPLITS.read_text(encoding="utf-8"))["split"]
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    items = []
    for f in files:
        items += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [
        i for i in items
        if assignment[i["id"]] == split and i["behaviour"] == "answerable" and i["type"] != "holistic"
    ]


def score(hits, gold, index) -> dict[str, float]:
    g = gains_of(hits, gold)
    ideal = ideal_gains(gold, index, 10)
    out = {
        "hit@5": hit_at_k(g, 5),
        "hit@10": hit_at_k(g, 10),
        "coverage@10": coverage_at_k(hits, gold, 10),
        "mrr@10": mrr_at_k(g, 10),
        "ndcg@10": ndcg_at_k(g, 10, ideal),
    }
    # A metric outside [0, 1] is a bug in the metric or the matcher (nDCG once reached 1.2): stop, do not report it.
    bad = {k: v for k, v in out.items() if not -1e-9 <= v <= 1 + 1e-9}
    if bad:
        raise ValueError(f"metric outside [0, 1]: {bad}; gains {g}, ideal {ideal}")
    return out


def run(questions: list[dict], modes: list[str], index, on_step=None) -> tuple[dict, dict, dict]:
    """Return (per-question metrics, rankings with gains, timings), each keyed by mode first.

    A tqdm bar shows progress in the terminal; `on_step(mode, done, total)` lets the caller (the
    dashboard's status file) follow the same progress.
    """
    per_q: dict[str, dict] = {m: {} for m in modes}
    dumps: dict[str, dict] = {m: {} for m in modes}
    timings: dict[str, list[float]] = {m: [] for m in modes}
    total, done = len(modes) * len(questions), 0
    with tqdm(total=total, desc="retrieval eval", unit="q", dynamic_ncols=True) as bar:
        for mode in modes:
            bar.set_postfix(mode=mode + " (loading)", refresh=True)
            search(questions[0]["question"], mode, K)  # first call loads the models; not timed
            bar.set_postfix(mode=mode, refresh=True)
            for q in questions:
                res = search(q["question"], mode, K)
                per_q[mode][q["id"]] = score(res.hits, q["gold"], index)
                dumps[mode][q["id"]] = {
                    "chunk_ids": [h.chunk_id for h in res.hits],
                    "gains": gains_of(res.hits, q["gold"]),
                }
                timings[mode].append(res.timings["total"])
                done += 1
                bar.update(1)
                if on_step:
                    on_step(mode, done, total)
    return per_q, dumps, timings


def mode_metrics(ids: list[str], per_q: dict, modes: list[str]) -> dict:
    """Mean and bootstrap interval of every metric, per mode, over the given question ids."""
    out = {}
    for mode in modes:
        out[mode] = {}
        for metric in METRICS:
            mean, lo, hi = bootstrap_ci([per_q[mode][i][metric] for i in ids])
            out[mode][metric] = {"mean": mean, "ci_low": lo, "ci_high": hi}
    return out


BREAKDOWNS = {  # dimension -> how to read it from a question
    "type": lambda q: q["type"],
    "format": lambda q: q["format"],
    "document": primary_doc,  # the document of the first gold entry
}


def summarise_groups(questions: list[dict], per_q: dict, modes: list[str]) -> tuple[dict, dict]:
    """Descriptive breakdowns by type, format and document (each pooled across tiers, with the
    number of questions from each tier so the mix is visible), and one pooled row over everything.

    Pooling mixes tiers of different difficulty, so none of this is a headline number; the
    per-tier view in `summarise` is the main result. Small groups get an interval that means little;
    the dashboard shows n next to every row.
    """
    breakdowns: dict[str, dict] = {}
    for dim, key in BREAKDOWNS.items():
        groups: dict[str, list[dict]] = defaultdict(list)
        for q in questions:
            groups[key(q)].append(q)
        breakdowns[dim] = {}
        for value, qs in sorted(groups.items()):
            tier_n = defaultdict(int)
            for q in qs:
                tier_n[f"round_{round_of(q)}"] += 1
            breakdowns[dim][value] = {"n": len(qs), "n_by_tier": dict(sorted(tier_n.items())),
                                      "modes": mode_metrics([q["id"] for q in qs], per_q, modes)}
    ids = [q["id"] for q in questions]
    return breakdowns, {"n": len(ids), "modes": mode_metrics(ids, per_q, modes)}


def summarise(questions: list[dict], per_q: dict, modes: list[str]) -> dict:
    """Per tier: n, mean and interval per mode and metric, plus paired differences."""
    tiers: dict[int, list[str]] = defaultdict(list)
    for q in questions:
        tiers[round_of(q)].append(q["id"])
    out = {}
    for tier, ids in sorted(tiers.items()):
        block = {"n": len(ids), "modes": mode_metrics(ids, per_q, modes), "paired_diffs": {}}
        for a, b in DIFFS:
            if a not in per_q or b not in per_q:
                continue  # a partial run (--modes) has no such pair
            for metric in DIFF_METRICS:
                d, lo, hi = paired_bootstrap_diff(
                    [per_q[a][i][metric] for i in ids], [per_q[b][i][metric] for i in ids]
                )
                block["paired_diffs"][f"{a} - {b} | {metric}"] = {
                    "diff": d, "ci_low": lo, "ci_high": hi, "supported": lo > 0 or hi < 0,
                }
        out[f"round_{tier}"] = block
    return out


def print_report(summary: dict, timings: dict, split: str) -> None:
    label = "PILOT on dev" if split == "dev" else f"FINAL on {split}"
    print(f"\n=== retrieval eval ({label}); mean [95% bootstrap CI], k={K} ===")
    for tier, block in summary.items():
        print(f"\n{tier}  (n = {block['n']})")
        print(f"  {'mode':<15}" + "".join(f"{m:>22}" for m in METRICS))
        for mode, metrics in block["modes"].items():
            cells = "".join(
                f"{metrics[m]['mean']:>9.2f} [{metrics[m]['ci_low']:.2f},{metrics[m]['ci_high']:.2f}]".rjust(22)
                for m in METRICS
            )
            print(f"  {mode:<15}{cells}")
        for name, d in block["paired_diffs"].items():
            flag = "interval excludes 0" if d["supported"] else "no supported difference"
            print(f"  {name:<34}{d['diff']:>+7.3f} [{d['ci_low']:+.3f},{d['ci_high']:+.3f}]  {flag}")
    print("\nmean latency per query (s, warm):")
    for mode, ts in timings.items():
        print(f"  {mode:<15}{sum(ts) / len(ts):.3f}")


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> None:
    """Run the eval; the status file (read by the dashboard) records running, done or error."""
    try:
        _main()
    except SystemExit as e:
        if e.code not in (None, 0):
            write_status(STATUS_PATH, state="error", message=str(e.code))
        raise
    except BaseException as e:
        write_status(STATUS_PATH, state="error", message=f"{type(e).__name__}: {e}")
        raise


def _main() -> None:
    split = option("--split", "dev")
    # --modes a,b runs only those modes; --tag NAME keeps the output apart from the main run;
    # --rerank-model ID tries another cross-encoder without editing config.py.
    modes = option("--modes", ",".join(config.RETRIEVE_MODES)).split(",")
    tag = option("--tag", "")
    if option("--rerank-model", ""):
        config.RERANK_MODEL = option("--rerank-model", "")
    source = Path(option("--questions", "eval/questions.jsonl"))
    questions = load_questions(split, source)
    print(f"{len(questions)} eligible {split} questions from {source} (answerable, not holistic); modes {modes}")

    with open(config.CHUNKS_PATH, encoding="utf-8") as f:
        index = index_chunks([json.loads(line) for line in f])
    key = f"retrieval_{split}{'_' + tag if tag else ''}"
    started, total = time.monotonic(), len(questions) * len(modes)
    config.RESULTS_DIR.mkdir(exist_ok=True)
    write_status(STATUS_PATH, state="running", split=split, tag=tag, key=key, mode="starting",
                 **progress_fields(0, total, started))

    def on_step(mode: str, done: int, total: int) -> None:
        write_status(STATUS_PATH, state="running", split=split, tag=tag, key=key, mode=mode,
                     **progress_fields(done, total, started))

    per_q, dumps, timings = run(questions, modes, index, on_step)
    summary = summarise(questions, per_q, modes)
    breakdowns, pooled = summarise_groups(questions, per_q, modes)
    print_report(summary, timings, split)

    config.RESULTS_DIR.mkdir(exist_ok=True)
    stamp = {
        "git_sha": git_sha(),
        "time_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "pilot": split == "dev",
        "split": split,
        "question_source": str(source),
        "k": K,
        "settings": {
            "chunk_max_tokens": config.CHUNK_MAX_TOKENS,
            "prefix_heading_path": config.CHUNK_PREFIX_HEADING_PATH,
            "bm25_use_embed_text": config.BM25_USE_EMBED_TEXT,
            "rrf_k": config.RRF_K,
            "rerank_candidates": config.RERANK_CANDIDATES,
            "embed_model": config.EMBED_MODEL,
            "rerank_model": config.RERANK_MODEL,
            "bootstrap_resamples": config.BOOTSTRAP_RESAMPLES,
        },
        "mean_latency_s": {m: sum(t) / len(t) for m, t in timings.items()},
        "tiers": summary,
        "breakdowns": breakdowns,
        "pooled": pooled,
    }
    path = config.RESULTS_DIR / "results.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    suffix = f"_{tag}" if tag else ""
    results[f"retrieval_{split}{suffix}"] = stamp
    path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    dump_path = config.RESULTS_DIR / f"retrieval_{split}{suffix}_per_question.json"
    dump_path.write_text(json.dumps({"per_question": per_q, "rankings": dumps}, indent=1), encoding="utf-8")
    print(f"\nwritten {path} and {dump_path}")
    write_status(STATUS_PATH, state="done", split=split, tag=tag, key=key, mode="",
                 **progress_fields(total, total, started))


if __name__ == "__main__":
    main()
