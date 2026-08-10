# The write-up (explain.html)

The review page is for the person reading the diff. The write-up is for everyone else: the engineer
who never opened this branch, and the non-engineer who never will. One self-contained HTML file,
built from the same understanding as the review, sitting behind the page's **Explain** tab.

Write it **after the review page is open** — the human is already reading, so nothing waits on it.
`$SKILL_DIR/explain-template.html` holds the CSS and a specimen of every part; take the CSS as it
is, keep the parts you use, replace the content. Save the result as `$REVIEW_DIR/explain.html`.

Write it in the language the review is written in, and set `<html lang>` to match.

## Never

- **No external resources.** CSS inline, figures as SVG, system fonts. One file, or it cannot be sent.
- **No dark mode.** No `prefers-color-scheme`, no `data-theme` — `color-scheme: light` and done.
- **No table or flow explained without a figure.** A section of prose and a table alone reads as a
  block of something the reader can't place.
- **Nothing about the review itself.** No comments, no importance, no hunks. The reader is a
  teammate being told what the branch does, not a reviewer.

## Where the material comes from

You have just read the whole diff to build the review, so **build the write-up from that**, not from
another pass over the code. The review's `overview`, group `intent`s and section `explain`s are the
same understanding at a lower resolution; the write-up is where the figures, the cast and the reasons
go. Read the plan, the PR description and the commit bodies for the *why* — design reasoning is
densest in commit messages, and the review page deliberately has no room for it.

Numbers (diff size, test counts) go in only when you checked them just now.

## Structure — biggest story first

The reader reads top to bottom. The further a change reaches, the higher it goes.

1. **Header + overview** — three lines; the most-read part of the page
2. **Cast** — who appears in this story
3. **Data model changes** — a changed shape outranks everything else
4. **Infrastructure and environment changes** — what running it now involves
5. **Design decisions** — why it went this way
6. **How it runs** — the actual movement
7. **Mechanisms that need explaining** — concurrency, failure behavior; anything unreadable without
   the premise
8. **New libraries** — **only when an external package was added.** Not your own modules, not
   wider use of a library that was already there. No additions, no section.

Drop what you have nothing for. **Use these names as the headings** — anything you want to add
belongs in the section's first sentence, not in its heading.

## How it is written

The write-up is not a record of the implementation. Depth comes from the figures and from real
data; the prose stays thin and evenly sized.

- **Headings are short noun phrases.** No `—` or `:` joining two claims, no identifiers.
  `Data model changes`, not `DB changes — holding which browser the session belongs to`.
- **One claim per paragraph, 120 characters.** Past three sentences, split it or turn it into a
  figure or a table.
- **Four paragraphs is a section's limit.** More than that, cut with an `h3`; if it won't cut, the
  section is holding two stories.
- **Keep paragraphs the same length.** A 250-character block next to a one-line paragraph tells the
  reader nothing about where to look.
- **Reasons live in "Design decisions".** No "why it was written this way", no "we could have done X",
  no "this bit us in E2E" anywhere else. Every other section says only what happens.
- **Name the role, not the identifier.** Function, table and environment-variable names appear only
  where the reader has to grep for exactly that name. A few `<code>` per section at most.
- **Define a term once in plain words and then keep calling it that.** One voice throughout.

### The overview reads "technical ＝ what it means"

```html
<li>
  [technical: one sentence. One name (table, function, file) is allowed]
  <span class="mean">[what changed for the people using or running it]</span>
</li>
```

The technical half is grey, the half after `＝` is bold on its own line — so the reader can skip the
left side and still follow. **One claim per line, one sentence per side**, six lines at most, all
about the same length.

The right side is what changed *for the person on the other side of the screen*, never a restatement
of the left: "anyone could call it before", "you no longer get logged out when two tabs move at once",
"it takes effect the moment the setting is saved". Put a number in when you have one — a behavioral
change only means something once its size is known.

### The cast separates leads from the rest

- **Leads** (what this branch really changed): blue, large, with a dotted "this branch" line at the
  bottom of the card, also written as `＝`. Three or so — more and nothing reads as the thing to
  hold on to.
- **Supporting** (unchanged, or merely used more): grey, small.

### Choose the figure before writing the section

If you can't think of a figure, the section is at the wrong grain.

| To show | Figure |
|---|---|
| Two conditions overlapping | Venn |
| Tables and their relationships | ER — **new in color, existing in grey, with a legend** |
| What the data means | Three mini tables side by side (two inputs → one result), with real seed values |
| Flow between services | Sequence diagram — lifelines, numbered messages, notes |
| Concurrency and races | Two-lane timeline, **before (it breaks) above, after (it doesn't) below** |
| The approach changed | Before / after comparison |
| The final output | JSON code block, with the lines that matter colored |

**A data model needs the ER diagram and the real data both.** The table definition alone never says
what the table is for: the ER diagram shows where it hangs, the real data shows who can then do what,
and the API response or screen closes it.

### Writing the SVGs

- Define the `<defs>` marker **per SVG** and give each figure its own id (`#arrow` / `#k-arrow`)
- Never write `svg text { font-size: … }` in CSS — **it beats the `font-size` attribute** and
  flattens every per-element size. Put it on a shared class instead (`.box-label`)
- Text inside a circle or a box: place it by how far it spreads left and right, not by its anchor
- Wrap a wide figure in `<div class="scroll">` so the page itself never scrolls sideways

## Read it through before calling it done

- Any `—` or identifier left in a heading?
- Any paragraph past 120 characters, any section past four paragraphs?
- Is the overview one claim per line, with the lines about the same length?
- Has "why it was built this way" leaked out of the design-decisions section?
- Too many `<code>` in the prose — anything that could be said as a role instead?
- Read top to bottom: one voice, one altitude?
