"""A simple dashboard: one Run Evaluation button, three metric cards, one bar chart.

Run: uv run python eval/simple_dashboard.py [--port 8766] [--open]

It reuses the run machinery of dashboard_server.py (the same POST /api/run, the same status file,
the same loopback-only and token checks), and only changes the page. The page opens on the most
recently written run, not on a preferred one. The older, fuller page is still eval/dashboard_server.py.
"""

import json
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import dashboard_server as ds
from dashboard import NEEDED, available_keys

from rag import config

PAGE = Path(__file__).with_name("simple_dashboard.html")


class Handler(ds.Handler):
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        path = urlparse(self.path).path
        if path == "/":
            html = PAGE.read_text(encoding="utf-8").replace("__SERVER__", json.dumps({"token": ds.TOKEN}))
            return self._send(200, html, "text/html")
        if path == "/api/results":
            results_path = config.RESULTS_DIR / "results.json"
            results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
            usable = {k: results[k] for k in available_keys(results) if all(n in results[k] for n in NEEDED)}
            return self._send(200, usable)
        return super().do_GET()  # /api/status and 404


def main() -> None:
    port = int(ds.option("--port", "8766"))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"simple dashboard at {url}  (Ctrl+C to stop; the run's tqdm output goes to results/run.log)")
    if "--open" in sys.argv:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
