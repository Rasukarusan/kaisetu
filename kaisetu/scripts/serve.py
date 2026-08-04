#!/usr/bin/env python3
"""kaisetu server.

Serves the review page with review-data.json embedded and opens a browser.
The page's "Finish review" button writes the result JSON. The server does not
exit; the page remains usable for viewing, further comments, and resubmission.
review-data.json is re-read on every request, so rewriting explanations makes
the page follow automatically.
The calling agent watches for the result JSON, reads it, and kills this process
when it is no longer needed.

Usage:
  serve.py <review-data.json> [--port N] [--result PATH] [--no-open]
  serve.py <review-data.json> --build [output.html]   # emit static HTML only (no server)

Dependencies: Python 3 standard library only.
"""
import argparse
import json
import os
import pathlib
import socket
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent


PLACEHOLDERS = ("__REVIEW_DATA__", "__REVIEW_STATE__", "__REVIEW_VERSION__")


def render(data: dict, state_text: str = "null", version: str = "static") -> str:
    template = (ROOT / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False)
    # Escape sequences that could be parsed as a closing tag inside <script>
    payload = payload.replace("</", "<\\/")
    state_payload = state_text.replace("</", "<\\/")
    missing = [p for p in PLACEHOLDERS if p not in template]
    if missing:
        sys.exit(f"template.html is missing placeholders: {' / '.join(missing)}")
    return (template.replace("__REVIEW_DATA__", payload)
                    .replace("__REVIEW_STATE__", state_payload)
                    .replace("__REVIEW_VERSION__", version))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    ap = argparse.ArgumentParser(description="kaisetu server")
    ap.add_argument("data", help="path to review-data.json")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--result", help="result JSON path (default: <data>.result.json)")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    ap.add_argument("--build", nargs="?", const="-", metavar="OUT",
                    help="emit static HTML and exit (default OUT: <data>.html)")
    args = ap.parse_args()

    data_path = pathlib.Path(args.data).resolve()
    state_path = data_path.with_suffix(".state.json")    # autosaved work-in-progress; the page restores from it

    # Review data is re-read every time; when explanations are rewritten the page detects it and rebuilds
    def load_data() -> dict:
        return json.loads(data_path.read_text(encoding="utf-8"))

    def data_version() -> str:
        return str(data_path.stat().st_mtime_ns)

    def state_text() -> str:
        return state_path.read_text(encoding="utf-8") if state_path.is_file() else "null"

    if args.build is not None:
        out = data_path.with_suffix(".html") if args.build == "-" else pathlib.Path(args.build)
        out.write_text(render(load_data(), state_text()), encoding="utf-8")
        print(out)
        return

    result_path = pathlib.Path(args.result) if args.result else data_path.with_suffix(".result.json")
    replies_path = data_path.with_suffix(".replies.json")  # AI answers to comments (the page polls this)
    port = args.port or free_port()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):  # no access log
            pass

        def _json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length) or b"{}")

        def _respond(self, code=200, body=b"ok", ctype="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                # Render on every request, embedding the latest review data and state (comment drafts)
                body = render(load_data(), state_text(), data_version()).encode("utf-8")
                self._respond(200, body, "text/html; charset=utf-8")
            elif self.path == "/api/replies":
                body = replies_path.read_bytes() if replies_path.is_file() else b"{}"
                self._respond(200, body, "application/json; charset=utf-8")
            elif self.path == "/api/version":
                # The page polls this; on change it re-reads the review data and rebuilds
                body = json.dumps({"version": data_version()}).encode("utf-8")
                self._respond(200, body, "application/json; charset=utf-8")
            elif self.path == "/plan":
                plan = load_data().get("plan")
                if not plan:
                    self._respond(404, b"plan not set")
                    return
                # Resolve as absolute path / relative to server CWD / relative to the data file, in that order
                for base in (pathlib.Path(plan), pathlib.Path.cwd() / plan, data_path.parent / plan):
                    if base.is_file():
                        self._respond(200, base.read_text(encoding="utf-8").encode("utf-8"))
                        return
                self._respond(404, f"plan not found: {plan}".encode("utf-8"))
            else:
                self._respond(404, b"not found")

        def do_POST(self):
            if self.path == "/api/state":
                state_path.write_text(
                    json.dumps(self._json_body(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._respond()
            elif self.path == "/api/finish":
                result_path.write_text(
                    json.dumps(self._json_body(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._respond()
                print(f"finished: {result_path}", flush=True)
            else:
                self._respond(404, b"not found")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"kaisetu: {url}", flush=True)
    print(f"result: {result_path}", flush=True)
    print(f"pid: {os.getpid()}", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
