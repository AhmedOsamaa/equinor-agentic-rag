"""Progress of an eval run.

The eval script writes a small status file after every question, so the dashboard can show a
progress bar for a run it started (or one started from a terminal).
"""

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from rag import config

STATUS_PATH = config.RESULTS_DIR / "run_status.json"


def eta_seconds(done: int, total: int, elapsed: float) -> float | None:
    """Seconds left at the pace so far; None until a few steps have set a pace."""
    if done < 3 or done >= total or elapsed <= 0:
        return None
    return elapsed / done * (total - done)


STATUS_RETRIES = 40   # about one second of trying before a status update is dropped
STATUS_WAIT = 0.025


def write_status(path: Path, **fields) -> bool:
    """Replace the status file atomically, so a reader never sees a half-written file.

    Best effort, and it never raises: on Windows `os.replace` fails with PermissionError while another
    process (the dashboard page polling every 0.8 s) has the file open. That failure once killed the
    first test run 8 seconds in, and the error handler's own status write failed the same way, so no
    error was recorded. Progress reporting must never be able to stop an eval run: retry briefly, then
    give up on this one update. Returns whether the update was written.
    """
    record = {**fields, "updated_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    tmp = path.with_suffix(".tmp")
    for _ in range(STATUS_RETRIES):
        try:
            tmp.write_text(json.dumps(record), encoding="utf-8")
            os.replace(tmp, path)
            return True
        except OSError:
            time.sleep(STATUS_WAIT)
    return False


def read_status(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"state": "idle"}


STALE_AFTER_S = 20  # the eval updates the status after every question (about 0.2 s), so 20 s of silence means it died


def status_age_seconds(status: dict, now: datetime | None = None) -> float | None:
    """Seconds since the status file was last written, or None if it carries no timestamp."""
    stamp = status.get("updated_utc")
    if not stamp:
        return None
    return ((now or datetime.now(UTC)) - datetime.fromisoformat(stamp)).total_seconds()


def settle_stale(status: dict, process_alive: bool, now: datetime | None = None) -> dict:
    """A 'running' status nobody is updating is a run that died: report it as an error, not as running.

    Without this, a run that crashed leaves "running" in the file and the dashboard would show a live
    bar forever and keep the Run button disabled. A run that is alive, or one started from a terminal
    that is still updating the file, is left alone.
    """
    if status.get("state") != "running" or process_alive:
        return status
    age = status_age_seconds(status, now)
    if age is None or age > STALE_AFTER_S:
        return {**status, "state": "error",
                "message": f"the last run stopped at {status.get('done', '?')} of {status.get('total', '?')} steps "
                           "and left no result; see the server terminal"}
    return status


def progress_fields(done: int, total: int, started: float) -> dict:
    elapsed = time.monotonic() - started
    return {"done": done, "total": total, "elapsed_s": round(elapsed, 1), "eta_s": eta_seconds(done, total, elapsed)}


def git_sha() -> str:
    """The commit a run was produced at, with "+dirty" if tracked files have uncommitted changes."""
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, cwd=config.ROOT).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], text=True,
                                        cwd=config.ROOT).strip()
        return sha + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
