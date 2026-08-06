---
name: kaisetu
description: Group a large diff by intent and launch a local review UI, sorted by importance with AI explanations. The human makes the review judgments; comments made on screen come back to the session via "Finish review". Use explicitly for large diffs or self-review after implementing a plan.
---

# kaisetu

A skill that launches a review UI showing a diff as "groups by intent × sorted by importance × with AI explanations".
**Reviewing (judging good/bad) is the human's job. The AI only organizes the diff for reading and adds explanations.**
Comments the human leaves on screen come back to you to act on.

Works with both Claude Code and Codex — map the steps below to whatever process-execution and
wait facilities your environment provides.

The directory containing this SKILL.md is referred to as `$SKILL_DIR` below.
Always read `$SKILL_DIR/schema.md` for the data format.

**Language:** write all review content (title, tagline, overview, intents, explanations, annotations)
in the language the user is conversing in. The page's own labels follow the same language
(e.g. a Japanese review shows 解説 / メモ / 疑問 instead of AI note / Note / Question) — it is detected
from the text, so set `lang` in review-data.json only when the detection would get it wrong.

There are two modes, decided by what is being reviewed:

- **Diff review** (default) — steps 1–6 below.
- **HTML review** — the target is an HTML file itself. No diff, no grouping, no explanations:
  the page is rendered and the human comments on it element by element.
  Use it when the user passes an `.html` file or asks to review a rendered page / a document that is
  an HTML file. See "HTML review mode" at the end.

## Overall flow

```
1. Collect diff → 2. Group + explain → 3. Generate review-data.json → 4. Start serve.py (browser opens)
→ 5. Human comments on screen (diff lines, groups, overview, AI explanations) → "Finish review"
→ 6. Read the result JSON and respond (fix code / answer / rewrite explanations)
     ↑___ human replies to answers and resubmits (threads); rewritten explanations auto-refresh the page ___|
```

## 1. Collect the diff

- Put working files in `~/.kaisetu/<repo-name>/<YYYYMMDD-HHMMSS>/` (never pollute the target repo).
  Create a fresh timestamped directory per review (past reviews are browsed via `/kaisetu-list`, so never overwrite).
  This directory is referred to as `$REVIEW_DIR` below.
- Scope: follow the user's arguments if given. Otherwise use uncommitted changes (`git diff HEAD`).
  For a whole branch, determine the repo's default base branch and use `git diff $BASE...HEAD`
  (check the remote HEAD, then the PR base, then fall back to `main`).
- Save:
  - `diff.patch`: the full diff (`git diff ... > diff.patch`)
  - stats: `git diff --shortstat` and `grep -c '^@@' diff.patch` (files / hunks / +N −N)

## 2. Group and explain

If a plan exists (`plans/*.md` etc.), read it first so you can explain the intent of the changes accurately.

Organize in 3 levels: **group (unit of intent) > section (unit of explanation per feature) > hunk**.

- First write the `tagline`: **one sentence that anyone can read**, shown large at the top.
  No function or file names, no jargon, no `＝` — say what the change means for the product, its users,
  or operations. **It may be slightly imprecise — favor a rough description that conveys the whole
  thing at a glance.**
  Example: `Links to the app and the admin tools are built in one place, so they stop breaking`
- Then write the `overview`: 3–5 bullet points (lines starting with `- `, newline-separated) describing
  what this branch/diff does overall. Base it on the plan, PR description, and branch name; write it as
  the introduction a first-time reader sees at the very top of the review page.
- **Write each overview line as "explanation an engineer understands ＝ outcome a non-engineer
  understands"** (＝ is the full-width equals sign U+FF1D).
  The right side states *what happens as a result* in words that make sense to someone who doesn't read
  code (no function or file names), and is rendered on its own line led by an arrow.
  Example: `Consolidate URL building and host checks into resolveAppUrl ＝ URLs are built in one place, so missed updates can no longer cause broken links`
  See "Writing the overview" in schema.md for details.
- Group hunks by **intent** (e.g. rename + related import fixes = 1 group). Not by file.
- Give each group an `intent` (what the change is for) and, if useful, an `impact` (blast radius).
- Give each group an `importance`. This is a reading-order guide for how carefully a human should read
  it — not a verdict on the code:
  - `high`: shared/foundation code where behavior may change; data, auth, or billing
  - `medium`: wide-reaching mechanical changes; UI that contains logic changes
  - `low`: docs, tests only, trivial renames
- Split each group into `sections` — **coherent per-feature units** — and write the explanation
  (`explain`) at this level.
  - Size each section so that "reading this section gives you the whole change for that feature"
    (e.g. "New resolveAppUrl entry point", "Call-site updates", "Test updates").
  - **Do not split by file.** Hunks from the same file may appear in multiple sections/groups
    (hunk IDs and @@ line numbers identify each change).
- Only where line-level notes are needed, add `annotations` to a hunk:
  - `explain`: what the line means / why (put longer explanations in the section's explain)
  - `question`: something to confirm with the human, or a spot whose intent you couldn't determine
- For large numbers of same-shaped mechanical changes, include a representative hunk and note
  "same pattern across N hunks" in the explain.
- **Never critique or propose fixes.** Stick to presenting the facts: what changed, why, and the blast radius.

## 3–4. Generate and launch the UI

1. Write `$REVIEW_DIR/review-data.json` following schema.md.
   Order groups by importance (high → medium → low). Set `repoRoot` to the target repo's absolute path.
   Also write `$REVIEW_DIR/meta.json` for the list view (`/kaisetu-list` reads it instead of opening
   the full diff; it contains only title / tagline / repoRoot / generatedAt — see schema.md).
2. Start the server as a long-running process (the browser opens automatically).
   **Run it with the target repo root as CWD** (the page's plan link serves the plan file via `/plan`,
   so the relative `plan` path must resolve from CWD):
   ```bash
   python3 $SKILL_DIR/scripts/serve.py $REVIEW_DIR/review-data.json
   ```
   In Claude Code use the Bash tool with `run_in_background: true`; in Codex run `exec_command` with a
   short yield time and keep the returned session ID. The URL, result path, and pid are printed on startup.
   If the browser cannot auto-open in your environment, pass `--no-open` and give the printed URL to the user.
   **The server keeps running after "Finish review"** (the user can keep looking at the page).
3. Detect completion asynchronously.
   In Claude Code, run a separate background command that waits for the result file:
   ```bash
   until [ -f $REVIEW_DIR/review-data.result.json ]; do sleep 2; done
   ```
   (`run_in_background: true`. When the user presses "Finish review", the result JSON is written,
   this command exits, and you get a task notification.)
   In Codex, poll the server session with an empty `write_stdin`, or check for the result file on the
   next user turn. Never block on sleep or wait for long periods when no result exists.
4. Tell the user: "The review page is open. When you're done, press 'Finish review' on the page." Then wait.

## 5–6. Ingest results and respond

Comments are **threads** (human comment → AI answer → human reply → …).

1. Read `review-data.result.json`. The `markdown` field contains a human-readable summary.
2. Show the summary to the user and handle the comments (fix or answer).
   Only handle threads with **`awaiting: true`** (unresolved and ending with a human message = needs an answer).
   Skip `resolved: true` (marked "✓ Resolve" on screen) and threads already answered with no new reply.
   Read each thread's `messages` to the end and answer **the most recent human message**.
   - `comments` = notes on diff lines. Fix the code, or explain the reasoning.
   - `docComments` / `groupComments` are usually **comments on prose you wrote** (overview, group
     intent, section explanations). If it says "unclear" or "rewrite this", rewrite the corresponding
     field in `$REVIEW_DIR/review-data.json` and save.
     The server re-reads the file, so **the page swaps in the new explanation within seconds**
     (comments are preserved). See the table "Comments on explanations" in schema.md for which field
     to rewrite. If it's about the code itself, fix or answer as usual.
     Never change `groups[].id` / `sections[].id` / the `hunks` structure (comment anchors would shift).
3. **Write your answers to `$REVIEW_DIR/review-data.replies.json`** (format in schema.md).
   The page polls it every few seconds and shows each answer in its thread as an "AI" message.
   If you fixed code, also write an answer like "Fixed: …".
   **If the file already exists, load it and append to the `replies` arrays** (removing past answers
   removes them from the page).
4. **Leave the server running.** The user reads your answers, continues threads via "Reply", and
   presses "Finish review" again (the result JSON is overwritten).
   Delete the result file and re-run the wait command from step 3–4.3 to detect the next round the same way.
   When the review exchange is fully done, clean up with `kill <pid>` using the pid printed at startup.

## HTML review mode (the target is an HTML file)

For reviewing an HTML file itself — a shared explainer, a report, a generated page.
**Skip steps 1–2 entirely: no diff, no grouping, no explanations.** The human reads the rendered page
and comments on the parts that need changing; you fix the HTML.

1. Create `$REVIEW_DIR` as in step 1 and write `review-data.json` with just these fields:
   ```json
   {
     "title": "Review of the release notes page",
     "html": "docs/release-notes.html",
     "generatedAt": "2026-08-05 10:00",
     "repoRoot": "/Users/me/repos/myapp"
   }
   ```
   `html` is the reviewed file, absolute or relative to the server CWD (= the target repo root).
   Add nothing else — no `groups`, `overview`, `stats`, or explanations.
   Write `meta.json` as usual so `/kaisetu-list` can reopen it.
2. Start the server and set up completion detection exactly as in steps 3–4.
   The page renders the file in an iframe; files next to it (CSS, images, JS) are served too.
3. The human clicks any element to comment on it, or "On the whole page" for a page-wide comment.
   Numbered pins mark commented elements.
4. Read the result JSON's **`elementComments`** and act on each thread with `awaiting: true`:
   - `selector` — CSS selector of the element (`null` means the comment is about the whole page)
   - `label` / `text` — which element it was and the text it contained; use these to find the spot
     in the source
   - `anchored: false` — the element no longer exists (the page changed after the comment was written)
   - Fix the HTML file directly. The server watches it, so the page reloads with your fix within
     seconds and the comments stay anchored.
   - Answer in `$REVIEW_DIR/review-data.replies.json` under `elementComments`
     (`key` = the result's `key`; see schema.md).
5. Threads, "Reply", resolve, and "Finish review" behave exactly as in diff review (steps 5–6).

## Notes

- **If the user asks in chat to rewrite the overview etc., handle it the same way**: rewrite the field in
  `$REVIEW_DIR/review-data.json` and the page rebuilds within seconds (no need to wait for
  "Finish review", no server restart).
- Static HTML only (e.g. to share with another session): `serve.py <data.json> --build out.html`
- The page's "Copy summary" button is for **pasting comments into another session** (e.g. Codex).
  Within this session, use "Finish review".
- Work-in-progress state (comments, resolved flags) is auto-saved to `review-data.state.json`; reopening
  the page restores from the newer of localStorage and state.json (works across browsers via state.json).
- When restarting the server on the same `$REVIEW_DIR`, delete any old `*.result.json` first
  (otherwise completion detection fires immediately).
- Past reviews can be listed and reopened with the `/kaisetu-list` skill.
