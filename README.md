# kaisetu

English | [日本語](README.ja.md)

**A review UI for AI-generated diffs — the AI organizes and explains, the human judges.**

*kaisetu* (解説, Japanese for "commentary") is an agent skill for [Claude Code](https://code.claude.com) and Codex.
Run `/kaisetu` and your coding agent turns a large diff into a local review page:
changes **grouped by intent**, **sorted by risk**, **explained inline** — with a comment system that
sends your feedback straight back into the agent session.

AI agents produce diffs faster than humans can review them. kaisetu doesn't try to review for you —
judging the change is still your job. It removes everything else: figuring out which hunks belong
together, which parts deserve attention first, and what the author (the AI) was trying to do.

```
/kaisetu
  → the agent collects the diff, groups hunks by intent, writes explanations
  → a local server starts and your browser opens
  → you read, and comment on diff lines / group intents / the overview / the AI's explanations
  → "Finish review" → the comments land back in the agent session
  → the agent fixes code or answers; answers appear in the page as threads
  → reply, resubmit, repeat — until you're done
```

## Features

- **Two-audience overview** — every summary line is written as
  *"explanation an engineer understands ＝ outcome a non-engineer understands"*,
  so both readers get it at a glance
- **Groups by intent, not by file** — a rename plus its import fixes is one group; groups are
  displayed in risk order (high → medium → low) so you read the dangerous parts first
- **Inline AI notes** — per-feature explanations at the top of each section, line-level notes and
  *questions* (spots where even the AI couldn't tell the intent) directly on diff lines
- **Comment anything** — hover any diff line, the overview, a group's intent, or an AI explanation
  and press `+`. Comments are auto-saved (localStorage + server-side state)
- **Threaded round-trips** — the agent's answers appear inside the page; press *Reply* to continue
  a thread and *Finish review* to send it back. Unanswered threads are counted in the header
- **Self-rewriting explanations** — comment "this is unclear" on an explanation and the agent rewrites
  it; the page swaps in the new text within seconds, keeping your comments in place
- **Dark mode** — follows your OS, with a manual toggle
- **Zero dependencies** — one HTML template + a Python 3 standard-library server. No npm, no build

## Quick start (demo)

No agent needed — try the UI with the bundled sample data:

```bash
git clone https://github.com/Rasukarusan/kaisetu.git
cd kaisetu
python3 kaisetu/scripts/serve.py kaisetu/example/sample-data.json
```

Your browser opens the review page. Press `?` for keyboard shortcuts.

## Install as a skill

### Claude Code

```bash
git clone https://github.com/Rasukarusan/kaisetu.git
ln -s "$(pwd)/kaisetu/kaisetu" ~/.claude/skills/kaisetu
ln -s "$(pwd)/kaisetu/kaisetu-list" ~/.claude/skills/kaisetu-list
```

Restart Claude Code, then:

```
/kaisetu                    # review uncommitted changes (git diff HEAD)
/kaisetu the whole branch   # diff against the repo's base branch
/kaisetu abc1234            # a single commit
/kaisetu main..HEAD         # any revision range git understands
/kaisetu HEAD~3..HEAD       # e.g. the last 3 commits
/kaisetu-list               # list and reopen past reviews
```

The scope argument is free-form: commit hashes, ranges, branch names, or plain
words — the agent passes whatever revisions you name to `git diff`.

### Codex

Link the same directories into your Codex skills location (e.g. `~/.agents/skills/`) and invoke with
`$kaisetu`. The skill instructions are written to work with either agent.

## How it works

| File | Role |
|---|---|
| `kaisetu/SKILL.md` | The skill itself — how the agent collects, groups, and explains the diff |
| `kaisetu/schema.md` | Spec of `review-data.json`, the only thing the LLM generates |
| `kaisetu/template.html` | The review page (self-contained, no external resources) |
| `kaisetu/scripts/serve.py` | Local server (Python 3 stdlib only); `--build` emits static HTML |
| `kaisetu/example/sample-data.json` | Demo data |
| `kaisetu-list/SKILL.md` | Companion skill: list and reopen past reviews |

The agent writes `review-data.json` (groups → sections → hunks, with explanations) and starts
`serve.py`. The page and the agent communicate through files in `~/.kaisetu/<repo>/<timestamp>/`:

- `review-data.result.json` — written when you press *Finish review*; the agent watches for it
- `review-data.replies.json` — the agent's answers; the page polls and threads them
- `review-data.state.json` — auto-saved comments, so the review survives reloads and other browsers

Because the server re-reads `review-data.json` on every request, the agent can rewrite an explanation
you flagged and the page rebuilds itself — your comments stay anchored to hunk IDs, not to the prose.

Review content is generated in whatever language you converse with your agent in.

## Design principles

- **The human judges; the AI presents.** The skill explicitly forbids the agent from critiquing or
  proposing fixes in the review. It presents facts: what changed, why, blast radius.
- **Risk is a reading order, not a verdict.** high / medium / low tells you where to spend attention.
- **Don't pollute the target repo.** All working files live under `~/.kaisetu/`.
- **Static-friendly.** `serve.py --build` produces a single static HTML you can attach to a PR or
  send to a teammate.

## License

MIT
