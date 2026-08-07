#!/usr/bin/env python3
"""kaisetu server.

Serves the review page with review-data.json embedded and opens a browser.
The page's "Finish review" button writes the result JSON. The server does not
exit; the page remains usable for viewing, further comments, and resubmission.
review-data.json is re-read on every request, so rewriting explanations makes
the page follow automatically.
The calling agent watches for the result JSON, reads it, and kills this process
when it is no longer needed.

When review-data.json has a `doc` field, the page reviews that document itself:
it is served at /target (with its sibling assets) and shown in an iframe the
human comments on element by element. Markdown is rendered to HTML on the way
out; an HTML file is served as it is. Rewriting the file bumps the version, so
the page reloads with the fixed document.

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

import md_render

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdown", ".mkd")

# How the reader likes the page itself (theme, diff layout) — kept per user, not per review.
# Every review is served on a fresh port and localStorage is scoped to the origin, so a browser-side
# store would forget these the moment the next review opened on a different port.
PREFS_PATH = pathlib.Path.home() / ".kaisetu" / "prefs.json"

PLACEHOLDERS = ("__REVIEW_DATA__", "__REVIEW_STATE__", "__REVIEW_VERSION__", "__REVIEW_PREFS__")


def load_prefs() -> dict:
    try:
        prefs = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        return prefs if isinstance(prefs, dict) else {}
    except (OSError, ValueError):
        return {}


def save_prefs(update: dict) -> None:
    prefs = load_prefs()
    prefs.update(update)
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")


def render(data: dict, state_text: str = "null", version: str = "static", prefs: dict = None) -> str:
    template = (ROOT / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False)
    # Escape sequences that could be parsed as a closing tag inside <script>
    payload = payload.replace("</", "<\\/")
    state_payload = state_text.replace("</", "<\\/")
    prefs_payload = json.dumps(prefs or {}, ensure_ascii=False).replace("</", "<\\/")
    missing = [p for p in PLACEHOLDERS if p not in template]
    if missing:
        sys.exit(f"template.html is missing placeholders: {' / '.join(missing)}")
    return (template.replace("__REVIEW_DATA__", payload)
                    .replace("__REVIEW_STATE__", state_payload)
                    .replace("__REVIEW_VERSION__", version)
                    .replace("__REVIEW_PREFS__", prefs_payload))


def resolve_ref(ref: str, data_path: pathlib.Path):
    """Resolve a path written in review-data.json (plan / doc).

    Tried as an absolute path, relative to the server CWD, then relative to the data file.
    """
    for base in (pathlib.Path(ref), pathlib.Path.cwd() / ref, data_path.parent / ref):
        if base.is_file():
            return base
    return None


def is_markdown(path: pathlib.Path) -> bool:
    return path.suffix.lower() in MARKDOWN_SUFFIXES


def as_html(path: pathlib.Path) -> bytes:
    """The reviewed document as HTML — Markdown rendered, HTML passed through byte for byte."""
    if not is_markdown(path):
        return path.read_bytes()
    return md_render.render_document(path.read_text(encoding="utf-8"), path.name).encode("utf-8")


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

    # Document review mode: the reviewed file itself (served at /target), or None in diff mode
    def doc_target():
        ref = load_data().get("doc")
        return resolve_ref(ref, data_path) if ref else None

    def page_data() -> dict:
        # docKind tells the page whether the iframe holds our own render (Markdown) or the file itself
        data = load_data()
        target = doc_target()
        if target:
            data["docKind"] = "markdown" if is_markdown(target) else "html"
        return data

    def data_version() -> str:
        # The reviewed document counts too: fixing it makes the page reload with the new render
        parts = [str(data_path.stat().st_mtime_ns)]
        target = doc_target()
        if target:
            parts.append(str(target.stat().st_mtime_ns))
        return "-".join(parts)

    def state_text() -> str:
        return state_path.read_text(encoding="utf-8") if state_path.is_file() else "null"

    if args.build is not None:
        out = data_path.with_suffix(".html") if args.build == "-" else pathlib.Path(args.build)
        data = page_data()
        target = doc_target()
        if target:
            # No server to serve /target from, so inline the reviewed document (rendered via srcdoc)
            data["docInline"] = as_html(target).decode("utf-8")
        out.write_text(render(data, state_text(), prefs=load_prefs()), encoding="utf-8")
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
            """Serve a file sitting next to the reviewed document (its relative css / js / images).

            A neighbouring Markdown file is rendered as well, so links between docs work.
            """
            target = doc_target()
            if not target:
                return False
            rel = urllib.parse.unquote(self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/"))
            if not rel:
                return False
            base = target.parent.resolve()
            path = (base / rel).resolve()
            if not path.is_file() or not path.is_relative_to(base):  # no escaping the doc's directory
                return False
            if is_markdown(path):
                self._respond(200, as_html(path), "text/html; charset=utf-8")
                return True
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
                body = render(page_data(), state_text(), data_version(), load_prefs()).encode("utf-8")
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
                if found and is_markdown(found):
                    # It opens in a new tab, so a Markdown plan is rendered rather than dumped raw
                    self._respond(200, as_html(found), "text/html; charset=utf-8")
                elif found:
                    self._respond(200, found.read_text(encoding="utf-8").encode("utf-8"))
                else:
                    self._respond(404, f"plan not found: {plan}".encode("utf-8"))
            elif self.path == "/target":
                # Document review mode: the reviewed document, shown in the page's iframe
                ref = load_data().get("doc")
                if not ref:
                    self._respond(404, b"doc not set")
                    return
                target = doc_target()
                if target:
                    self._respond(200, as_html(target), "text/html; charset=utf-8")
                else:
                    self._respond(404, f"doc not found: {ref}".encode("utf-8"))
            elif not self._serve_asset():
                self._respond(404, b"not found")

        def do_POST(self):
            if self.path == "/api/prefs":
                # Theme and diff layout, remembered for the next review as well as this one
                save_prefs(self._json_body())
                self._respond()
            elif self.path == "/api/state":
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
