---
name: kaisetu-html
description: Write the shareable HTML write-up of a branch — the same explain.html kaisetu puts behind its Explain tab — without the diff review. It opens in the review UI, so it can be read and commented on row by row, and the comments come back to the session via "Finish". Use it for "explain this branch to the team", "make the share doc", "write the HTML".
---

# kaisetu-html

The write-up on its own. `/kaisetu` produces one alongside a review; this skill produces just the
page — for a branch already reviewed, work that never needed a diff review, or a document the team
is waiting on.

The output is **one self-contained HTML file** with figures, a cast and the design decisions,
readable by the engineer who never opened this branch and by the non-engineer who never will.

The directory containing this SKILL.md is `$SKILL_DIR`. The kaisetu skill sits next to it
(`$SKILL_DIR/../kaisetu`, referred to as `$KAISETU_DIR`); this skill uses its writing rules
(`$KAISETU_DIR/explain.md`), its template (`$KAISETU_DIR/explain-template.html`) and its server
(`$KAISETU_DIR/scripts/serve.py`).

Write the page in the language the user is conversing in.

## 1. Look for one already written for this branch

```bash
python3 $KAISETU_DIR/scripts/find_review.py --doc explain.html   # run with the target repo as CWD
```

One line per match — `<dir>` / `<generatedAt>` / `open|finished` / `<title>` — newest first, and
nothing when there is none.

- **Nothing printed** → go to step 2.
- **Something printed** → ask the user (AskUserQuestion): **reopen** that write-up (the page and its
  comment threads are still there — skip to step 4 with that directory), or **write a new one**.

## 2. Collect the material

- Scope: the current branch unless the user says otherwise.
  ```bash
  BASE=$(bash $KAISETU_DIR/scripts/base-branch.sh)   # prints UNKNOWN (exit 1) → ask which branch
  git log --oneline "$BASE"..HEAD
  git diff "$BASE"...HEAD --stat
  ```
- **Read the commit bodies** (`git show`) — design reasoning is densest there — plus the PR
  (`gh pr view`) and any plan or handoff document in the repo.
- Read the code the diff points at, enough to draw the figures honestly: the data model, the flow
  between services, what a request does. This is the expensive half of the work; the page is thin
  prose over what you learn here.
- Numbers (diff size, test counts) go in only when you checked them just now.

## 3. Write the page

Create `~/.kaisetu/<repo-name>/<YYYYMMDD-HHMMSS>/` (`$REVIEW_DIR`; never write into the target repo)
and write `$REVIEW_DIR/explain.html` following **`$KAISETU_DIR/explain.md`** — structure, length
budgets, which figure explains what, and the read-through at the end. Take the CSS from
`$KAISETU_DIR/explain-template.html` as it is.

If the user names a destination (`docs/release.html`, a ticket folder), write it there instead and
point `doc` at that path in the next step.

## 4. Open it for reading and comments

The write-up is reviewed the way any document is: rendered in the page, commented on row by row.

1. Write `$REVIEW_DIR/review-data.json`:
   ```json
   {
     "title": "Explainer: author follow and new releases",
     "doc": "explain.html",
     "branch": "feat/author-follow",
     "generatedAt": "2026-08-11 10:00",
     "repoRoot": "/Users/me/repos/myapp"
   }
   ```
   Nothing else — no `groups`, `overview` or `stats`. Write `$REVIEW_DIR/meta.json` too (title /
   tagline / branch / doc / repoRoot / generatedAt), so `/kaisetu-list` can reopen it and step 1 can
   find it.
2. Start the server with the target repo root as CWD, as a long-running process:
   ```bash
   python3 $KAISETU_DIR/scripts/serve.py $REVIEW_DIR/review-data.json
   ```
   (Claude Code: Bash with `run_in_background: true`. The URL, result path and pid are printed.)
3. Wait for the result file in the background:
   ```bash
   until [ -f $REVIEW_DIR/review-data.result.json ]; do sleep 2; done
   ```
4. Tell the user the page is open **and give them the path of the HTML file** — it is self-contained,
   so sending that one file is all it takes to share it.

## 5. Handle the comments

Follow kaisetu's steps 5–7 (`$KAISETU_DIR/SKILL.md`), which for a document means:

- Read `review-data.result.json` and act on every `elementComments` thread with `awaiting: true`
  (`selector` / `label` / `text` say which row it is; `anchored: false` means that row is gone).
- **Fix `explain.html` directly.** The server watches it, so the page reloads with the fix within
  seconds and the comments stay anchored.
- Answer under `elementComments` in `$REVIEW_DIR/review-data.replies.json` (format in
  `$KAISETU_DIR/schema.md`); the page shows each answer in its thread.
- Leave the server running — the user replies and presses "Finish" again. Delete the result file and
  wait again. `kill <pid>` when the exchange is done.

## Notes

- Static copy for sending elsewhere: the file itself is already that. `serve.py <data.json> --build
  out.html` makes a standalone copy of the *review page* instead, comments and all.
- Reviewing a diff at the same time? Use `/kaisetu` — it writes this same page and puts it behind the
  review's Explain tab, which is one page instead of two.
- Past write-ups are listed and reopened with `/kaisetu-list`.
