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
  "stats": { "files": 107, "hunks": 268, "additions": 1468, "deletions": 812 },
  "groups": [
    {
      "id": "g1",                       // unique ID (g1, g2, ...)
      "title": "Shared URL / host-check foundation",
      "intent": "Consolidate per-deployment-mode URL building and host checks into one place…", // why this change exists (1–3 sentences)
      "impact": "Foundation code also used on the legacy path, so the blast radius is wide.",   // blast-radius note (optional)
      "importance": "high",             // "high" | "medium" | "low" — how carefully this needs reading
      "tags": ["refactor"],             // feat / fix / refactor / test / docs / chore etc.
      "sections": [
        // Coherent per-feature units. Explanations are written at this level.
        // Hunks from the same file may appear in multiple sections/groups.
        {
          "id": "s1",                              // unique ID (s1, s2, ...)
          "title": "New shared entry point resolveAppUrl",
          "explain": "URL building is consolidated into this function; the subdomain/legacy-path branches now live here. Call sites…", // coherent explanation (a few sentences)
          "hunks": [
            {
              "id": "h079",                                    // unique ID (h001, h002, ...)
              "file": "webapp/src/lib/auth.subdomain.test.ts", // path relative to repo root
              "diff": "@@ -1,10 +1,13 @@\n import Cookies from 'js-cookie';\n+import { vi } from 'vitest';\n-import { save } from './auth';",
              // ↑ first line is the @@ header, rest is the hunk body as unified diff (verbatim from git diff)
              "annotations": [
                // Only where line-level notes are needed (put longer explanations in the section's explain)
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

## HTML review mode

When `html` is set, the reviewed target is that HTML file itself. The page renders it in an iframe and
the human comments on its elements — no groups, no explanations.

```jsonc
{
  "title": "Review of the release notes page",
  "html": "docs/release-notes.html",   // reviewed file: absolute, or relative to the server CWD / this file
  "generatedAt": "2026-08-05 10:00",
  "repoRoot": "/Users/me/repos/myapp"
}
```

- All diff-review fields (`groups`, `overview`, `tagline`, `stats`, `base`, `plan`) are omitted.
- Files sitting next to the HTML (CSS, JS, images) are served, so relative links work.
- Rewriting the HTML file bumps the version, so the page reloads with the new render within seconds;
  comments stay anchored to their elements.
- `htmlInline` is added by `serve.py --build` only (it embeds the page for the static, server-less HTML).
  Never write it by hand.

Comments are anchored to a CSS selector (`body > main > p:nth-of-type(1)`), with the element's text kept
as a fallback anchor for when the page changes. `key: "page"` is a comment on the page as a whole.

## Granularity guide

- **group** = the intent of a change (the unit importance is judged on)
- **section** = a coherent per-feature unit (the unit of explanation). Size it so "reading this section
  gives you the whole change for that feature"
- **annotation** = a line-level note. Not every hunk needs one

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
  "elementComments": [                  // HTML review mode
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
  "elementComments": [            // HTML review mode: comments on elements of the reviewed page
    {
      "key": "body > main > p:nth-of-type(1)",
      "selector": "body > main > p:nth-of-type(1)",   // null = a comment on the whole page (key "page")
      "label": "p “The checkout flow now confirms payment in a …”",
      "text": "The checkout flow now confirms payment in a single step. …",  // text at comment time
      "anchored": true,           // false = that element no longer exists in the current HTML
      "messages": [ … ], "resolved": false, "awaiting": true
    }
  ],
  "html": "docs/release-notes.html",   // reviewed page (null in diff mode)
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
  In HTML review mode it comes from the reviewed page's path, so fixing the page preserves them too.
- HTML review mode: elements are anchored by CSS selector, falling back to their text when the page
  changed. Commented elements get numbered pins over the page, and threads sit in a right-hand column in
  page order — the header's comment counter toggles that column (there is no separate drawer; the pin and
  the number badge jump between page and thread). Clicking a card's header folds the thread; resolved
  threads start folded, showing the anchor line plus a one-line preview. Turning off "Comment mode" (`p`)
  hides the pins and lets the human use the page normally (links, buttons).
- Comments are threads. A "Reply" button appears under each AI answer so the human can continue.
  Threads ending with a human message show "Awaiting AI reply", and the header comment counter shows
  "awaiting N".
- When review-data.json is rewritten, the page detects it within seconds and rebuilds (while a comment
  is being typed, an "Apply to page" bar appears instead of rebuilding automatically).
