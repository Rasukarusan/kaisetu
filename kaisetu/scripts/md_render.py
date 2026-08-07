#!/usr/bin/env python3
"""Markdown → HTML for document review mode.

Dependency-free (standard library only) and deterministic: the same source always
produces the same elements in the same order, so the CSS selectors that comment
anchors are built from survive edits made elsewhere in the file.

Covers the subset that actually shows up in project docs: headings (with stable
ids), nested and task lists, fenced and indented code, GFM tables, blockquotes,
images, links, inline HTML, and YAML front matter.

Usage:
  from markdown import render_document
  html = render_document(path.read_text(), title=path.name)
"""
import html as _html
import re

__all__ = ["render_document", "render_body"]


# ---------- inline ----------

_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(\s*(<[^>]*>|[^\s)]*)(?:\s+\"([^\"]*)\")?\s*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(\s*(<[^>]*>|[^\s)]*)(?:\s+\"([^\"]*)\")?\s*\)")
_AUTO_RE = re.compile(r"<((?:https?|ftp|mailto):[^>\s]+)>")
_RAWTAG_RE = re.compile(r"<!--.*?-->|</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>", re.S)
_BACKSLASH_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>~|])")
# A URL written on its own, with no [](): linked like GitHub does. Runs on already-escaped
# text, so held fragments (real links, raw tags) are placeholders and cannot be caught.
_BARE_URL_RE = re.compile(r"(?<![\w@/])(https?://[^\s<>\"'\x00]*[^\s<>\"'.,;:!?)\]\x00])")
_HOLD_RE = re.compile("\x00(\\d+)\x00")

_EMPHASIS = (
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S), "del"),
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S), "strong"),
    (re.compile(r"(?<![A-Za-z0-9])__(?=\S)(.+?)(?<=\S)__(?![A-Za-z0-9])", re.S), "strong"),
    (re.compile(r"\*(?=\S)([^*]+?)(?<=\S)\*", re.S), "em"),
    (re.compile(r"(?<![A-Za-z0-9_])_(?=\S)([^_]+?)(?<=\S)_(?![A-Za-z0-9_])", re.S), "em"),
)


def _esc(text: str) -> str:
    return _html.escape(text, quote=False)


def _attr(text: str) -> str:
    return _html.escape(text, quote=True)


def _url(raw: str) -> str:
    """Clean a link target. `javascript:` is dropped — reviewed docs are rendered, not trusted."""
    url = raw.strip()
    if url.startswith("<") and url.endswith(">"):
        url = url[1:-1]
    return "#" if re.match(r"\s*javascript:", url, re.I) else url


def _inline(text: str) -> str:
    """Render inline markup.

    Anything that must not be touched by later passes (code, links, raw tags) is
    swapped for a placeholder first, so emphasis only ever runs over plain text.
    """
    holds = []

    def hold(fragment: str) -> str:
        holds.append(fragment)
        return "\x00%d\x00" % (len(holds) - 1)

    def code(m):
        body = m.group(2)
        if body.startswith(" ") and body.endswith(" ") and body.strip():
            body = body[1:-1]
        return hold("<code>%s</code>" % _esc(body))

    def image(m):
        title = ' title="%s"' % _attr(m.group(3)) if m.group(3) else ""
        return hold('<img src="%s" alt="%s"%s>' % (_attr(_url(m.group(2))), _attr(m.group(1)), title))

    def link(m):
        title = ' title="%s"' % _attr(m.group(3)) if m.group(3) else ""
        return hold('<a href="%s"%s>%s</a>' % (_attr(_url(m.group(2))), title, _inline(m.group(1))))

    def auto(m):
        return hold('<a href="%s">%s</a>' % (_attr(m.group(1)), _esc(m.group(1))))

    text = _CODE_RE.sub(code, text)
    text = _IMG_RE.sub(image, text)
    text = _LINK_RE.sub(link, text)
    text = _AUTO_RE.sub(auto, text)
    text = _RAWTAG_RE.sub(lambda m: hold(m.group(0)), text)
    text = _BACKSLASH_RE.sub(lambda m: hold(_esc(m.group(1))), text)

    text = _esc(text)
    text = _BARE_URL_RE.sub(lambda m: '<a href="%s">%s</a>' % (m.group(1), m.group(1)), text)
    text = re.sub(r"(?: {2,}|\\)\n", "<br>\n", text)
    for pattern, tag in _EMPHASIS:
        text = pattern.sub(lambda m, t=tag: "<%s>%s</%s>" % (t, m.group(1), t), text)

    # A held fragment can contain another placeholder (a code span inside a link label)
    for _ in range(4):
        if not _HOLD_RE.search(text):
            break
        text = _HOLD_RE.sub(lambda m: holds[int(m.group(1))], text)
    return text


# ---------- blocks ----------

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^`\s]*)")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:\s+(.*?))?\s*$")
_HR = re.compile(r"^ {0,3}([-*_])[ \t]*(?:\1[ \t]*){2,}$")
_BQ = re.compile(r"^ {0,3}>[ ]?(.*)$")
_LI = re.compile(r"^( *)([-*+]|\d{1,9}[.)])(?:([ \t]+)(.*))?$")
_TABLE_SEP = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
_HTML_START = re.compile(r"^ {0,3}<(?:/?[A-Za-z][A-Za-z0-9-]*|!--)")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)\s*$")
_TASK = re.compile(r"^\[([ xX])\]\s+(.*)$")


def _is_block_start(line: str) -> bool:
    """True when the line begins a block, so an open paragraph has to end before it."""
    return bool(_FENCE.match(line) or _ATX.match(line) or _HR.match(line)
                or _BQ.match(line) or _LI.match(line) or _HTML_START.match(line))


def _slug(text: str, used: dict) -> str:
    """GitHub-style heading id, so in-document links (`[…](#heading)`) work."""
    base = re.sub(r"<[^>]+>", "", text)
    base = _html.unescape(base).strip().lower()
    base = re.sub(r"[^\w\s-]", "", base, flags=re.UNICODE).strip()
    base = re.sub(r"\s+", "-", base) or "section"
    used[base] = used.get(base, 0) + 1
    return base if used[base] == 1 else "%s-%d" % (base, used[base] - 1)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _marker_kind(marker: str) -> str:
    return "ol" if marker[:-1].isdigit() else "ul"


def _marker_shape(marker: str) -> str:
    """`-` / `*` / `1.` / `1)` — changing the shape starts a new list, as in CommonMark."""
    return _marker_kind(marker) + marker[-1]


def _unwrap_p(html_str: str) -> str:
    """Tight list items hold text directly, not a paragraph."""
    return re.sub(r"^<p>(.*?)</p>", lambda m: m.group(1), html_str, count=1, flags=re.S)


def _row_cells(line: str):
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", row)]


def _table(lines, start: int, ids: dict):
    header = _row_cells(lines[start])
    aligns = []
    for spec in _row_cells(lines[start + 1]):
        left, right = spec.startswith(":"), spec.endswith(":")
        aligns.append("center" if left and right else "right" if right else "left" if left else "")
    i = start + 2
    rows = []
    while i < len(lines) and lines[i].strip() and "|" in lines[i] and not _is_block_start(lines[i]):
        rows.append(_row_cells(lines[i]))
        i += 1

    def cell(tag, text, col):
        style = ' style="text-align:%s"' % aligns[col] if col < len(aligns) and aligns[col] else ""
        return "<%s%s>%s</%s>" % (tag, style, _inline(text), tag)

    head = "".join(cell("th", c, n) for n, c in enumerate(header))
    body = "".join(
        "<tr>%s</tr>" % "".join(
            cell("td", row[n] if n < len(row) else "", n) for n in range(len(header)))
        for row in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, body), i


def _list(lines, start: int, ids: dict):
    first = _LI.match(lines[start])
    base = len(first.group(1))
    kind = _marker_kind(first.group(2))
    shape = _marker_shape(first.group(2))
    start_num = int(first.group(2)[:-1]) if kind == "ol" else 1

    items, cur, content_indent, loose, blanks = [], None, 0, False, 0
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            blanks += 1
            i += 1
            continue
        item = _LI.match(line)
        indent = _indent_of(line)
        if item and (cur is None or indent < content_indent):
            if cur is not None and (len(item.group(1)) != base or _marker_shape(item.group(2)) != shape):
                break                       # a differently-shaped list starts here
            if cur is not None and blanks:
                loose = True                # items separated by a blank line
            content_indent = len(item.group(1)) + len(item.group(2)) + len(item.group(3) or " ")
            cur = [item.group(4) or ""]
            items.append(cur)
            blanks = 0
            i += 1
            continue
        if cur is None or (blanks and indent < content_indent):
            break                           # dedented after a blank line: the list is over
        if blanks:
            cur.extend([""] * blanks)       # a second block inside one item
            loose = True
            blanks = 0
        cur.append(line[content_indent:] if indent >= content_indent else line.lstrip())
        i += 1

    rendered = []
    tasks = False
    for item in items:
        while item and not item[-1].strip():
            item.pop()
        checked = None
        if item:
            task = _TASK.match(item[0])
            if task:
                checked = task.group(1).lower() == "x"
                item[0] = task.group(2)
                tasks = True
        inner = _blocks(item, ids)
        if not loose:
            inner = _unwrap_p(inner)
        if checked is not None:
            inner = '<input type="checkbox" disabled%s> %s' % (" checked" if checked else "", inner)
        rendered.append("<li>%s</li>" % inner)

    attrs = ' start="%d"' % start_num if kind == "ol" and start_num != 1 else ""
    attrs += ' class="task-list"' if tasks else ""
    return "<%s%s>%s</%s>" % (kind, attrs, "".join(rendered), kind), i


def _blocks(lines, ids: dict) -> str:
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        fence = _FENCE.match(line)
        if fence:
            marker, info = fence.group(1), fence.group(2)
            closing = re.compile(r"^ {0,3}%s{%d,}\s*$" % (re.escape(marker[0]), len(marker)))
            body, i = [], i + 1
            while i < n and not closing.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            cls = ' class="language-%s"' % _attr(info) if info else ""
            out.append("<pre><code%s>%s</code></pre>" % (cls, _esc("\n".join(body))))
            continue

        atx = _ATX.match(line)
        if atx:
            level = len(atx.group(1))
            text = re.sub(r"\s+#+$", "", (atx.group(2) or "").strip())
            out.append('<h%d id="%s">%s</h%d>' % (level, _slug(text, ids), _inline(text), level))
            i += 1
            continue

        if _HR.match(line):
            out.append("<hr>")
            i += 1
            continue

        if _BQ.match(line):
            body = []
            while i < n:
                quoted = _BQ.match(lines[i])
                if quoted:
                    body.append(quoted.group(1))
                elif lines[i].strip() and not _is_block_start(lines[i]):
                    body.append(lines[i])       # lazy continuation
                else:
                    break
                i += 1
            out.append("<blockquote>%s</blockquote>" % _blocks(body, ids))
            continue

        if _LI.match(line):
            html_str, i = _list(lines, i, ids)
            out.append(html_str)
            continue

        if "|" in line and i + 1 < n and "|" in lines[i + 1] and _TABLE_SEP.match(lines[i + 1]):
            html_str, i = _table(lines, i, ids)
            out.append(html_str)
            continue

        if _HTML_START.match(line):
            body = []
            while i < n and lines[i].strip():
                body.append(lines[i])
                i += 1
            out.append("\n".join(body))
            continue

        if line.startswith("    "):
            body = []
            while i < n and (lines[i].startswith("    ") or not lines[i].strip()):
                body.append(lines[i][4:])
                i += 1
            while body and not body[-1].strip():
                body.pop()
            out.append("<pre><code>%s</code></pre>" % _esc("\n".join(body)))
            continue

        para, i = [line], i + 1
        level = None
        while i < n and lines[i].strip():
            setext = _SETEXT.match(lines[i])
            if setext:
                level = 1 if setext.group(1)[0] == "=" else 2
                i += 1
                break
            if _is_block_start(lines[i]):
                break
            para.append(lines[i])
            i += 1
        text = "\n".join(l.lstrip() for l in para).strip("\n")
        if level:
            out.append('<h%d id="%s">%s</h%d>' % (level, _slug(text, ids), _inline(text), level))
        else:
            out.append("<p>%s</p>" % _inline(text))
    return "".join(out)


def render_body(text: str) -> str:
    """Render Markdown to an HTML fragment."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [re.sub(r"^[ \t]+", lambda m: m.group(0).expandtabs(4), l) for l in text.split("\n")]
    ids, out = {}, []

    # YAML front matter is part of the document under review, so it is shown, not hidden
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() in ("---", "..."):
                out.append('<div class="frontmatter"><pre>%s</pre></div>'
                           % _esc("\n".join(lines[1:end])))
                lines = lines[end + 1:]
                break

    out.append(_blocks(lines, ids))
    return "".join(out)


_DOC = """<!DOCTYPE html>
<html lang="%(lang)s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
:root {
  color-scheme: light;
  --bg: #ffffff;
  --ink: #22252b;
  --ink-soft: #5b6270;
  --ink-faint: #8a919f;
  --border: #e4e7ee;
  --border-strong: #d4d9e3;
  --code-bg: #f2f4f7;
  --block-bg: #fafbfc;
  --link: #2f6bb0;
  --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Hiragino Sans", sans-serif;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #14181e;
  --ink: #e6e9ef;
  --ink-soft: #a7aebb;
  --ink-faint: #737d8c;
  --border: #2a3039;
  --border-strong: #3b4350;
  --code-bg: #212630;
  --block-bg: #1a1f27;
  --link: #6fabe2;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: var(--sans); font-size: 15px; line-height: 1.85;
  -webkit-font-smoothing: antialiased;
}
.md { max-width: 820px; margin: 0 auto; padding: 34px 40px 140px; }
.md > :first-child { margin-top: 0; }
h1, h2, h3, h4, h5, h6 { line-height: 1.45; font-weight: 700; margin: 1.9em 0 .7em; }
h1 { font-size: 27px; letter-spacing: -.01em; padding-bottom: .3em; border-bottom: 1px solid var(--border); }
h2 { font-size: 21px; padding-bottom: .3em; border-bottom: 1px solid var(--border); }
h3 { font-size: 17px; }
h4 { font-size: 15px; }
h5, h6 { font-size: 14px; color: var(--ink-soft); }
p { margin: 0 0 1.1em; }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
strong { font-weight: 700; }
del { color: var(--ink-faint); }
hr { height: 1px; border: 0; background: var(--border); margin: 2.2em 0; }
ul, ol { margin: 0 0 1.1em; padding-left: 1.6em; }
li { margin: .28em 0; }
li > ul, li > ol { margin: .28em 0; }
ul.task-list { list-style: none; padding-left: .3em; }
ul.task-list input { margin-right: .5em; }
blockquote {
  margin: 0 0 1.1em; padding: .2em 0 .2em 1.1em;
  border-left: 3px solid var(--border-strong); color: var(--ink-soft);
}
blockquote > :last-child { margin-bottom: 0; }
code {
  font-family: var(--mono); font-size: .88em;
  background: var(--code-bg); border-radius: 4px; padding: .15em .38em;
}
pre {
  margin: 0 0 1.3em; padding: 13px 15px; overflow-x: auto;
  background: var(--block-bg); border: 1px solid var(--border); border-radius: 8px;
}
pre code { background: none; padding: 0; font-size: 12.8px; line-height: 1.7; }
table { border-collapse: collapse; margin: 0 0 1.3em; display: block; overflow-x: auto; }
th, td { border: 1px solid var(--border); padding: 7px 12px; text-align: left; }
th { background: var(--block-bg); font-weight: 700; }
img { max-width: 100%%; height: auto; }
.frontmatter {
  margin: 0 0 1.6em; padding: 10px 14px;
  background: var(--block-bg); border: 1px dashed var(--border-strong); border-radius: 8px;
}
.frontmatter pre {
  margin: 0; padding: 0; border: 0; background: none;
  font-size: 12px; color: var(--ink-soft); white-space: pre-wrap;
}
</style>
</head>
<body>
<article class="md">
%(body)s
</article>
</body>
</html>
"""


def render_document(text: str, title: str = "", lang: str = "") -> str:
    """Render Markdown to a full, self-contained HTML document."""
    body = render_body(text)
    if not lang:
        lang = "ja" if re.search(r"[぀-ヿ一-鿿]", text) else "en"
    return _DOC % {"lang": lang, "title": _esc(title or "document"), "body": body}


if __name__ == "__main__":
    import pathlib
    import sys

    src = pathlib.Path(sys.argv[1])
    sys.stdout.write(render_document(src.read_text(encoding="utf-8"), src.name))
