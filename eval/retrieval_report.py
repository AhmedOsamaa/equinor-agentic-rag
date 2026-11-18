"""Readable report from a finished retrieval eval run (no search is re-run).

Run: uv run python eval/retrieval_report.py [--split dev]

Reads results/results.json and results/retrieval_<split>_per_question.json and writes
results/retrieval_<split>_report.md with (1) the per-tier table and (2) every question where
some mode has no chunk containing the gold quote in its top 10, with the question, the gold
evidence and the top 3 chunks of each failing mode. A miss with a gain-1 chunk (right page, quote
not in the chunk) is flagged: it may be a label problem (quote split across chunks) and not a
retrieval failure.
"""

import json
import sys
from pathlib import Path

from rag import config
from rag.splits import round_of

CANDIDATES = Path("eval/candidates")
METRICS = ["hit@5", "hit@10", "coverage@10", "mrr@10", "ndcg@10"]
SNIPPET = 300


def load_questions() -> dict[str, dict]:
    out = {}
    for path in sorted(CANDIDATES.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                out[item["id"]] = item
    return out


def load_chunks() -> dict[str, dict]:
    with config.CHUNKS_PATH.open(encoding="utf-8") as f:
        return {c["chunk_id"]: c for c in map(json.loads, f)}


def snippet(text: str) -> str:
    flat = " ".join(text.split())
    return flat[:SNIPPET] + ("..." if len(flat) > SNIPPET else "")


def table_section(results: dict, split: str) -> list[str]:
    run = results[f"retrieval_{split}"]
    label = "PILOT" if run["pilot"] else "FINAL"
    lines = [
        f"# Retrieval eval, {split} ({label})",
        "",
        f"git `{run['git_sha']}`, {run['time_utc']}, k={run['k']}. Mean [95% bootstrap CI]; "
        + "n is the number of questions in the tier. Never blend the tiers.",
        "",
    ]
    for tier, block in run["tiers"].items():
        lines += [f"## {tier} (n = {block['n']})", "", "| mode | " + " | ".join(METRICS) + " |",
                  "|---|" + "---|" * len(METRICS)]
        for mode, metrics in block["modes"].items():
            cells = " | ".join(
                f"{metrics[m]['mean']:.2f} [{metrics[m]['ci_low']:.2f}, {metrics[m]['ci_high']:.2f}]" for m in METRICS
            )
            lines.append(f"| {mode} | {cells} |")
        lines += ["", "Paired differences (a - b):", ""]
        for name, d in block["paired_diffs"].items():
            verdict = "interval excludes 0" if d["supported"] else "no supported difference"
            lines.append(f"- {name}: {d['diff']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}], {verdict}")
        lines.append("")
    lines += ["Mean latency per query (s, warm): "
              + ", ".join(f"{m} {t:.3f}" for m, t in run["mean_latency_s"].items()), ""]
    return lines


def miss_section(dump: dict, questions: dict, chunks: dict) -> list[str]:
    rankings = dump["rankings"]
    modes = list(rankings)
    ids = sorted(rankings[modes[0]], key=lambda i: (round_of(questions[i]), i))
    missed = [i for i in ids if any(max(rankings[m][i]["gains"], default=0) < 2 for m in modes)]
    lines = [f"# Misses: {len(missed)} of {len(ids)} questions have no quote chunk in the top 10 for at least one mode",
             ""]
    for qid in missed:
        q = questions[qid]
        lines += [f"## {qid} (round {round_of(q)}, type {q['type']}, format {q['format']})", "",
                  f"**Question:** {q['question']}", "", "**Gold evidence:**"]
        lines += [f"- {g['doc_id']} p{g['page']}: \"{g['evidence_quote']}\"" for g in q["gold"]]
        lines.append("")
        for mode in modes:
            r = rankings[mode][qid]
            first = next((rank for rank, g in enumerate(r["gains"], 1) if g >= 2), None)
            if first is not None:
                lines.append(f"- {mode}: quote chunk at rank {first}")
                continue
            note = ""
            if 1 in r["gains"]:
                note = " (a right-page chunk without the quote is in the top 10: check for a split quote)"
            lines += ["", f"**{mode}: MISS**{note}", ""]
            for rank, cid in enumerate(r["chunk_ids"][:3], 1):
                c = chunks[cid]
                lines.append(f"{rank}. gain {r['gains'][rank - 1]}, {c['doc_id']} p{c['page']}, "
                             f"`{' > '.join(c['heading_path'])}`: {snippet(c['text'])}")
            lines.append("")
    return lines


def main() -> None:
    split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "dev"
    results = json.loads((config.RESULTS_DIR / "results.json").read_text(encoding="utf-8"))
    dump = json.loads((config.RESULTS_DIR / f"retrieval_{split}_per_question.json").read_text(encoding="utf-8"))
    lines = table_section(results, split) + miss_section(dump, load_questions(), load_chunks())
    out = config.RESULTS_DIR / f"retrieval_{split}_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()
