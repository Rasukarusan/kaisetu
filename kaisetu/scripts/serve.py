#!/usr/bin/env python3
"""kaisetu server.

Serves the review page with review-data.json embedded and opens a browser.
The page's "Finish" button writes the result JSON. The server does not
exit; the page remains usable for viewing, further comments, and resubmission.
review-data.json is re-read on every request, so rewriting explanations makes
the page follow automatically.
The page's "Refresh" button posts to /api/refresh, which re-takes the diff
through refresh.py: the explanations and the comments stay, the hunk bodies catch
up with the working tree, and the page reloads by itself.
The calling agent watches for the result JSON, reads it, and kills this process
when it is no longer needed.

When review-data.json has a `doc` field, the page reviews that document itself:
it is served at /target (with its sibling assets) and shown in an iframe the
human comments on element by element. Markdown is rendered to HTML on the way
out; an HTML file is served as it is. Rewriting the file bumps the version, so
the page reloads with the fixed document.

Each file header has a "file" link, which opens /file in a new tab: the whole file as it stands in
the working tree. Code is highlighted with the hunk's lines marked; a Markdown or HTML file is
rendered as the document it is, with a "Source" button for the code behind it.

An `explain` field points at the shareable write-up of the same branch. It is served
at /explain and reached from the page's Explain tab, in the same iframe and with the
same element-by-element commenting. It may be named before it exists: the page shows
the tab as pending and lights it up when the file lands.

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

import file_page
import md_render
import refresh as refresh_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdown", ".mkd")

# How the reader likes the page itself (theme, diff layout) — kept per user, not per review.
# Every review is served on a fresh port and localStorage is scoped to the origin, so a browser-side
# store would forget these the moment the next review opened on a different port.
PREFS_PATH = pathlib.Path.home() / ".kaisetu" / "prefs.json"

PLACEHOLDERS = ("__REVIEW_DATA__", "__REVIEW_STATE__", "__REVIEW_VERSION__", "__REVIEW_PREFS__")

# How much of a file the "file" button will render. Past this the reader is looking at a generated
# blob, not the code around the change — it is cut, and the page says so (and offers the raw file).
FILE_VIEW_MAX_LINES = 20000


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

    # The shareable write-up behind the Explain tab. Named in the data before it is written, so
    # this stays None until the agent finishes it — that is what the tab's pending state is for.
    def explain_target():
        ref = load_data().get("explain")
        return resolve_ref(ref, data_path) if ref else None

    def page_data() -> dict:
        # docKind tells the page whether the iframe holds our own render (Markdown) or the file itself
        data = load_data()
        target = doc_target()
        if target:
            data["docKind"] = "markdown" if is_markdown(target) else "html"
        if data.get("explain"):
            ex = explain_target()
            data["explainReady"] = ex is not None
            data["explainVersion"] = explain_version()
            if ex:
                data["explainPath"] = str(ex)   # what the page's "Copy file path" hands over
        return data

    def data_version() -> str:
        # The reviewed document counts too: fixing it makes the page reload with the new render
        parts = [str(data_path.stat().st_mtime_ns)]
        target = doc_target()
        if target:
            parts.append(str(target.stat().st_mtime_ns))
        return "-".join(parts)

    def explain_version() -> str:
        # Kept out of data_version on purpose: writing the write-up must not reload the review page
        # under the reader. The page watches this one on its own and only reloads the iframe.
        target = explain_target()
        return str(target.stat().st_mtime_ns) if target else ""

    def state_text() -> str:
        return state_path.read_text(encoding="utf-8") if state_path.is_file() else "null"

    if args.build is not None:
        out = data_path.with_suffix(".html") if args.build == "-" else pathlib.Path(args.build)
        data = page_data()
        target = doc_target()
        if target:
            # No server to serve /target from, so inline the reviewed document (rendered via srcdoc)
            data["docInline"] = as_html(target).decode("utf-8")
        explain = explain_target()
        if explain:
            data["explainInline"] = as_html(explain).decode("utf-8")
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
            # Routed on the path alone: the page appends a cache-busting query when it re-reads
            # the write-up, and a link may carry one of its own
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                # Render on every request, embedding the latest review data and state (comment drafts)
                body = render(page_data(), state_text(), data_version(), load_prefs()).encode("utf-8")
                self._respond(200, body, "text/html; charset=utf-8")
            elif path == "/api/replies":
                body = replies_path.read_bytes() if replies_path.is_file() else b"{}"
                self._respond(200, body, "application/json; charset=utf-8")
            elif path == "/api/version":
                # The page polls this; on change it re-reads the review data and rebuilds.
                # `explain` moves on its own — the page only reloads the iframe for it.
                body = json.dumps({"version": data_version(), "explain": explain_version()}).encode("utf-8")
                self._respond(200, body, "application/json; charset=utf-8")
            elif path == "/plan":
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
            elif path == "/file":
                # A whole file from the target repo, opened in its own tab from a file header.
                # Code arrives highlighted with `start`/`count` marked; a Markdown or HTML file
                # arrives rendered, with `src=1` for the code behind it. `raw=1` is the plain text.
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                rel = (query.get("path") or [""])[0]
                flag = lambda k: (query.get(k) or ["0"])[0] == "1"
                as_int = lambda k: int((query.get(k) or ["0"])[0]) if (query.get(k) or ["0"])[0].isdigit() else 0
                data = load_data()
                base = pathlib.Path(data.get("repoRoot") or pathlib.Path.cwd()).resolve()
                target = (base / rel).resolve() if rel else None
                if not rel or not target.is_relative_to(base) or not target.is_file():
                    self._respond(404, f"file not found: {rel}".encode("utf-8"),
                                  "text/plain; charset=utf-8")
                    return
                blob = target.read_bytes()
                if b"\0" in blob[:8000]:
                    self._respond(415, b"not a text file", "text/plain; charset=utf-8")
                    return
                text = blob.decode("utf-8", errors="replace")
                if flag("raw"):
                    self._respond(200, text.encode("utf-8"), "text/plain; charset=utf-8")
                    return

                q = urllib.parse.quote(rel, safe="")
                start, count = as_int("start"), as_int("count")
                at = f"&start={start}&count={count}" if start else ""
                theme = load_prefs().get("theme", "")
                # A document is shown as the document. `doc=1` is the render itself, inside the
                # frame; `src=1` is the code behind it, which is where every other file starts.
                renderable = is_markdown(target) or target.suffix.lower() in (".html", ".htm")
                if renderable and flag("doc"):
                    self._respond(200, as_html(target), "text/html; charset=utf-8")
                    return
                if renderable and not flag("src"):
                    page = file_page.render_document(
                        rel, f"/file?doc=1&path={q}", f"/file?src=1&path={q}{at}" + (f"#L{start}" if start else ""),
                        theme, "markdown" if is_markdown(target) else "html")
                    self._respond(200, page.encode("utf-8"), "text/html; charset=utf-8")
                    return

                # A file too long to render whole is cut, and the page says by how much
                lines = text.split("\n")
                truncated = len(lines) if len(lines) > FILE_VIEW_MAX_LINES else 0
                if truncated:
                    text = "\n".join(lines[:FILE_VIEW_MAX_LINES])
                page = file_page.render(rel, text, start, count, theme, truncated,
                                        f"/file?raw=1&path={q}")
                self._respond(200, page.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/explain":
                # The shareable write-up, shown in the page's Explain tab and openable on its own
                ref = load_data().get("explain")
                if not ref:
                    self._respond(404, b"explain not set")
                    return
                target = explain_target()
                if target:
                    self._respond(200, as_html(target), "text/html; charset=utf-8")
                else:
                    self._respond(404, f"explain not written yet: {ref}".encode("utf-8"))
            elif path == "/target":
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
                incoming = self._json_body()
                # A refresh moves comment anchors and bumps _rev. Until the page reloads it still
                # holds the positions from before, and writing those back would undo the move.
                current = 0
                if state_path.is_file():
                    try:
                        saved = json.loads(state_path.read_text(encoding="utf-8"))
                        current = int(saved.get("_rev") or 0)
                    except (OSError, ValueError, TypeError):
                        current = 0
                if int(incoming.get("_rev") or 0) < current:
                    self._respond(200, b'{"stale": true}', "application/json; charset=utf-8")
                    return
                state_path.write_text(
                    json.dumps(incoming, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._respond(200, b'{"ok": true}', "application/json; charset=utf-8")
            elif self.path == "/api/refresh":
                # Re-take the diff in place: the explanations and the comments stay, the code
                # catches up with the working tree. Rewriting the data bumps the version, so the
                # page reloads on its own from here.
                try:
                    summary = refresh_mod.refresh(data_path)
                    body = {"ok": True, **summary}
                    print(f"refreshed: {summary['message']}", flush=True)
                except (refresh_mod.Refused, OSError, ValueError) as e:
                    body = {"ok": False, "error": str(e)}
                    print(f"refresh failed: {e}", flush=True)
                self._respond(200, json.dumps(body, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
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
