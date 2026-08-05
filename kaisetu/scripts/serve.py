#!/usr/bin/env python3
"""kaisetu server.

Serves the review page with review-data.json embedded and opens a browser.
The page's "Finish review" button writes the result JSON. The server does not
exit; the page remains usable for viewing, further comments, and resubmission.
review-data.json is re-read on every request, so rewriting explanations makes
the page follow automatically.
The calling agent watches for the result JSON, reads it, and kills this process
when it is no longer needed.

When review-data.json has an `html` field, the page reviews that HTML file
itself: it is served at /target (with its sibling assets) and shown in an
iframe the human comments on element by element. Rewriting the HTML bumps the
version, so the page reloads with the fixed page.

Usage:
  serve.py <review-data.json> [--port N] [--result PATH] [--no-open]
  serve.py <review-data.json> --build [output.html]   # emit static HTML only (no server)

Dependencies: Python 3 standard library only.
"""
import argparse
import json
import mimetypes
import os
import pathlib
import socket
import sys
import urllib.parse
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


def resolve_ref(ref: str, data_path: pathlib.Path):
    """Resolve a path written in review-data.json (plan / html).

    Tried as an absolute path, relative to the server CWD, then relative to the data file.
    """
    for base in (pathlib.Path(ref), pathlib.Path.cwd() / ref, data_path.parent / ref):
        if base.is_file():
            return base
    return None


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

    # HTML review mode: the reviewed page itself (served at /target), or None in diff mode
    def html_target():
        ref = load_data().get("html")
        return resolve_ref(ref, data_path) if ref else None

    def data_version() -> str:
        # The reviewed HTML counts too: fixing it makes the page reload with the new render
        parts = [str(data_path.stat().st_mtime_ns)]
        target = html_target()
        if target:
            parts.append(str(target.stat().st_mtime_ns))
        return "-".join(parts)

    def state_text() -> str:
        return state_path.read_text(encoding="utf-8") if state_path.is_file() else "null"

    if args.build is not None:
        out = data_path.with_suffix(".html") if args.build == "-" else pathlib.Path(args.build)
        data = load_data()
        target = html_target()
        if target:
            # No server to serve /target from, so inline the reviewed page (rendered via srcdoc)
            data["htmlInline"] = target.read_text(encoding="utf-8")
        out.write_text(render(data, state_text()), encoding="utf-8")
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

        def _serve_asset(self) -> bool:
            """Serve a file sitting next to the reviewed HTML (its relative css / js / images)."""
            target = html_target()
            if not target:
                return False
            rel = urllib.parse.unquote(self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/"))
            if not rel:
                return False
            base = target.parent.resolve()
            path = (base / rel).resolve()
            if not path.is_file() or not path.is_relative_to(base):  # no escaping the page's directory
                return False
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in (
                "application/javascript", "application/json", "image/svg+xml"
            ):
                ctype += "; charset=utf-8"
            self._respond(200, path.read_bytes(), ctype)
            return True

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
                found = resolve_ref(plan, data_path)
                if found:
                    self._respond(200, found.read_text(encoding="utf-8").encode("utf-8"))
                else:
                    self._respond(404, f"plan not found: {plan}".encode("utf-8"))
            elif self.path == "/target":
                # HTML review mode: the reviewed page, shown in the page's iframe
                ref = load_data().get("html")
                if not ref:
                    self._respond(404, b"html not set")
                    return
                target = html_target()
                if target:
                    self._respond(200, target.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._respond(404, f"html not found: {ref}".encode("utf-8"))
            elif not self._serve_asset():
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
