import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from dashboard import available_keys, default_key, render_page

RUN = {"tiers": {"round_1": {}}, "breakdowns": {}, "pooled": {}, "mean_latency_s": {}, "pilot": True, "split": "dev"}


def test_only_runs_written_by_the_current_eval_are_listed():
    results = {"retrieval_dev": {"tiers": {}}, "retrieval_dev_reviewed": RUN, "other": RUN}
    assert available_keys(results) == ["retrieval_dev_reviewed"]


def test_final_test_run_is_preferred_over_the_dev_pilot():
    both = {"retrieval_dev_reviewed": RUN, "retrieval_test_final": RUN}
    assert default_key(both) == "retrieval_test_final"
    assert default_key({"retrieval_dev_reviewed": RUN}) == "retrieval_dev_reviewed"
    assert default_key({}) == ""


def _embedded(html: str, element_id: str):
    m = re.search(rf'<script id="{element_id}" type="application/json">(.*?)</script>', html, re.DOTALL)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_page_embeds_the_run_and_defaults_to_the_static_version():
    html = render_page(RUN)
    assert _embedded(html, "data")["split"] == "dev"
    assert _embedded(html, "serverinfo") == {"enabled": False}


def test_server_info_reaches_the_page():
    info = {"enabled": True, "token": "t", "keys": ["a"], "current": "a", "git": "abc"}
    assert _embedded(render_page(RUN, info), "serverinfo")["token"] == "t"


def test_closing_script_tags_in_data_cannot_break_out_of_the_page():
    run = {**RUN, "note": "</script><b>x</b>"}
    html = render_page(run)
    assert "</script><b>" not in html          # escaped, so it cannot end the data element early
    assert _embedded(html, "data")["note"] == "</script><b>x</b>"


def _started_command(monkeypatch, tmp_path, split, tag):
    """Run dashboard_server.start_run with Popen and the status/log paths faked; return the command it would run."""
    import dashboard_server as ds

    seen = {}
    monkeypatch.setattr(ds.config, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(ds, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(ds.subprocess, "Popen", lambda cmd, **kw: seen.setdefault("cmd", cmd))
    ds.start_run(split, tag)
    return seen["cmd"], json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))


def test_the_run_button_starts_the_split_that_was_selected(monkeypatch, tmp_path):
    cmd, status = _started_command(monkeypatch, tmp_path, "test", "rerun")
    assert cmd[cmd.index("--split") + 1] == "test" and cmd[cmd.index("--tag") + 1] == "rerun"
    assert status["split"] == "test" and status["key"] == "retrieval_test_rerun"
    cmd, status = _started_command(monkeypatch, tmp_path, "dev", "reviewed")
    assert cmd[cmd.index("--split") + 1] == "dev" and status["key"] == "retrieval_dev_reviewed"
