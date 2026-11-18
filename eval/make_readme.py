"""Render README.md from docs/README_template.md and results/results.json.

    uv run python eval/make_readme.py

Every number in the README comes from this script reading results.json; the template holds prose and placeholders only
({{RETRIEVAL}}, {{GENERATION}}, {{CLOSED}}, {{NONANS}}, {{AGENT}}).
"""

import json
import re
from pathlib import Path

RESULTS = json.loads(Path("results/results.json").read_text(encoding="utf-8"))
TIERS = ("round_1", "round_2", "round_3")
TIER_NAME = {"round_1": "Round 1 (easy, natural)", "round_2": "Round 2 (hard, synonym-swapped)", "round_3": "Round 3 (multi-page, Claude-written)"}


def ci(d: dict) -> str:
    return f"{d['mean']:.2f} [{d['ci_low']:.2f}, {d['ci_high']:.2f}]"


def retrieval() -> str:
    t = RESULTS["retrieval_test_tablesum2"]
    rows = ["| Tier | n | Mode | hit@10 [95% CI] | MRR@10 [95% CI] |", "|---|---|---|---|---|"]
    for tier in TIERS:
        n = t["tiers"][tier]["n"]
        for mode, m in t["tiers"][tier]["modes"].items():
            rows.append(f"| {TIER_NAME[tier]} | {n} | {mode} | {ci(m['hit@10'])} | {ci(m['mrr@10'])} |")
    lat = t["mean_latency_s"]
    rows.append("")
    rows.append("Mean latency per query: " + ", ".join(f"{k} {v:.3f} s" for k, v in lat.items()) + ".")
    return "\n".join(rows)


def per_tier_table(key: str, tags: list[str], label: dict[str, str]) -> str:
    g = RESULTS[key]
    rows = ["| Tier | n | " + " | ".join(f"{label[t]} correct (strict) [95% CI]" for t in tags) + " |",
            "|---|---|" + "---|" * len(tags)]
    for tier in TIERS:
        n = g["per_tier"][tier][tags[0]]["correct_strict"]["n"]
        rows.append(f"| {TIER_NAME[tier]} | {n} | " + " | ".join(ci(g["per_tier"][tier][t]["correct_strict"]) for t in tags) + " |")
    if g.get("paired_diff"):
        rows.append("")
        rows.append("Paired difference on the same questions (second minus first; an interval containing 0 means no difference is claimed):")
        rows.append("")
        for name, d in g["paired_diff"].items():
            m = re.match(r"round_(\d)_correct_strict_(.+?)_minus_(.+)", name)
            if m:
                name = f"{TIER_NAME['round_' + m.group(1)]}: {label[m.group(2)]} minus {label[m.group(3)]}"
            rows.append(f"- {name}: {d['mean']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] (n = {d['n']})")
    return "\n".join(rows)


def counts(d: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in d.items())


def non_answerable(key: str, tags: list[str], label: dict[str, str]) -> str:
    g = RESULTS[key]["non_answerable"]
    rows = ["| Question kind | n | " + " | ".join(f"{label[t]} (judged correct / status)" for t in tags) + " |", "|---|---|" + "---|" * len(tags)]
    for behaviour, per_tag in g.items():
        n = per_tag[tags[0]]["n"]
        cells = [f"{counts(per_tag[t]['correct'])} / {counts(per_tag[t]['status'])}" for t in tags]
        rows.append(f"| {behaviour} | {n} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def main() -> None:
    gen_tags = ["nano_final", "mini_final"]
    closed_tags = ["closed_nano", "closed_mini"]
    agent_tags = ["pilot1_mini", "agent_tool"]
    label = {"nano_final": "gpt-5-nano", "mini_final": "gpt-5-mini", "closed_nano": "nano, no passages", "closed_mini": "mini, no passages",
             "pilot1_mini": "fixed pipeline (mini)", "agent_tool": "tool-calling agent (mini)"}
    text = Path("docs/README_template.md").read_text(encoding="utf-8")
    text = text.replace("{{RETRIEVAL}}", retrieval())
    text = text.replace("{{GENERATION}}", per_tier_table("generation_test_review_claude", gen_tags, label))
    text = text.replace("{{NONANS}}", non_answerable("generation_test_review_claude", gen_tags, label))
    text = text.replace("{{CLOSED}}", per_tier_table("generation_test_review_claude_closedbook", closed_tags, label))
    text = text.replace("{{AGENT}}", per_tier_table("generation_dev_review_claude_agent_vs_fixed", agent_tags, label)
                        + "\n\n" + non_answerable("generation_dev_review_claude_agent_vs_fixed", agent_tags, label))
    Path("README.md").write_text(text, encoding="utf-8")
    print("README.md written,", len(text.splitlines()), "lines")


if __name__ == "__main__":
    main()
