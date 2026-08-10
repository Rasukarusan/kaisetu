# review-data.json schema

The review data passed to `scripts/serve.py`. The LLM generates only this JSON; the template renders the HTML.

Write all human-facing text (title, tagline, overview, intent, impact, explain, annotations) in the
language the user is conversing in.

```jsonc
{
  "title": "Review of unstaged app/system URL cleanup",     // page title
  // The tagline is one plain sentence anyone can read — no ＝, no code vocabulary.
  "tagline": "Links to the app and the admin tools are built in one place, so they stop breaking",
  // Each overview line is "technical explanation ＝ what happens as a result" (full-width ＝).
  // The right side of ＝ gets its own line on screen. See "Writing the overview" below.
  "overview": "- Consolidate URL building and host checks into resolveAppUrl ＝ URLs are built in one place so missed updates no longer break links\n- …",
  "lang": "ja",                                         // optional: language of the review text. The page's own
                                                        // labels (解説 / メモ / 疑問 …) follow it. Detected from
                                                        // the prose when omitted, so it is rarely needed
  "generatedAt": "2026-07-25 09:30",                    // generation time (write it yourself; don't compute in JS)
  "base": "main..HEAD + unstaged",                      // human description of the diff scope
  "plan": "plans/url-cleanup.md",                       // plan file consulted (path relative to repo root), or null. Rendered as a link served at /plan
  "repoRoot": "/Users/me/repos/myapp",                  // absolute path of the target repo (used by /kaisetu-list as the base path when reopening)
  "stats": {
    "files": 107, "hunks": 268, "additions": 1468, "deletions": 812,
    // optional: what the added lines are made of. Rendered as a bar + legend under the overview.
    // Largest first. See "Writing the composition" below
    "breakdown": [
      { "kind": "generated", "label": "Generated (lock file, snapshots, openapi)", "files": 5, "additions": 812 },
      { "kind": "test", "label": "Tests", "files": 24, "additions": 380 },
      { "kind": "code", "label": "Implementation", "files": 39, "additions": 276 }
    ],
    "core": "The core is 4 files in the auth server, 295 lines"  // optional: one sentence
  },
  "groups": [
    {
      "id": "g1",                       // unique ID (g1, g2, ...)
      "title": "Shared URL and host-check foundation",  // short plain noun phrase — no identifiers, no dash
      "intent": "URL building and host checks for every deployment mode live in one place…",  // what this part does and why (1–2 sentences)
      "impact": "Spans the web app, the admin tools, and the legacy path.",  // one sentence: which areas it reaches (optional)
      "importance": "high",             // "high" | "medium" | "low" — how carefully this needs reading
      "tags": ["refactor"],             // feat / fix / refactor / test / docs / chore etc.
      "sections": [
        // 1–3 per group. A section is a story within the group, not one mechanism or one file.
        // Hunks from the same file may appear in multiple sections/groups.
        {
          "id": "s1",                              // unique ID (s1, s2, ...)
          "title": "Shared URL resolution",
          "explain": "Builds every app and admin URL from one function, with the deployment-mode branches kept inside it. Call sites pass the mode instead of assembling hosts themselves.", // 1–3 sentences
          "hunks": [
            {
              "id": "h079",                                    // unique ID (h001, h002, ...)
              "file": "webapp/src/lib/auth.subdomain.test.ts", // path relative to repo root
              "diff": "@@ -1,10 +1,13 @@\n import Cookies from 'js-cookie';\n+import { vi } from 'vitest';\n-import { save } from './auth';",
              // ↑ first line is the @@ header, rest is the hunk body as unified diff (verbatim from git diff)
              "annotations": [
                // Only where one line is unreadable without a note. One sentence, a handful per review.
                {
                  "type": "explain",              // "explain" (note) | "question" (something to confirm with the human)
                  "match": "import { vi }",       // anchor: shown right below the first hunk-body line containing this string
                  "line": 2,                      // or a hunk-body line number (1-based, excluding the @@ line). match takes precedence
                  "text": "Import added for the migration to vitest's mock API."
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## Writing the overview (tagline / overview)

### tagline — one sentence anyone can read

It sits large at the top of the review, so it has to land for someone who does not read code.
No function or file names, no jargon, and **no `＝`** — say what the change means for the product,
its users, or operations, in one sentence.

```
Links to the app and the admin tools are built in one place, so they stop breaking
```

### overview — one line per point, both readers at once

**Each line carries both "an explanation an engineer understands" and "an outcome a non-engineer
understands", joined by the full-width equals sign `＝` (U+FF1D).**

```
Consolidate scattered URL building and host checks into resolveAppUrl ＝ URLs are built in one place, so missed updates can no longer cause broken links
```

- Left of `＝`: the usual technical explanation (function/module names are fine)
- Right of `＝`: **what happens as a result**, in words for someone who doesn't read code.
  Describe what changes for the feature, its users, or operations. No jargon, file names, or function names.
- On screen the right side goes on its own line, led by an arrow (`→`) — write the data with `＝`,
  the page renders the outcome as "and so this happens".
- The half-width `=` does NOT split (so `=` inside code is never caught). A line with no meaningful
  outcome can omit `＝`.

## Writing the composition (stats.breakdown / stats.core)

"107 files, +1468" reads as a mountain, and most of a large diff is usually lock files and generated
snapshots. `breakdown` says how much of it is actually there to read, as a bar under the overview.

- One entry per category, **largest `additions` first**. Only categories that exist in this diff —
  never pad the list with zeros. Percentages are computed from `additions`, so leave them out
- `kind` picks the colour and is one of `code` / `test` / `generated` / `migration` / `infra` /
  `config` / `docs` / `other`. Hand-written code is the saturated colour, generated files the faintest
- `label` is what the reader sees. Name the actual files when it helps
  (`Generated (drizzle snapshots, pnpm-lock, openapi)`), and keep it to one line
- `files` and `additions` come straight from `git diff --numstat`; they should add up to `stats`
- `core` is one optional sentence pointing at the heart of the change — the few files that carry the
  intent, with their line count (`The core is 4 files in the auth server, 295 lines`)

The block is omitted entirely when `breakdown` is missing or empty.

## Document review mode

When `doc` is set, the reviewed target is that document file itself. The page renders it in an iframe
and the human comments on its elements — no groups, no explanations.

```jsonc
{
  "title": "Review of the release notes",
  "doc": "docs/release-notes.md",   // reviewed file: absolute, or relative to the server CWD / this file
  "generatedAt": "2026-08-05 10:00",
  "repoRoot": "/Users/me/repos/myapp"
}
```

- All diff-review fields (`groups`, `overview`, `tagline`, `stats`, `base`, `plan`) are omitted.
- `.md` / `.markdown` is rendered to HTML by the server; `.html` is served exactly as written.
  The rendered Markdown follows the review page's light / dark setting; a reviewed HTML file is
  never touched.
- Files sitting next to the document (images, CSS, JS, and other Markdown files) are served, so
  relative links work.
- Rewriting the source file bumps the version, so the page reloads with the new render within seconds;
  comments stay anchored to their elements.
- `docKind` (`"markdown"` | `"html"`) is filled in by `serve.py` from the file's extension, and
  `docInline` is added by `serve.py --build` only (it embeds the rendered document for the static,
  server-less HTML). Never write either by hand.

Comments are anchored to a CSS selector (`body > main > p:nth-of-type(1)`), with the element's text kept
as a fallback anchor for when the document changes. Markdown headings are rendered with an id, so their
selectors (`#open-questions`) survive edits anywhere else in the file. `key: "page"` is a comment on the
document as a whole.

## Granularity guide

The page is a reading guide, not a write-up of the implementation. Consolidate: fewer, larger units
with shorter text. See "Group and explain" in SKILL.md for the writing rules.

- **group** = one architectural unit of intent — a service, a layer, a boundary (the unit importance is
  judged on). **4–7 groups, however large the diff is**; a 100-file diff is still 4–7 groups
- **section** = a story within the group (the unit of explanation). **1–3 per group**; a section holding
  50 hunks is normal. Never one per file, per mechanism, or per edge case
- **annotation** = a note on one line that can't be read without it. A handful across the whole review

| Field | Budget |
|---|---|
| `tagline` | 1 sentence |
| `overview` | 3–5 lines, one point and one sentence per line |
| `intent` | 1–2 sentences |
| `impact` | 1 sentence naming the areas the change reaches |
| `explain` | 1–3 sentences |
| `annotations[].text` | 1 sentence |

These are hard caps. If the text doesn't fit, the unit is too fine-grained — merge it, or drop the
detail. Titles, intents and overview lines carry no identifiers or syntax; name the role in plain words.

## List metadata (meta.json)

A small file `/kaisetu-list` uses for its listing. Put it next to review-data.json.
All values are copies of the same-named fields in review-data.json (so the list never parses the full diff).

```jsonc
{
  "title": "Review of unstaged app/system URL cleanup",
  "tagline": "Consolidate URL building into one place",
  "repoRoot": "/Users/me/repos/myapp",
  "generatedAt": "2026-07-25 09:30"
}
```

## Answer file (review-data.replies.json)

AI answers to human comments. Put it in the same directory as the review data; the page polls it every
few seconds and shows each answer in its thread as an "AI" message (server mode only).

Comments are **threads**. `replies[i]` answers the i-th (0-based) human message in that thread.
When the human replies to an answer, the human messages grow — so **load the existing replies.json and
append to the `replies` arrays** (removing past answers removes them from the page).

```jsonc
{
  "comments": [
    {
      "key": "h081:2",            // use the key exactly as it appears in result.json comments[].key
      "replies": [
        "Fixed: hosts with a port number are now accepted.",     // answer to the 1st comment
        "IPv6 is not handled yet. I can normalize via URL.hostname if needed." // answer to the reply
      ]
    }
  ],
  "groupComments": [
    { "group": "g1", "replies": ["You're right. The design is…"] }
  ],
  "docComments": [
    { "target": "overview", "replies": ["Trimmed to 3 points and moved the legacy-path item first."] }
  ],
  "elementComments": [                  // document review mode
    { "key": "body > main > p:nth-of-type(1)", "replies": ["Fixed: replaced the jargon with plain wording."] }
  ]
}
```

## Comments on explanations

Just like diff lines, the prose the AI wrote shows a `+` on hover for commenting.
There are 3 targets:

| Target | In result JSON | Field to rewrite |
|---|---|---|
| Overview | `docComments` with `target: "overview"` | `tagline` / `overview` |
| Group intent | `groupComments` with `group: "<gid>"` | that group's `intent` / `impact` |
| AI explanation (section) | `docComments` with `target: "section:<sid>"` | that section's `title` / `explain` |

For "this is unclear, rewrite it" requests, **just rewrite the field in review-data.json and save**.
The server re-reads the file and the page rebuilds (comments are preserved).

**Never change `groups[].id` / `sections[].id` / the `hunks` structure.**
Comments hang off hunk IDs and line numbers, so restructuring the diff shifts their anchors.

## Result file (review-data.result.json)

Written when "Finish review" is pressed. Each comment is a thread of alternating human and AI messages.

```jsonc
{
  "title": "…",
  "finished": true,
  "comments": [
    {
      "key": "h081:2",
      "file": "webapp/src/lib/url-config.ts",
      "line": "L12",
      "code": " export const userUrlMode = env.USER_URL_MODE;",
      "messages": [
        { "role": "human", "text": "Wouldn't this reject hosts with a port?" },
        { "role": "ai",    "text": "Fixed: …" },
        { "role": "human", "text": "What about IPv6?" }   // ← ends with human = unanswered
      ],
      "resolved": false,
      "awaiting": true            // unresolved AND ends with a human message (= needs an answer)
    }
  ],
  "groupComments": [
    { "group": "g1", "messages": [ … ], "resolved": false, "awaiting": true }
  ],
  "docComments": [                // comments on prose the AI wrote (overview / section explanations)
    { "target": "overview", "label": "Overview", "messages": [ … ], "resolved": false, "awaiting": true }
  ],
  "elementComments": [            // document review mode: comments on elements of the reviewed document
    {
      "key": "body > main > p:nth-of-type(1)",
      "selector": "body > main > p:nth-of-type(1)",   // null = a comment on the whole document (key "page")
      "label": "p “The checkout flow now confirms payment in a …”",
      "text": "The checkout flow now confirms payment in a single step. …",  // text at comment time
      "anchored": true,           // false = that element no longer exists in the current render
      "messages": [ … ], "resolved": false, "awaiting": true
    }
  ],
  "doc": "docs/release-notes.md",   // reviewed document (null in diff mode)
  "markdown": "…"                 // human-readable summary (threads as nested bullet lists)
}
```

## Rendering rules (template behavior)

- Groups are displayed in `importance` order (high → medium → low). Order them that way in the JSON as
  well (within the same level, JSON order is preserved).
- Hunks render side by side by default (old left, new right); deletions line up with the additions that
  replaced them. The header's "Split" toggle switches to the unified view and is remembered per browser.
  Comments are keyed by hunk ID and row index in both layouts, so switching never moves them.
- A section's `explain` is shown as an "AI explanation" callout at the top of the section's first hunk.
- Groups containing `type: "question"` annotations get a "question" badge in the index.
- Human comments are saved to localStorage and to the server's state.json. The localStorage key is
  derived from the diff structure (hunk IDs and bodies), so rewriting explanations preserves comments.
  In document review mode it comes from the reviewed file's path, so fixing it preserves them too.
- How the reader likes the page — `theme`, `split`, `splitPos` — is kept per user in
  `~/.kaisetu/prefs.json` and embedded into the page at render time, so a setting made in one review
  is already in place when the next one opens. It cannot live in localStorage: each review is served
  on a fresh port, and localStorage is scoped to the origin. serve.py owns this file; never write
  review data into it.
- Document review mode: the render is read as rows — the innermost blocks (paragraph, heading, list
  item, table row, code block); wrappers are not rows. Hovering a row puts a `+` in its gutter and
  pressing it opens the comment, the same gesture as the `+` on a diff line; the document itself
  never reacts to the pointer. Rows are anchored by CSS selector, falling back to their text when the
  document changed. A commented row keeps a numbered pin where its `+` was, and threads sit in a
  right-hand column in document order — the header's comment counter toggles that column (there is no
  separate drawer; the pin and the number badge jump between document and thread). Clicking a card's
  header folds the thread; resolved threads start folded, showing the anchor line plus a one-line
  preview. Turning off "Comment mode" (`p`) hides the `+` and the pins and lets the human use the
  document normally (links, buttons).
- Comments are threads. A "Reply" button appears under each AI answer so the human can continue.
  Threads ending with a human message show "Awaiting AI reply", and the header comment counter shows
  "awaiting N".
- When review-data.json is rewritten, the page detects it within seconds and rebuilds (while a comment
  is being typed, an "Apply to page" bar appears instead of rebuilding automatically).
