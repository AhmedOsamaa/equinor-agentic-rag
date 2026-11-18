from rag.runstate import (
    eta_seconds,
    progress_fields,
    read_status,
    settle_stale,
    write_status,
)


def test_eta_waits_for_a_pace_and_ends_at_the_end():
    assert eta_seconds(1, 100, 5.0) is None            # too early to say
    assert eta_seconds(10, 100, 20.0) == 180.0         # 2 s per step, 90 steps left
    assert eta_seconds(100, 100, 200.0) is None        # finished
    assert eta_seconds(5, 100, 0.0) is None


def test_write_and_read_status_round_trip_and_default_to_idle(tmp_path):
    path = tmp_path / "status.json"
    assert read_status(path) == {"state": "idle"}
    write_status(path, state="running", done=3, total=10)
    got = read_status(path)
    assert got["state"] == "running" and got["done"] == 3 and "updated_utc" in got
    assert not path.with_suffix(".tmp").exists()       # the temp file was replaced, not left behind


def test_unreadable_status_file_counts_as_idle(tmp_path):
    path = tmp_path / "status.json"
    path.write_text("{not json", encoding="utf-8")
    assert read_status(path) == {"state": "idle"}


def test_progress_fields_have_what_the_dashboard_needs():
    import time

    f = progress_fields(2, 10, time.monotonic() - 4.0)
    assert f["done"] == 2 and f["total"] == 10 and f["elapsed_s"] >= 4.0 and f["eta_s"] is None


def test_a_locked_status_file_is_retried_and_then_written(tmp_path, monkeypatch):
    # The failure that stopped the first test run: os.replace refused while a poller had the file open.
    import rag.runstate as rs

    real_replace, calls = rs.os.replace, {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dst)

    monkeypatch.setattr(rs.os, "replace", flaky)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)
    path = tmp_path / "status.json"
    assert write_status(path, state="running", done=7) is True
    assert read_status(path)["done"] == 7 and calls["n"] == 4


def test_status_write_never_raises_even_if_the_file_stays_locked(tmp_path, monkeypatch):
    import rag.runstate as rs

    def always_locked(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(rs.os, "replace", always_locked)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)
    assert write_status(tmp_path / "status.json", state="running") is False   # dropped, not raised


def _stamp(seconds_ago):
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat(timespec="seconds")


def test_a_running_status_nobody_updates_is_reported_as_an_error():
    stale = {"state": "running", "done": 40, "total": 345, "updated_utc": _stamp(300)}
    out = settle_stale(stale, process_alive=False)
    assert out["state"] == "error" and "40 of 345" in out["message"]


def test_a_live_or_recently_updated_run_is_left_alone():
    fresh = {"state": "running", "done": 40, "total": 345, "updated_utc": _stamp(1)}
    assert settle_stale(fresh, process_alive=False) == fresh      # e.g. a run started from a terminal
    old = {"state": "running", "done": 40, "total": 345, "updated_utc": _stamp(300)}
    assert settle_stale(old, process_alive=True) == old           # our own subprocess is still alive
    assert settle_stale({"state": "done"}, process_alive=False) == {"state": "done"}
    assert settle_stale({"state": "idle"}, process_alive=False) == {"state": "idle"}


def test_a_running_status_without_a_timestamp_counts_as_dead():
    assert settle_stale({"state": "running"}, process_alive=False)["state"] == "error"
