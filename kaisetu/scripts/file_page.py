#!/usr/bin/env python3
"""The page behind a file header's "View" link: one whole file, on its own.

A hunk is a few lines cut out of a file, and the question it most often raises is what surrounds
them. This is the file as it stands in the working tree, as a standalone page that opens in its own
tab and can be kept open beside the review.

A file is shown as what it is. Code arrives as code — line numbers, highlighted, with the hunk's
lines marked and scrolled to. A document (Markdown or HTML) arrives as the document, rendered, the
way its reader would see it; its "Source" button is what then shows the code behind it.

Highlighting is done here rather than in the browser: no dependency, no script to load, and the
page is complete the moment it arrives. It is deliberately shallow — comments, strings, numbers and
keywords are what tell code apart at a glance; anything finer would be a syntax engine, and the
reader already has one of those in their editor.

Dependencies: Python 3 standard library only.
"""
import html
import pathlib

# ---------- languages ----------
# Keywords are the words that carry the shape of the code, not every name the language defines.

_C_LIKE = """break case catch class const continue default delete do else enum export extends
finally for function if implements import in instanceof interface let new package private protected
public return static super switch this throw throws try typeof var void while yield async await
of as from readonly declare namespace type abstract"""

_LANGS = {
    "js": {
        "label": "javascript", "line": ["//"], "block": ("/*", "*/"), "strings": ['"', "'", "`"],
        "kw": set(_C_LIKE.split()) | {"true", "false", "null", "undefined", "NaN", "satisfies", "keyof", "infer"},
    },
    "py": {
        "label": "python", "line": ["#"], "block": None,
        "strings": ['"""', "'''", '"', "'"], "multiline": ['"""', "'''"],
        "kw": set("""and as assert async await break class continue def del elif else except finally
            for from global if import in is lambda nonlocal not or pass raise return try while with
            yield True False None self cls match case""".split()),
    },
    "go": {
        "label": "go", "line": ["//"], "block": ("/*", "*/"), "strings": ['"', "`", "'"],
        "kw": set("""break case chan const continue default defer else fallthrough for func go goto
            if import interface map package range return select struct switch type var nil true
            false make new len cap append error string int int64 float64 bool byte rune""".split()),
    },
    "rb": {
        "label": "ruby", "line": ["#"], "block": None, "strings": ['"', "'"],
        "kw": set("""alias and begin break case class def defined do else elsif end ensure false for
            if in module next nil not or redo rescue retry return self super then true undef unless
            until when while yield require require_relative attr_accessor attr_reader""".split()),
    },
    "rs": {
        "label": "rust", "line": ["//"], "block": ("/*", "*/"), "strings": ['"'],
        "kw": set("""as async await break const continue crate dyn else enum extern false fn for if
            impl in let loop match mod move mut pub ref return self Self static struct super trait
            true type unsafe use where while Some None Ok Err""".split()),
    },
    "java": {
        "label": "java", "line": ["//"], "block": ("/*", "*/"), "strings": ['"', "'"],
        "kw": set(_C_LIKE.split()) | set("""abstract boolean byte char double final float int long
            native short synchronized transient volatile true false null record sealed""".split()),
    },
    "php": {
        "label": "php", "line": ["//", "#"], "block": ("/*", "*/"), "strings": ['"', "'"],
        "kw": set(_C_LIKE.split()) | {"echo", "elseif", "endif", "foreach", "global", "isset", "unset",
                                      "use", "trait", "fn", "match", "true", "false", "null"},
    },
    "css": {
        "label": "css", "line": [], "block": ("/*", "*/"), "strings": ['"', "'"],
        "kw": set("""important media supports keyframes import font-face charset use mixin include
            extend if else each function return""".split()),
    },
    "sh": {
        "label": "shell", "line": ["#"], "block": None, "strings": ['"', "'"],
        "kw": set("""if then else elif fi for while until do done case esac function return local
            export source echo set unset trap exit shift read declare readonly""".split()),
    },
    "sql": {
        "label": "sql", "line": ["--"], "block": ("/*", "*/"), "strings": ["'", '"'],
        "kw": set("""select from where join left right inner outer on group by order having limit
            offset insert into values update set delete create table alter drop index primary key
            foreign references not null unique default and or as distinct union all with returning
            begin commit rollback""".split()),
    },
    "yaml": {"label": "yaml", "line": ["#"], "block": None, "strings": ['"', "'"],
             "kw": {"true", "false", "null", "yes", "no", "on", "off"}},
    "json": {"label": "json", "line": [], "block": None, "strings": ['"'],
             "kw": {"true", "false", "null"}},
    "html": {"label": "html", "line": [], "block": ("<!--", "-->"), "strings": ['"', "'"], "kw": set()},
    # Prose is not code: a number in a sentence is a number, not a literal worth colouring
    "md": {"label": "markdown", "line": [], "block": None, "strings": [], "kw": set(), "numbers": False},
    "text": {"label": "", "line": [], "block": None, "strings": [], "kw": set(), "numbers": False},
}

_BY_EXT = {
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js", ".ts": "js", ".tsx": "js", ".vue": "js",
    ".py": "py", ".pyi": "py",
    ".go": "go",
    ".rb": "rb", ".rake": "rb",
    ".rs": "rs",
    ".java": "java", ".kt": "java", ".kts": "java", ".scala": "java", ".swift": "java",
    ".c": "java", ".h": "java", ".cc": "java", ".cpp": "java", ".hpp": "java", ".cs": "java",
    ".php": "php",
    ".css": "css", ".scss": "css", ".sass": "css", ".less": "css",
    ".sh": "sh", ".bash": "sh", ".zsh": "sh", ".fish": "sh",
    ".sql": "sql",
    ".yml": "yaml", ".yaml": "yaml", ".toml": "yaml", ".ini": "yaml", ".cfg": "yaml",
    ".json": "json", ".jsonc": "json",
    ".html": "html", ".htm": "html", ".xml": "html", ".svg": "html", ".vue.html": "html",
    ".md": "md", ".markdown": "md",
}
_BY_NAME = {
    "Dockerfile": "sh", "Makefile": "sh", ".env": "sh", ".gitignore": "text", "Gemfile": "rb",
    "Rakefile": "rb", "Brewfile": "rb",
}


def language_for(path: str) -> dict:
    name = pathlib.PurePosixPath(path).name
    key = _BY_NAME.get(name) or _BY_EXT.get(pathlib.PurePosixPath(name.lower()).suffix) or "text"
    return _LANGS[key]


# ---------- the scanner ----------
# One pass over the file, emitting (kind, text). Kinds: "" plain, "c" comment, "s" string,
# "k" keyword, "n" number. It runs over the whole text rather than line by line, so a block comment
# or a triple-quoted string stays one thing across the lines it spans.

def tokenize(text: str, cfg: dict):
    out, buf = [], []
    line_comments = sorted(cfg.get("line") or [], key=len, reverse=True)
    block = cfg.get("block")
    strings = sorted(cfg.get("strings") or [], key=len, reverse=True)
    multiline = set(cfg.get("multiline") or [])
    kw = cfg.get("kw") or set()
    numbers = cfg.get("numbers", True)

    def flush():
        if buf:
            out.append(("", "".join(buf)))
            buf.clear()

    i, n = 0, len(text)
    while i < n:
        ch = text[i]

        lc = next((c for c in line_comments if text.startswith(c, i)), None)
        if lc:
            end = text.find("\n", i)
            end = n if end < 0 else end
            flush()
            out.append(("c", text[i:end]))
            i = end
            continue

        if block and text.startswith(block[0], i):
            end = text.find(block[1], i + len(block[0]))
            end = n if end < 0 else end + len(block[1])
            flush()
            out.append(("c", text[i:end]))
            i = end
            continue

        quote = next((q for q in strings if text.startswith(q, i)), None)
        if quote:
            j, closed = i + len(quote), False
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text.startswith(quote, j):
                    j += len(quote)
                    closed = True
                    break
                if text[j] == "\n" and quote not in multiline:
                    break
                j += 1
            # A quote that never closes on its line was not one: an apostrophe in a comment or in
            # prose. It stays plain, and scanning carries on from just after it.
            if not closed:
                buf.append(quote)
                i += len(quote)
                continue
            flush()
            out.append(("s", text[i:j]))
            i = j
            continue

        prev = text[i - 1] if i else ""
        if numbers and ch.isdigit() and not (prev.isalnum() or prev == "_"):
            j = i
            while j < n and (text[j].isalnum() or text[j] in "._"):
                j += 1
            flush()
            out.append(("n", text[i:j]))
            i = j
            continue

        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            word = text[i:j]
            if word in kw:
                flush()
                out.append(("k", word))
            else:
                buf.append(word)
            i = j
            continue

        buf.append(ch)
        i += 1
    flush()
    return out


def _rows(tokens):
    """Tokens regrouped per line, so each line can carry its own number."""
    lines = [[]]
    for kind, txt in tokens:
        parts = txt.split("\n")
        for k, part in enumerate(parts):
            if k:
                lines.append([])
            if part:
                lines[-1].append((kind, part))
    return lines


def _line_html(spans):
    return "".join(
        f'<span class="t{kind}">{html.escape(txt)}</span>' if kind else html.escape(txt)
        for kind, txt in spans
    ) or "&nbsp;"


CSS = """
:root {
  color-scheme: light;
  --bg: #f4f5f7; --card: #ffffff; --surface-2: #fafbfc; --surface-3: #f2f4f7;
  --border: #e4e7ee; --border-strong: #d4d9e3;
  --ink: #22252b; --ink-soft: #5b6270; --ink-faint: #8a919f;
  --here-bg: #fff8e2; --here-num: #b58a00;
  --t-c: #7a8394; --t-s: #2c7a4b; --t-k: #9a3ea1; --t-n: #b3541e;
  --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Hiragino Sans", sans-serif;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #14171c; --card: #191d23; --surface-2: #1d2229; --surface-3: #222831;
  --border: #2b323b; --border-strong: #3a424e;
  --ink: #dfe3ea; --ink-soft: #a5adba; --ink-faint: #79828f;
  --here-bg: #2c2a1c; --here-num: #d9b45a;
  --t-c: #7e8796; --t-s: #7fc98f; --t-k: #d08ad6; --t-n: #e0a06a;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans); }
header {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 11px 18px; background: var(--card); border-bottom: 1px solid var(--border);
  font-family: var(--mono); font-size: 12.5px;
}
header .path { font-weight: 700; word-break: break-all; }
header .meta { color: var(--ink-faint); white-space: nowrap; }
header .actions { margin-left: auto; display: flex; gap: 8px; flex: none; }
header button, header a {
  font-family: var(--mono); font-size: 11.5px; line-height: 1; text-decoration: none;
  padding: 5px 10px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--border-strong); background: var(--card); color: var(--ink-soft);
}
header button:hover, header a:hover { color: #2f6bb0; border-color: #2f6bb0; }
main { padding: 0 0 40vh; }
table { border-collapse: collapse; width: 100%; font-family: var(--mono); font-size: 12.5px; line-height: 1.62; }
td { padding: 0 12px; vertical-align: top; white-space: pre; }
td.n {
  width: 1%; text-align: right; user-select: none; color: var(--ink-faint);
  background: var(--surface-3); border-right: 1px solid var(--border); position: sticky; left: 0;
}
td.c { width: 100%; }
tr:target td.n, tr.here td.n { background: var(--here-bg); color: var(--here-num); font-weight: 700; }
tr.here td.c { background: var(--here-bg); }
tr { scroll-margin-top: 30vh; }
.tc { color: var(--t-c); font-style: italic; }
.ts { color: var(--t-s); }
.tk { color: var(--t-k); }
.tn { color: var(--t-n); }
.note { padding: 12px 18px; color: var(--ink-soft); font-size: 12.5px; }
/* A rendered document sits in a frame below the same header, so the file's own styles are its own */
iframe { display: block; width: 100%; height: calc(100vh - 43px); border: 0; background: #fff; }
""" 


def _page(path: str, theme: str, meta: str, actions: str, body: str, note: str = "") -> str:
    """One page of chrome — the path, what it is, and the ways out of it — around `body`."""
    attr = f' data-theme="{html.escape(theme)}"' if theme in ("light", "dark") else ""
    esc_path = html.escape(path)
    return f"""<!DOCTYPE html>
<html lang="en"{attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc_path} — kaisetu</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <span class="path">{esc_path}</span>
  <span class="meta">{html.escape(meta)}</span>
  <span class="actions">
    <button id="copy" data-path="{esc_path}">Copy path</button>
    {actions}
  </span>
</header>
{body}
{note}
<script>
document.getElementById("copy").addEventListener("click", async e => {{
  const btn = e.currentTarget;
  try {{ await navigator.clipboard.writeText(btn.dataset.path); }} catch (err) {{ return; }}
  const was = btn.textContent;
  btn.textContent = "Copied";
  setTimeout(() => {{ btn.textContent = was; }}, 1200);
}});
</script>
</body>
</html>
"""


def render_document(path: str, doc_href: str, source_href: str, theme: str = "", kind: str = "") -> str:
    """A Markdown or HTML file shown as the document it is, with the code one click away."""
    actions = f'<a href="{html.escape(source_href, quote=True)}">Source</a>'
    body = f'<iframe src="{html.escape(doc_href, quote=True)}" title="{html.escape(path)}"></iframe>'
    return _page(path, theme, kind, actions, body)


def render(path: str, text: str, start: int = 0, count: int = 0,
           theme: str = "", truncated: int = 0, raw_href: str = "") -> str:
    """The file as code: line numbers, highlighted, the hunk's lines marked and scrolled to."""
    cfg = language_for(path)
    rows = _rows(tokenize(text, cfg))
    first, last = (start, start + max(count, 1) - 1) if start else (0, -1)
    body = []
    for i, spans in enumerate(rows, 1):
        here = ' class="here"' if first <= i <= last else ""
        body.append(f'<tr id="L{i}"{here}><td class="n">{i}</td><td class="c">{_line_html(spans)}</td></tr>')
    meta = f"{len(rows)} lines" + (f" of {truncated}" if truncated else "")
    if cfg["label"]:
        meta += f" · {cfg['label']}"
    note = (f'<div class="note">Showing the first {len(rows)} of {truncated} lines. '
            f'"Raw" has the whole file.</div>') if truncated else ""
    actions = f'<a href="{html.escape(raw_href, quote=True)}">Raw</a>' if raw_href else ""
    table = f'<main><table><tbody>{chr(10)}{chr(10).join(body)}{chr(10)}</tbody></table></main>'
    return _page(path, theme, meta, actions, table, note)
