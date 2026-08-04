# review-data.json schema

The review data passed to `scripts/serve.py`. The LLM generates only this JSON; the template renders the HTML.

Write all human-facing text (title, tagline, overview, intent, impact, explain, annotations) in the
language the user is conversing in.

```jsonc
{
  "title": "Review of unstaged app/system URL cleanup",     // page title
  // Write tagline / overview as "technical explanation ＝ what happens as a result" (full-width ＝).
  // The right side of ＝ gets its own style on screen. See "Writing the overview" below.
  "tagline": "Consolidate URL building into one place ＝ prepares the migration so links never break",
  "overview": "- Consolidate URL building and host checks into resolveAppUrl ＝ URLs are built in one place so missed updates no longer break links\n- …",
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
      "risk": "high",                   // "high" | "medium" | "low"
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

**Each line carries both "an explanation an engineer understands" and "an outcome a non-engineer
understands", joined by the full-width equals sign `＝` (U+FF1D).**

```
Consolidate scattered URL building and host checks into resolveAppUrl ＝ URLs are built in one place, so missed updates can no longer cause broken links
```

- Left of `＝`: the usual technical explanation (function/module names are fine)
- Right of `＝`: **what happens as a result**, in words for someone who doesn't read code.
  Describe what changes for the feature, its users, or operations. No jargon, file names, or function names.
- The tagline renders its right side as a second line; each overview line renders its right side as a
  styled continuation.
- The half-width `=` does NOT split (so `=` inside code is never caught). A line with no meaningful
  outcome can omit `＝`.

## Granularity guide

- **group** = the intent of a change (the unit of risk assessment)
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
  "markdown": "…"                 // human-readable summary (threads as nested bullet lists)
}
```

## Rendering rules (template behavior)

- Groups are displayed in `risk` order (high → medium → low). Order them by risk in the JSON as well
  (within the same risk, JSON order is preserved).
- A section's `explain` is shown as an "AI explanation" callout at the top of the section's first hunk.
- Groups containing `type: "question"` annotations get a "question" badge in the index.
- Human comments are saved to localStorage and to the server's state.json. The localStorage key is
  derived from the diff structure (hunk IDs and bodies), so rewriting explanations preserves comments.
- Comments are threads. A "Reply" button appears under each AI answer so the human can continue.
  Threads ending with a human message show "Awaiting AI reply", and the header comment counter shows
  "awaiting N".
- When review-data.json is rewritten, the page detects it within seconds and rebuilds (while a comment
  is being typed, an "Apply to page" bar appears instead of rebuilding automatically).
