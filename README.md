# kaisetu - How I scrolled past green and red and called it a review

English | [日本語](README.ja.md)


https://github.com/user-attachments/assets/d9aa9e8a-78bb-4940-b91a-99abae4b015e


**A review UI that reshapes AI-generated diffs into something a human can actually read.**

**[Try the demo in your browser](https://rasukarusan.github.io/kaisetu/sample-kidoku.html)** — a real 23-file review, no install.

A confession first: I wasn't really reading my AI's diffs. Open a 23-file diff and you quietly
close the tab. Scroll past the green and red, call it "reviewed", approve with a "probably fine".
And before the review is even done, the AI has the next diff ready.

Where to start reading, which changes belong together, what the author was trying to do.
A human PR comes with an author who fills that in, even verbally. An AI diff doesn't.

*kaisetu* (解説, Japanese for "commentary") is an agent skill for
[Claude Code](https://code.claude.com) and Codex that fills that gap. Run `/kaisetu` and your
coding agent turns a large diff into a local review page: changes **grouped by intent**,
**sorted by importance**, **explained inline**, with comments on the page going straight back
into the agent session.

I built kaisetu to make this self-review easier. I wanted to read my own AI-written diffs with
the same calm I bring to a teammate's PR. I've stopped reading diffs top to bottom in file order.

<img width="715" alt="Terminal English-selection" src="https://github.com/user-attachments/assets/ee2cf175-e408-45e4-a57d-3f8d051ae851" />

## Three features that make self-review easier

- Wondering "where do I even start reading?" → **changes come grouped**
- Squinting at a hunk thinking "so what is this trying to do?" → **there's a one-line explanation**
- Piling up "I'll ask about this later" notes → **ask the AI right there**


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
/kaisetu docs/report.html   # review the rendered HTML page itself
/kaisetu-list               # list and reopen past reviews
```

The scope argument is free-form: commit hashes, ranges, branch names, or plain
words — the agent passes whatever revisions you name to `git diff`.
Name an `.html` file instead and it switches to HTML review: the page is rendered in an iframe and you
comment element by element, with numbered pins marking what you flagged.

### Codex

Link the same directories into your Codex skills location (e.g. `~/.agents/skills/`) and invoke with
`$kaisetu`. The skill instructions are written to work with either agent.

## License

MIT
