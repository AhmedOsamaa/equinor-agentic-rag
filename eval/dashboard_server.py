"""Local dashboard server: the results page with a run button and a live progress bar.

Run: uv run python eval/dashboard_server.py [--port 8765] [--open]

Opens nothing on the network: it binds 127.0.0.1 only, checks the Host header, and every POST must
carry a token that only this server's own page knows. It uses Python's standard library, so no web
framework is added.

The run button starts eval/retrieval_eval.py as a subprocess (the same command you would type) and
the page follows its status file; the same run draws its tqdm bar in this terminal
(stdout goes to results/run.log). Two buttons, two rules:
  - the page picks the split (dev or test); the tag picks the results key (retrieval_<split>_<tag>).
    There is no guard: a run with an existing split and tag overwrites that key.
"""

import json
import re
import secrets
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dashboard import available_keys, default_key, render_page

from rag import config
from rag.runstate import STATUS_PATH, git_sha, read_status, settle_stale, write_status

TOKEN = secrets.token_urlsafe(16)
TAG = re.compile(r"^[a-z0-9_]{1,20}$")
_lock = threading.Lock()
_proc: subprocess.Popen | None = None


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def is_running() -> bool:
    return _proc is not None and _proc.poll() is None


def server_info(current: str, keys: list[str]) -> dict:
    return {"enabled": True, "token": TOKEN, "keys": keys, "current": current, "git": git_sha()}


def start_run(split: str, tag: str) -> None:
    global _proc
    config.RESULTS_DIR.mkdir(exist_ok=True)
    cmd = [sys.executable, "eval/retrieval_eval.py", "--split", split, "--tag", tag]
    key = f"retrieval_{split}_{tag}"
    write_status(STATUS_PATH, state="running", split=split, tag=tag, key=key, mode="starting", done=0, total=0,
                 elapsed_s=0, eta_s=None)
    log = open(config.RESULTS_DIR / "run.log", "wb")  # noqa: SIM115 - the child owns it until it exits
    # stdout goes to the log; stderr (where tqdm draws its bar, and any traceback) stays in this terminal.
    _proc = subprocess.Popen(cmd, cwd=config.ROOT, stdout=log)


class Handler(BaseHTTPRequestHandler):
    server_version = "dashboard"

    def log_message(self, fmt, *args):  # quiet: one line per request is noise in the terminal
        pass

    def _send(self, code: int, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8") if ctype == "application/json" else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self) -> bool:
        # A page on another site must not be able to talk to this server (DNS rebinding): only our own host names.
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        url = urlparse(self.path)
        if url.path == "/api/status":
            # a status that says "running" while no process updates it is a run that died (see settle_stale)
            return self._send(200, settle_stale(read_status(STATUS_PATH), is_running()))
        if url.path != "/":
            return self._send(404, {"error": "not found"})
        results_path = config.RESULTS_DIR / "results.json"
        results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
        keys = available_keys(results)
        key = parse_qs(url.query).get("key", [""])[0] or default_key(results)
        if key not in keys:
            return self._send(404, f"No usable run {key!r}. Available: {keys}. Use the run button after loading a page with a run, or run eval/retrieval_eval.py.", "text/plain")
        return self._send(200, render_page(results[key], server_info(key, keys)), "text/html")

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Token") != TOKEN:
            return self._send(403, {"error": "forbidden"})
        if urlparse(self.path).path != "/api/run":
            return self._send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "bad request body"})
        split = body.get("split")
        if split not in ("dev", "test"):
            return self._send(400, {"error": "split must be dev or test"})
        tag = str(body.get("tag", "reviewed"))
        if not TAG.match(tag):
            return self._send(400, {"error": "tag: 1 to 20 characters of a-z, 0-9 and _"})
        with _lock:
            if is_running():
                return self._send(409, {"error": "a run is already in progress"})
            start_run(split, tag)
        return self._send(202, {"started": True, "split": split, "tag": tag})


def main() -> None:
    port = int(option("--port", "8765"))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"dashboard at {url}  (Ctrl+C to stop; the run's tqdm output goes to results/run.log)")
    if "--open" in sys.argv:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
