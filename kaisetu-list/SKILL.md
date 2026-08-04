---
name: kaisetu-list
description: List past kaisetu reviews and re-open the review UI (local server) for the one the user picks. After selection, only start the server; handle comments only after "Finish review" is pressed on the page.
---

# kaisetu-list

Lists the history of reviews done with `/kaisetu` and reopens the selected one.
Reviews are stored at `~/.kaisetu/<repo-name>/<YYYYMMDD-HHMMSS>/review-data.json`.

## 1. Collect the list

```bash
find ~/.kaisetu -mindepth 3 -maxdepth 3 -name 'review-data.json' | sort -r
```

For each review, read the following. **Never Read `review-data.json` itself — it contains the full diff.**
Take display values from the small `meta.json` in the same directory (one Bash call looping with jq
over all entries works well):

- Timestamp: the directory name (`YYYYMMDD-HHMMSS`)
- Repository: the parent directory name
- `title` / `tagline` / `repoRoot`: from `meta.json` (only for old reviews without one, extract fields
  with `jq -r '.title, .repoRoot'` from review-data.json — still no Read)
- Status: **finished** if `review-data.result.json` exists in the same directory. If so, also get the
  comment count (length of `.comments + .groupComments`) with jq

## 2. Present the list and let the user choose

Present a table, newest first:

| # | Time | Repository | Title | Status |
|---|---|---|---|---|
| 1 | 2026-07-28 12:00 | myapp | app/system URL cleanup | ✔ finished (3 comments) |
| 2 | … | … | … | ─ open |

- With 4 or fewer candidates, AskUserQuestion may be used. Otherwise show the table and ask for a number.
- If there are none, say "No review history found" and stop.

## 3. Reopen the selected review

Whether or not it is finished, **only re-display the review page** at this point.
Do not act on past comments or present summaries yet.

1. If an old `review-data.result.json` exists, delete it (otherwise completion detection fires
   immediately; on-screen comments are restored from the browser's localStorage, so nothing is lost).
2. Follow steps 3–4 onward of the kaisetu skill's SKILL.md to start the server with that
   `review-data.json` (use `repoRoot` as CWD). Set up the background completion wait the same way.
3. Say only "The review page is open" and wait. When the user presses "Finish review", follow
   kaisetu's steps 5–6 to read and handle the result.

All subsequent file operations and diff references are relative to `repoRoot`.
