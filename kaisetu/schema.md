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

