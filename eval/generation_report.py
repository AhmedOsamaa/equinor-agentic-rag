"""Turn judged generation runs into numbers with n and bootstrap intervals, per tier, and write them to results/results.json.

    uv run python eval/generation_report.py --split test --tags nano_final,mini_final --judge claude

Input: results/generation_<split>_<tag>.jsonl (the answers) and results/generation_<split>_<tag>_<judge>_judgments.json (the
verdicts: correct and faithful, each yes / partly / no / na). The judge is named in the result key and in every table,
because a number is only as good as who judged it. `claude` verdicts come from an LLM judge (and Claude wrote round 3
and 30 rewrites); they are not human judgments. Use `--judge` with another judge's file name part (for example a human
reviewer's) to report those verdicts.

Per tier (round 1 / 2 / 3, never blended), for answerable questions:
  correct_strict   = share of 'yes'                         (partly and no count as not correct)
  correct_lenient  = share of 'yes' or 'partly'
  faithful_strict  = share of 'yes'
The non-answerable and ambiguous questions are counted separately (n is tiny). The paired difference between the first
two tags is on the same questions, so a hard question is hard for both; if its interval contains 0, no difference is claimed.
"""

import json
import sys
from collections import Counter

from rag import config
from rag.splits import round_of
from rag.stats import bootstrap_ci, paired_bootstrap_diff


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load(split: str, tag: str, judge: str) -> tuple[dict, dict]:
    answers = {}
    for line in (config.RESULTS_DIR / f"generation_{split}_{tag}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        answers[r["id"]] = r
    verdicts = json.loads((config.RESULTS_DIR / f"generation_{split}_{tag}_{judge}_judgments.json").read_text(encoding="utf-8"))
    missing = set(answers) - set(verdicts)
    if missing:
        raise SystemExit(f"{tag}: {len(missing)} questions have no {judge} verdict, e.g. {sorted(missing)[:3]}")
    return answers, verdicts


def share(verdicts: list[dict], field: str, allowed: set[str]) -> list[float]:
    """1.0 for each verdict whose `field` is in `allowed`, else 0.0 (the per-question scores that get averaged)."""
    return [1.0 if v[field] in allowed else 0.0 for v in verdicts]


def interval(scores: list[float]) -> dict:
    mean, lo, hi = bootstrap_ci(scores)
    return {"n": len(scores), "mean": round(mean, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4)}


def main() -> None:
    split, judge = option("--split", "test"), option("--judge", "claude")
    tags = option("--tags", "nano_final,mini_final").split(",")
    data = {t: load(split, t, judge) for t in tags}
    ids = sorted(data[tags[0]][0])
    answerable = [i for i in ids if data[tags[0]][0][i]["behaviour"] == "answerable"]

    out: dict = {"judge": judge, "split": split, "tags": tags, "n_questions": len(ids), "n_answerable": len(answerable),
                 "per_tier": {}, "non_answerable": {}, "paired_diff": {}}
    for tag, (answers, verdicts) in data.items():
        sample = next(iter(answers.values()))
        # Runs made before stamping was added (the dev pilots) have no stamp; say so instead of guessing one.
        out.setdefault("runs", {})[tag] = {"model": sample["model"], "stamp": sample.get("stamp", "none: run before stamping existed")}
        for tier in (1, 2, 3):
            tier_ids = [i for i in answerable if round_of({"id": i}) == tier]
            v = [verdicts[i] for i in tier_ids]
            out["per_tier"].setdefault(f"round_{tier}", {})[tag] = {
                "correct_strict": interval(share(v, "correct", {"yes"})),
                "correct_lenient": interval(share(v, "correct", {"yes", "partly"})),
                "faithful_strict": interval(share(v, "faithful", {"yes"})),
                "answered": interval([1.0 if answers[i]["status"] == "answered" else 0.0 for i in tier_ids]),
            }
        for behaviour in ("unanswerable_out", "unanswerable_near", "ambiguous"):
            b_ids = [i for i in ids if answers[i]["behaviour"] == behaviour]
            out["non_answerable"].setdefault(behaviour, {})[tag] = {
                "n": len(b_ids), "correct": dict(Counter(verdicts[i]["correct"] for i in b_ids)),
                "status": dict(Counter(answers[i]["status"] for i in b_ids))}
    if len(tags) >= 2:
        a, b = tags[1], tags[0]   # second minus first: with the default order, mini minus nano
        for tier in (1, 2, 3):
            tier_ids = [i for i in answerable if round_of({"id": i}) == tier]
            sa = [1.0 if data[a][1][i]["correct"] == "yes" else 0.0 for i in tier_ids]
            sb = [1.0 if data[b][1][i]["correct"] == "yes" else 0.0 for i in tier_ids]
            mean, lo, hi = paired_bootstrap_diff(sa, sb)
            out["paired_diff"][f"round_{tier}_correct_strict_{a}_minus_{b}"] = {
                "n": len(tier_ids), "mean": round(mean, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4)}

    path = config.RESULTS_DIR / "results.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    key = f"generation_{split}_review_{judge}" + (f"_{option('--name', '')}" if option("--name", "") else "")
    results[key] = out
    path.write_text(json.dumps(results, indent=1), encoding="utf-8")

    print(f"{key}: judge = {judge}; answerable n = {len(answerable)} (rounds: "
          + ", ".join(f"{t}: {sum(round_of({'id': i}) == t for i in answerable)}" for t in (1, 2, 3)) + ")")
    for tier, per_tag in out["per_tier"].items():
        for tag, m in per_tag.items():
            c, f = m["correct_strict"], m["faithful_strict"]
            print(f"  {tier} {tag:<11} n={c['n']:<3} correct(yes) {c['mean']:.2f} [{c['ci_low']:.2f}, {c['ci_high']:.2f}]"
                  f"  lenient {m['correct_lenient']['mean']:.2f}  faithful(yes) {f['mean']:.2f} [{f['ci_low']:.2f}, {f['ci_high']:.2f}]"
                  f"  answered {m['answered']['mean']:.2f}")
    for name, d in out["paired_diff"].items():
        print(f"  {name}: {d['mean']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] n={d['n']}")
    print(f"written {path} key {key}")


if __name__ == "__main__":
    main()
