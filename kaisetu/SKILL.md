---
name: kaisetu
description: Group a large diff by intent and launch a local review UI, sorted by importance with AI explanations. The human makes the review judgments; comments made on screen come back to the session via "Finish". It also writes explain.html, a self-contained write-up of the branch for the team, shown in the page's Explain tab and commented on the same way. Use explicitly for large diffs or self-review after implementing a plan. Given an .html or .md file instead, it reviews that document itself - rendered in the UI and commented on row by row with a + button, with no grouping or explanations.
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
- **Document review** — the target is a document file itself, `.html` or `.md`. No diff, no grouping,
  no explanations: it is rendered, and the human comments on it row by row with the same `+` button
  they use on a diff line. Use it when the user passes an `.html` or `.md` file, or asks to review a
  rendered page or a written document. See "Document review mode" at the end.

## Overall flow

```
0. Already reviewed on this branch? → ask: reopen it, or start a new one
1. Collect diff → 2. Group + explain → 3. Generate review-data.json → 4. Start serve.py (browser opens)
→ 4.5 Write explain.html while the human reads (it lands in the page's Explain tab)
→ 5. Human comments on screen (diff lines, groups, overview, AI explanations) → "Finish"
→ 6. Read the result JSON and respond (fix code / answer / rewrite explanations)
→ 7. Re-take the diff so the page shows the fixed code
     ↑___ human replies to answers and resubmits (threads); rewritten explanations auto-refresh the page ___|
```

Steps 1–2 are the expensive half and they stay true after the code is fixed, so **the skill is run
once per review**. Everything after that — new answers, rewritten explanations, fixed code — updates
the page that is already open.

## 0. Look for a review of this branch

A review is built for a branch and stays true for as long as that branch is being worked on, so
running the skill again on the same branch is usually a request to go back to it. Before collecting
anything, look:

```bash
python3 $SKILL_DIR/scripts/find_review.py            # run with the target repo as CWD
python3 $SKILL_DIR/scripts/find_review.py --doc docs/spec.md   # document review mode
```

It prints one line per past review of this repository and branch — `<dir>` / `<generatedAt>` /
`open|finished` / `<title>` — newest first, and nothing when there is none. Diff reviews and
document reviews never match each other.

- **Nothing printed** → go to step 1 and build the review.
- **One or more printed** → **ask the user which they want** (AskUserQuestion), naming each
  candidate by its title and time:
  - **Reopen it** — the grouping, the explanations and the comment threads are all still there, and
    the diff is re-taken so the page shows the code as it stands now.
  - **Start a new review** — a fresh `$REVIEW_DIR`; the old one stays and is still reachable from
    `/kaisetu-list`.

  Never pick for the user. Rebuilding silently throws away a reading guide and every comment on it;
  reopening silently ignores a scope they may have meant to change. When the user named a scope the
  existing review does not cover (a different commit or range), say so in the option text.

To reopen, **skip steps 1–2 entirely**:

1. Delete any `review-data.result.json` in that directory (otherwise completion detection fires
   immediately; on-screen comments live in `review-data.state.json`, so nothing is lost).
2. Re-take the diff so the page shows the current code:
   `python3 $SKILL_DIR/scripts/refresh.py <dir>/review-data.json`
   Read what it reports and place any new hunks as described in step 7 — including emptying the
   "Changes made since the review" group. A review written without `scope` cannot be re-taken; it
   can only be read as the snapshot it is.
3. Start the server and set up completion detection as in steps 3–4, then continue from step 5.

## 1. Collect the diff

- Put working files in `~/.kaisetu/<repo-name>/<YYYYMMDD-HHMMSS>/` (never pollute the target repo).
  Create a fresh timestamped directory per review (past reviews are browsed via `/kaisetu-list`, so never overwrite).
  This directory is referred to as `$REVIEW_DIR` below.
- Scope: follow the user's arguments if given. Otherwise use uncommitted changes (`git diff HEAD`).
  For a whole branch, identify the branch this one was forked from **before** taking the diff:
  ```bash
  BASE=$(bash $SKILL_DIR/scripts/base-branch.sh)  # PR base → reflog fork record → remote HEAD → main
  git diff "$BASE"...HEAD
  ```
  If it prints `UNKNOWN` (exit 1), ask the user which branch to diff against instead of guessing.
- Note the command you settled on, **with the base resolved to a real revision** — it goes into
  `scope` in step 3, and is what lets the diff be taken again later without regenerating anything.
  When the scope includes uncommitted work, diff against the merge base so one command covers both:
  `git diff $(git merge-base "$BASE" HEAD)`.
- Save:
  - `diff.patch`: the full diff (`git diff ... > diff.patch`)
  - stats: `git diff --shortstat` and `grep -c '^@@' diff.patch` (files / hunks / +N −N)
- Work out what those lines are made of, so the reader isn't reading a number that overstates the
  change. Take the per-file counts and bucket them by path:
  ```bash
  git diff "$BASE"...HEAD --numstat | sort -rn   # added / deleted / path, biggest first
  ```
  Buckets: `generated` (lock files, schema snapshots, generated clients and openapi) / `test` /
  `code` / `migration` / `infra` (CI, Terraform, task definitions) / `config` / `docs`.
  Note the files and added lines per bucket, and which few files actually carry the intent —
  they become `stats.breakdown` and `stats.core` (see schema.md).

## 2. Group and explain

If a plan exists (`plans/*.md` etc.), read it first so you can explain the intent of the changes accurately.

Organize in 3 levels: **group (unit of intent) > section (unit of explanation) > hunk**.

**The page is a reading guide, not a write-up of the implementation.** A reviewer should be able to
read every word of prose on the page in about two minutes and then go read the diff itself.
Consolidation wins: fewer and larger units, shorter text. A faithful account of every mechanism is
a failure mode here, not thoroughness.

### Structure — keep it consolidated

- **Groups: 4–7, however large the diff is.** A group is one architectural unit of intent — usually a
  service, a layer, or a boundary — **not one mechanism**. A 100-file diff is still 4–7 groups.
  More than 8 means you split by mechanism — merge the groups that serve the same intent.
- **Sections: 1–3 per group.** A section holding 50 hunks is normal and fine. Split a group only when
  it genuinely contains separate stories (e.g. "the endpoint" / "the data it reads" / "wiring and config").
  Never make a section per file, per mechanism, or per edge case.
- **Titles are short, plain noun phrases.** No dash joining two thoughts, no identifiers, no syntax
  fragments: `Browser-level login table`, not `Bundling — the browser_id cookie and the browser_logins table`.

### Length budgets — treat these as hard caps

| Field | Budget |
|---|---|
| `tagline` | 1 sentence |
| `overview` | 3–5 lines, **one point and one sentence per line** |
| `intent` | 1–2 sentences |
| `impact` | 1 sentence naming the areas the change reaches |
| `explain` | 1–3 sentences |
| `annotations[].text` | 1 sentence |

If an explanation won't fit, the unit is too fine-grained — merge it, or drop the detail. Do not
grow the text to fit the material. As calibration: in Japanese an `explain` lands around 50–90
characters, an `intent` around 50–100, an `impact` around 30–60.

### One altitude per level

- `overview` — what the branch does for the product
- group `intent` — what this part of the system now does, and why that part exists
- section `explain` — what this bundle of hunks does, in the breath a colleague would use out loud
- `annotations` — only where one specific line is unreadable without a note

Each level answers "what / why" at its own altitude, and says something the level above didn't.
**Never push implementation detail upward.** A section `explain` is not the place for internal step
order, error handling, retry counts, rejected alternatives, upstream bug links, or the story of how a
behavior was discovered. That belongs in the code and the PR description.

### Plain words

- Name the role, not the identifier: "the long-lived cookie that identifies the browser", not
  "the signed `browser_id` cookie".
- Identifiers, SQL/Redis/HTTP syntax, config keys and constant values never appear in a `title`,
  `intent`, or `overview` line. Put a bare identifier in an `explain` only when the reader has to grep
  for that exact name.
- Keep one register throughout: every `explain` reads like every other one, same tense and sentence
  shape. Uneven length and tone is what makes a page feel unorganized.

Too much — one section, with five more like it in the same group:

> **Deciding the bundle, and the guard that rejects error responses**
> The after hook also runs on error responses, so it first checks statusCode and does nothing at 400 or
> above. Past that point the endpoint itself has already verified the hint's signature, iss and aud, so
> the hook reads sid and sub with `decodeJwt`, without checking the signature. The revocation target is
> the union of the hint's sid and the lineages looked up in the table; with no cookie, or a bad
> signature, it falls back to the sid alone. …

Right — one section covering all of that, and its neighbours:

> **End-session and bulk revocation**
> Validates the end-session request, identifies the authentication session it points at, and deletes the
> product sessions tied to it from Redis. Sends the browser back to an allow-listed URL afterwards.

### Writing the fields

- First write the `tagline`: **one sentence that anyone can read**, shown large at the top.
  No function or file names, no jargon, no `＝` — say what the change means for the product, its users,
  or operations. **It may be slightly imprecise — favor a rough description that conveys the whole
  thing at a glance.**
  Example: `Links to the app and the admin tools are built in one place, so they stop breaking`
- Then write the `overview`: 3–5 bullet points (lines starting with `- `, newline-separated) describing
  what this branch/diff does overall. Base it on the plan, PR description, and branch name; write it as
  the introduction a first-time reader sees at the very top of the review page.
  **One point per line, one sentence per side of the `＝`** — never stack two sentences on a line, and
  keep every line about the same length so the block reads as a set.
- **Write each overview line as "explanation an engineer understands ＝ outcome a non-engineer
  understands"** (＝ is the full-width equals sign U+FF1D).
  The right side states *what happens as a result* in words that make sense to someone who doesn't read
  code (no function or file names), and is rendered on its own line led by an arrow.
  Example: `Consolidate URL building and host checks into resolveAppUrl ＝ URLs are built in one place, so missed updates can no longer cause broken links`
  See "Writing the overview" in schema.md for details.
- Group hunks by **intent** (e.g. rename + related import fixes = 1 group). Not by file.
- Give each group an `intent`: what this part of the system now does, and why it exists. 1–2 sentences.
- Give each group an `impact`: **one sentence naming the areas the change reaches** (which services,
  modules, tables, or environments it spans). It is a map of the territory, not a list of what could
  break — no failure scenarios, no "silently stops working".
- Give each group an `importance`. This is a reading-order guide for how carefully a human should read
  it — not a verdict on the code:
  - `high`: shared/foundation code where behavior may change; data, auth, or billing
  - `medium`: wide-reaching mechanical changes; UI that contains logic changes
  - `low`: docs, tests only, trivial renames
- Split each group into 1–3 `sections` and write the explanation (`explain`) at this level.
  - A section is a **story within the group**, sized so that reading it tells you what that whole bundle
    of hunks does. Related mechanisms, their tests, and their config belong in the same section.
  - **Do not split by file, mechanism, or edge case.** Hunks from the same file may appear in multiple
    sections/groups (hunk IDs and @@ line numbers identify each change).
- Add `annotations` to a hunk **only** where a specific line is unreadable without a note — a handful
  across the whole review, not one per hunk. One sentence each:
  - `explain`: what this line means, when the section's explanation doesn't already cover it
  - `question`: something to confirm with the human, or a spot whose intent you couldn't determine
- For large numbers of same-shaped mechanical changes, include a representative hunk and note
  "same pattern across N hunks" in the explain.
- **Never critique or propose fixes.** Stick to presenting the facts: what changed and why.

### Check before you write the JSON

Read your own prose top to bottom and fix whatever fails:

- 7 or fewer groups? 3 or fewer sections in every group?
- Every `explain` within 3 sentences, and are they all about the same length?
- Any identifier, syntax fragment, or constant in a `title`, `intent`, or `overview` line?
- Any sentence explaining *how* the code is written rather than what it does — step order, error
  handling, why an alternative was rejected? Cut it.
- Does the whole page read in one voice, at a steady altitude?

## 3–4. Generate and launch the UI

1. Write `$REVIEW_DIR/review-data.json` following schema.md.
   Order groups by importance (high → medium → low). Set `repoRoot` to the target repo's absolute path,
   and `scope` to the diff command from step 1 (`{"cmd": "git diff 4f2a1c9...HEAD", "cwd": "<repo root>"}`).
   Without `scope` the diff can never be taken again, and the whole review has to be regenerated to
   see a one-line fix — so write it every time.
   Set `branch` to the branch the diff was taken on (`git rev-parse --abbrev-ref HEAD`).
   Set `explain` to `"explain.html"` — the write-up you produce in step 4.5. **Write it now, before
   the file exists**: that is what puts the pending Explain tab on the page, so the reader knows it
   is coming.
   Also write `$REVIEW_DIR/meta.json` for the list view (`/kaisetu-list` reads it instead of opening
   the full diff; it contains only title / tagline / branch / repoRoot / generatedAt — see schema.md).
   **`branch` is what step 0 matches on**, so a review written without it can never be found again
   from the branch it belongs to.
2. Start the server as a long-running process (the browser opens automatically).
   **Run it with the target repo root as CWD** (the page's plan link serves the plan file via `/plan`,
   so the relative `plan` path must resolve from CWD):
   ```bash
   python3 $SKILL_DIR/scripts/serve.py $REVIEW_DIR/review-data.json
   ```
   In Claude Code use the Bash tool with `run_in_background: true`; in Codex run `exec_command` with a
   short yield time and keep the returned session ID. The URL, result path, and pid are printed on startup.
   If the browser cannot auto-open in your environment, pass `--no-open` and give the printed URL to the user.
   **The server keeps running after "Finish"** (the user can keep looking at the page).
3. Detect completion asynchronously.
   In Claude Code, run a separate background command that waits for the result file:
   ```bash
   until [ -f $REVIEW_DIR/review-data.result.json ]; do sleep 2; done
   ```
   (`run_in_background: true`. When the user presses "Finish", the result JSON is written,
   this command exits, and you get a task notification.)
   In Codex, poll the server session with an empty `write_stdin`, or check for the result file on the
   next user turn. Never block on sleep or wait for long periods when no result exists.
4. Tell the user: "The review page is open. When you're done, press 'Finish' on the page."

## 4.5. Write the write-up for the team

The same branch has a second reader: the teammate who will never open the diff. They get
`$REVIEW_DIR/explain.html` — one self-contained page, with figures and a cast, reachable from the
**Explain** tab in the header and openable on its own to send on.

**Write it now, right after the page opens** — the human is already reading the diff, so the write-up
costs them no waiting. The page picks the file up within seconds of it landing: the tab stops being
pending and says so.

Follow `$SKILL_DIR/explain.md`. It is built from the understanding you already have — the overview,
the group intents and the section explanations at a different altitude — not from another pass over
the code.

Then tell the user in one line that the write-up is on the Explain tab, with its path.

## 5–7. Ingest results, respond, and re-take the diff

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
     Never change `groups[].id` / `sections[].id` / a hunk's `id` or `diff` — comments hang off a hunk
     ID and a line number, so editing either by hand moves someone's comment onto a different line.
     Moving a whole hunk entry to another section is safe: its ID and its body travel with it.
   - `elementComments` in a diff review are **comments on the write-up** (the result's `explain` says
     which file). Fix `$REVIEW_DIR/explain.html` directly — the page reloads the Explain tab within
     seconds and the comments stay anchored. Answer under `elementComments` in replies.json.
3. **Write your answers to `$REVIEW_DIR/review-data.replies.json`** (format in schema.md).
   The page polls it every few seconds and shows each answer in its thread as an "AI" message.
   If you fixed code, also write an answer like "Fixed: …".
   **If the file already exists, load it and append to the `replies` arrays** (removing past answers
   removes them from the page).
4. **When you changed code, re-take the diff** so the page stops showing the version you just fixed:
   ```bash
   python3 $SKILL_DIR/scripts/refresh.py $REVIEW_DIR/review-data.json
   ```
   The groups, the explanations and the comment threads all stay as they are; only the hunk bodies
   catch up with the working tree, every hunk that moved is badged "updated", and the page reloads
   within seconds. **Never re-run this skill to show a fix** — that throws away the reading guide and
   the review the human is in the middle of. (The human can press "Refresh" in the header to do
   the same thing whenever they have edited something themselves.)
   Read what it reports. New hunks mostly place themselves, next to the file or the directory they
   belong with; check that the section they landed in still reads true and extend its `explain` if
   the change added something the story does not cover. Anything with no neighbour on the page —
   a new app, a new top-level file — is waiting in a group at the top called "Changes made since the
   review". **Never leave that group standing**: move each hunk into the section it belongs to and
   write what the reader needs, leaving the rest of the review untouched. The group disappears once
   it is empty. A hunk keeps its ID and body when it moves, so comments stay anchored.
5. **Leave the server running.** The user reads your answers, continues threads via "Reply", and
   presses "Finish" again (the result JSON is overwritten).
   Delete the result file and re-run the wait command from step 3–4.3 to detect the next round the same way.
   When the review exchange is fully done, clean up with `kill <pid>` using the pid printed at startup.

## Document review mode (the target is an HTML or Markdown file)

For reviewing a document itself — a shared explainer, a report, a generated page, a spec or design
doc written in Markdown.
**Skip steps 1–2 entirely: no diff, no grouping, no explanations.** The human reads the rendered
document and comments on the parts that need changing; you fix the source file.

Step 0 still applies, with the reviewed file passed along
(`python3 $SKILL_DIR/scripts/find_review.py --doc docs/release-notes.md`): a document reviewed once
already on this branch is reopened rather than filed again.

1. Create `$REVIEW_DIR` as in step 1 and write `review-data.json` with just these fields:
   ```json
   {
     "title": "Review of the release notes",
     "doc": "docs/release-notes.md",
     "branch": "release-notes",
     "generatedAt": "2026-08-05 10:00",
     "repoRoot": "/Users/me/repos/myapp"
   }
   ```
   `doc` is the reviewed file, absolute or relative to the server CWD (= the target repo root).
   `.md` is rendered to HTML by the server; `.html` is shown as it is.
   Add nothing else — no `groups`, `overview`, `stats`, or explanations.
   Write `meta.json` as usual, `doc` and `branch` included, so `/kaisetu-list` can reopen it and
   step 0 can find it.
2. Start the server and set up completion detection exactly as in steps 3–4.
   The page renders the document in an iframe; files next to it (images, CSS, JS, other `.md`) are
   served too, so relative links work.
3. Commenting works like it does on a diff line: the human hovers a row — a paragraph, heading,
   list item, table row, code block — and presses the `+` that appears in its gutter. A commented
   row keeps a numbered pin in place of its `+`. "+ Comment on the whole document" above the
   document covers the document as a whole.
4. Read the result JSON's **`elementComments`** and act on each thread with `awaiting: true`:
   - `selector` — CSS selector of the row (`null` means the comment is about the whole document).
     For Markdown, headings carry an id, so a selector like `#open-questions` points straight at
     the heading whose section the comment belongs to
   - `label` / `text` — which element it was and the text it contained; use these to find the spot
     in the source
   - `anchored: false` — the element no longer exists (the document changed after the comment was
     written)
   - Fix the source file directly. The server watches it, so the page reloads with your fix within
     seconds and the comments stay anchored.
   - Answer in `$REVIEW_DIR/review-data.replies.json` under `elementComments`
     (`key` = the result's `key`; see schema.md).
5. Threads, "Reply", resolve, and "Finish" behave exactly as in diff review (steps 5–6).

## Notes

- The write-up is a file like any other: rewrite `$REVIEW_DIR/explain.html` whenever, and the Explain
  tab follows within seconds. When a fix to the code makes something in it untrue, fix it there too —
  that page is what the team reads instead of the diff.
- **If the user asks in chat to rewrite the overview etc., handle it the same way**: rewrite the field in
  `$REVIEW_DIR/review-data.json` and the page rebuilds within seconds (no need to wait for
  "Finish", no server restart).
- The same goes for code: after any edit to the target repo — answering a comment, or work the user
  asked for in chat — run `scripts/refresh.py` so the open page shows what the code says now.
- Static HTML only (e.g. to share with another session): `serve.py <data.json> --build out.html`
- The page's "Copy summary" button is for **pasting comments into another session** (e.g. Codex).
  Within this session, use "Finish".
- Work-in-progress state (comments, resolved flags) is auto-saved to `review-data.state.json`; reopening
  the page restores from the newer of localStorage and state.json (works across browsers via state.json).
- When restarting the server on the same `$REVIEW_DIR`, delete any old `*.result.json` first
  (otherwise completion detection fires immediately).
- Past reviews can be listed and reopened with the `/kaisetu-list` skill.
