"""Build the retrieval results dashboard from a run in results/results.json.

Static file (no server, no run button):
    uv run python eval/dashboard.py [--key retrieval_test_final] [--out results/dashboard_<key>.html]
With the run button and a live progress bar, use the local server instead:
    uv run python eval/dashboard_server.py

The page shows, per tier (the main view) and then by question type, format and document
(descriptive), the retrieval metrics of vector, hybrid and hybrid + rerank with their bootstrap
intervals and n, coverage@10 as a percentage, a small labelled pooled row, the paired differences
between modes and the latency. Every number comes from results/results.json, written by
eval/retrieval_eval.py; this script only embeds that run, so nothing here is typed or recomputed.

Without --key it shows the final test run if there is one, otherwise the latest reviewed dev pilot
(clearly labelled a pilot on the page).
"""

import json
import sys
from pathlib import Path

RESULTS = Path("results/results.json")
TEMPLATE = Path(__file__).with_name("dashboard_template.html")
PREFERRED = ["retrieval_test_final", "retrieval_dev_reviewed"]
NEEDED = ("tiers", "breakdowns", "pooled", "mean_latency_s")


def available_keys(results: dict) -> list[str]:
    """Runs the page can show: retrieval runs written by the current eval (older ones lack breakdowns)."""
    return sorted(k for k, v in results.items() if k.startswith("retrieval_") and all(n in v for n in NEEDED))


def default_key(results: dict) -> str:
    keys = available_keys(results)
    return next((k for k in PREFERRED if k in keys), keys[0] if keys else "")


def _embed(value) -> str:
    # "</" would end the script element early; the JSON stays valid with an escaped slash.
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_page(run: dict, server_info: dict | None = None) -> str:
    """The self-contained HTML for one run. server_info switches on the run panel (see dashboard_server.py)."""
    html = TEMPLATE.read_text(encoding="utf-8")
    return html.replace("__DATA__", _embed(run)).replace("__SERVER__", _embed(server_info or {"enabled": False}))


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    key = option("--key", "") or default_key(results)
    if not key or key not in results:
        raise SystemExit(f"no usable retrieval run; available: {available_keys(results)}")
    run = results[key]
    for needed in NEEDED:
        if needed not in run:
            raise SystemExit(f"{key!r} has no {needed!r}: it was written by an older eval. Re-run eval/retrieval_eval.py.")
    out = Path(option("--out", f"results/dashboard_{key}.html"))
    out.write_text(render_page(run), encoding="utf-8")
    print(f"wrote {out} from {key} ({'pilot' if run['pilot'] else 'FINAL'}, split {run['split']}, git {run['git_sha']})")


if __name__ == "__main__":
    main()
