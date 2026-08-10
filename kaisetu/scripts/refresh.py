#!/usr/bin/env python3
"""Re-take the diff of a review that is already open.

The review page holds two very different things. The groups, sections and explanations are what
the agent spent its thinking on, and they stay true after a line is fixed. The hunk bodies are a
photograph of the working tree, and they go stale the moment anything is edited. Re-running the
whole skill throws the first away to renew the second.

This script renews only the second. It re-runs the diff command recorded in `scope`, matches the
new hunks against the ones already in the review, and writes the new bodies back in place —
keeping every ID, so the comments hanging off them stay where they belong. Comments sitting on a
line that was rewritten move onto the rewrite; hunks that no longer exist are dropped, unless they
carry a comment, in which case they stay marked as gone so the thread still has its subject.

review-data.json is rewritten in place, so a running serve.py notices within seconds and the page
reloads by itself. Nothing has to be restarted and no explanation is regenerated.

Usage:
  refresh.py <review-data.json>

Dependencies: Python 3 standard library only.
"""
import argparse
import datetime
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from collections import defaultdict

# How alike two hunk bodies must be to count as the same change, edited. Below this they are
# treated as one hunk having vanished and another having appeared.
MATCH_THRESHOLD = 0.45

# How much of a line has to survive a rewrite for a comment on it to still be about it. Below this
# the replacement is simply a different line, and the comment is told its subject is gone.
LINE_SURVIVES = 0.5

# How many leading directories a new file must share with one already on the page to join its
# section. One is meaningless — every file under `apps/` shares that much.
MIN_SHARED_DIRS = 2


class Refused(Exception):
    """The refresh cannot be done, for a reason worth telling the caller about."""


# ---------- patch parsing ----------

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
C_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


def _unquote(path: str) -> str:
    """git's quoted path form → the real name.

    A path with non-ASCII bytes comes out as `"a/\\350\\250\\255.md"` — C escapes over raw UTF-8
    bytes, not the \\uXXXX that a JSON decoder expects. Decoding it as anything but bytes gives a
    different name, and a different name loses the file's whole place in the review.
    """
    body, out, i = path[1:-1], bytearray(), 0
    while i < len(body):
        char = body[i]
        if char == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt.isdigit() and len(body) >= i + 4:
                try:
                    out.append(int(body[i + 1:i + 4], 8))
                    i += 4
                    continue
                except ValueError:
                    pass
            if nxt in C_ESCAPES:
                out.append(C_ESCAPES[nxt])
                i += 2
                continue
        out.extend(char.encode("utf-8"))
        i += 1
    return out.decode("utf-8", "replace")


def _strip_prefix(path: str) -> str:
    """`a/src/app.ts` → `src/app.ts`, including git's quoted form for non-ASCII names."""
    path = path.split("\t")[0]
    if len(path) > 1 and path.startswith('"') and path.endswith('"'):
        path = _unquote(path)
    return re.sub(r"^[ab]/", "", path)


def parse_patch(text: str):
    """Unified diff → (hunks, files touched).

    A hunk is `{"file", "header", "body"}`, body being the lines under the @@ header exactly as
    git wrote them — the same shape the review data stores in `diff`.

    The body's extent comes from the counts in the @@ header, never from what the lines look like.
    Deleting a SQL or Lua comment puts `--- keep ids stable` in the body, which is indistinguishable
    from a file header by eye; trusting the shape there truncates the hunk and loses the review of it.
    """
    hunks, files, path, cur = [], [], None, None
    old_left = new_left = 0
    for line in text.rstrip("\n").split("\n"):
        if cur is not None:
            kind = line[:1]
            if kind == "\\":                            # "\ No newline at end of file": counts nothing
                cur["body"].append(line)
                continue
            if (kind == "-" and old_left) or (kind == "+" and new_left) or (
                    kind in (" ", "") and old_left and new_left):
                cur["body"].append(line)
                old_left -= kind != "+"
                new_left -= kind != "-"
                continue
            cur = None                                  # counts spent: this line belongs to the patch again
        if line.startswith("diff --git "):
            path = None
        elif line.startswith("--- "):
            old = line[4:]
            path = None if old == "/dev/null" else _strip_prefix(old)
            if path:
                files.append(path)
        elif line.startswith("+++ "):
            new = line[4:]
            if new != "/dev/null":                      # /dev/null = the file was deleted
                if path in files:
                    files.remove(path)
                path = _strip_prefix(new)
                files.append(path)
        elif line.startswith("@@"):
            counts = HUNK_HEADER.match(line)
            if counts:
                old_left = int(counts.group(1) or 1)
                new_left = int(counts.group(2) or 1)
                cur = {"file": path or "?", "header": line, "body": []}
                hunks.append(cur)
    return [h for h in hunks if h["body"]], sorted(set(files))


def split_diff(text: str):
    """A stored `diff` string → (@@ header, body lines). The page splits it the same way."""
    lines = str(text or "").rstrip("\n").split("\n")
    if lines and lines[0].startswith("@@"):
        return lines[0], lines[1:]
    return "", lines


def join_diff(header: str, body) -> str:
    return "\n".join([header, *body]) if header else "\n".join(body)


# ---------- matching ----------

def match_hunks(olds, news):
    """Pair up hunks of one file. → {index in olds: index in news}

    Untouched hunks match on their body exactly; an edited one is found by similarity, preferring
    the pair that also sits at a similar place in the file.
    """
    pairs, used = {}, set()
    by_body = defaultdict(list)
    for j, n in enumerate(news):
        by_body["\n".join(n["body"])].append(j)
    for i, o in enumerate(olds):
        queue = by_body.get("\n".join(o["body"]))
        while queue:
            j = queue.pop(0)
            if j not in used:
                pairs[i] = j
                used.add(j)
                break

    candidates = []
    for i, o in enumerate(olds):
        if i in pairs:
            continue
        for j, n in enumerate(news):
            if j in used:
                continue
            sm = difflib.SequenceMatcher(None, o["body"], n["body"], autojunk=False)
            if sm.quick_ratio() < MATCH_THRESHOLD:
                continue
            ratio = sm.ratio()
            if ratio >= MATCH_THRESHOLD:
                candidates.append((ratio, -abs(i - j), i, j))
    for _, _, i, j in sorted(candidates, reverse=True):
        if i not in pairs and j not in used:
            pairs[i] = j
            used.add(j)
    return pairs


NEW_GROUP_ID = "g-new"       # the catch-all group new hunks land in until the agent places them


def row_map(old_body, new_body):
    """Where each row of the old hunk body ended up in the new one. → {old index: new index}

    → (mapping, rows that no longer exist)

    A row that survived keeps its line. A rewritten one points at the line that replaced it — the
    closest of the replacements, so a comment lands on the fix it was asking for rather than on
    whatever happens to come first. A row that was simply taken away has no honest home: it still
    gets a position, near where it used to be, but it comes back in the second value so whatever
    was anchored there can say out loud that its line is gone.
    """
    mapping, lost = {}, set()
    if not new_body:
        return mapping, lost
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, old_body, new_body, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mapping[i1 + k] = j1 + k
        elif tag == "replace":
            for i in range(i1, i2):
                scored = [(difflib.SequenceMatcher(None, old_body[i], new_body[j],
                                                   autojunk=False).ratio(), j)
                          for j in range(j1, j2)]
                best, mapping[i] = max(scored)
                if best < LINE_SURVIVES:
                    # Nothing here resembles the old line: the replacement is a different line,
                    # not a rewrite of this one, so whatever was anchored here has lost its subject
                    lost.add(i)
        elif tag == "delete":
            for i in range(i1, i2):
                mapping[i] = min(j1, len(new_body) - 1)
                lost.add(i)
    return mapping, lost


# ---------- the review tree ----------

def move_annotations(hunk, new_body, rows, lost):
    """Keep the notes that still have a line to sit on, and drop the ones that do not.

    A note anchored to text the fix removed has nothing left to explain, whichever way it was
    anchored. Keeping it would silently restick it to some other line, and a wrong explanation
    reads exactly like a right one.
    """
    kept = []
    for ann in hunk.get("annotations") or []:
        anchor = ann.get("match")
        if anchor:
            if any(anchor in line[1:] for line in new_body if not line.startswith("\\")):
                kept.append(ann)
            continue
        line = ann.get("line")
        if isinstance(line, int) and line >= 1:
            if line - 1 in lost or rows.get(line - 1) is None:
                continue
            ann["line"] = rows[line - 1] + 1
        kept.append(ann)
    if kept:
        hunk["annotations"] = kept
    else:
        hunk.pop("annotations", None)


def iter_sections(data):
    """(group, section) for every section, including the flat `group.hunks` shape."""
    for group in data.get("groups") or []:
        sections = group.get("sections")
        if sections is None:
            sections = [group] if group.get("hunks") is not None else []
        for section in sections:
            yield group, section


def next_id_maker(existing):
    """Hand out h-IDs that continue the ones already used, at the same width."""
    width, highest = 3, 0
    for hid in existing:
        m = re.fullmatch(r"h(\d+)", str(hid or ""))
        if m:
            highest = max(highest, int(m.group(1)))
            width = max(width, len(m.group(1)))
    counter = {"n": highest}

    def make():
        counter["n"] += 1
        return "h" + str(counter["n"]).zfill(width)
    return make


def is_japanese(data) -> bool:
    if data.get("lang"):
        return data["lang"].startswith("ja")
    text = " ".join(str(data.get(k) or "") for k in ("title", "tagline", "overview"))
    return bool(re.search(r"[ぁ-んァ-ン一-龯]", text))


# ---------- comment keys ----------

def _line_keys(*stores):
    keys = set()
    for store in stores:
        keys |= set((store or {}).keys())
    return keys


def build_key_map(keys, row_maps, row_counts):
    """Old `hunkId:row` comment keys → where they point after the refresh.

    Keys on a hunk that was not re-matched are left alone (the hunk is kept as it was). Two threads
    cannot share a line, so a collision moves the later one **down** the hunk, never up: reading
    order is what tells the human which comment was about what, and reversing it is worse than
    sitting a line off. A hunk that shrank below the number of comments on it lets the last ones
    keep an index past its end, where the page collects them under the diff rather than losing them.
    """
    by_hunk = defaultdict(list)
    for key in keys:
        cut = key.rfind(":")
        if cut < 0:
            continue
        hid, idx = key[:cut], key[cut + 1:]
        if idx.isdigit():
            by_hunk[hid].append(int(idx))

    mapping = {}
    for hid, indexes in by_hunk.items():
        rows = row_maps.get(hid)
        if rows is None:                      # unmatched hunk: its body is untouched, so are its keys
            continue
        limit, previous = max(0, row_counts.get(hid, 1) - 1), -1
        for idx in sorted(indexes):
            target = max(rows.get(idx, min(idx, limit)), previous + 1)
            previous = target
            if target != idx:
                mapping[f"{hid}:{idx}"] = f"{hid}:{target}"
    return mapping


def _detached_notes(keys, lost_rows, key_map) -> dict:
    """Threads whose line the fix removed → the line they were written on, under their new key."""
    notes = {}
    for key in keys:
        cut = key.rfind(":")
        if cut < 0 or not key[cut + 1:].isdigit():
            continue
        was = lost_rows.get(key[:cut], {}).get(int(key[cut + 1:]))
        if was is not None:
            notes[key_map.get(key, key)] = was
    return notes


def apply_key_map(store, mapping):
    """Rename the keys of one `{key: value}` comment store in place."""
    if not store:
        return
    moved = {k: store.pop(k) for k in list(store) if k in mapping}
    for old, value in moved.items():
        store[mapping[old]] = value


# ---------- the refresh itself ----------

def run_diff(scope):
    cmd = scope.get("cmd")
    if not cmd:
        raise Refused("scope.cmd is not set in the review data — nothing to re-run")
    cwd = scope.get("cwd") or scope.get("repoRoot")
    if not cwd or not pathlib.Path(cwd).is_dir():
        raise Refused(f"scope.cwd is not a directory: {cwd}")
    done = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused(f"the diff command failed: {done.stderr.strip() or done.returncode}")
    return done.stdout


def refresh(data_path) -> dict:
    """Re-take the diff and write it back into review-data.json. → a summary of what moved."""
    data_path = pathlib.Path(data_path).resolve()
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if data.get("doc"):
        raise Refused("this is a document review — the server already follows the file itself")

    scope = dict(data.get("scope") or {})
    scope.setdefault("repoRoot", data.get("repoRoot"))
    new_hunks, files = parse_patch(run_diff(scope))

    old_by_file = defaultdict(list)
    for _, section in iter_sections(data):
        for h in section.get("hunks") or []:
            header, body = split_diff(h.get("diff"))
            old_by_file[h.get("file")].append({"section": section, "hunk": h,
                                               "header": header, "body": body})
    new_by_file = defaultdict(list)
    for h in new_hunks:
        new_by_file[h["file"]].append(h)

    # Which comments exist, so a vanished hunk that carries one can be kept as its subject
    state_path = data_path.with_suffix(".state.json")
    replies_path = data_path.with_suffix(".replies.json")
    state = _read_json(state_path) or {}
    replies = _read_json(replies_path) or {}
    commented = {k[:k.rfind(":")] for k in _line_keys(
        state.get("comments"), state.get("resolved"), state.get("commentSides")) if ":" in k}
    commented |= {c["key"][:c["key"].rfind(":")] for c in replies.get("comments") or []
                  if isinstance(c, dict) and ":" in str(c.get("key", ""))}

    # IDs are handed out from what the review started with, so dropping the highest-numbered hunk
    # never lets a newcomer inherit its ID — and with it, its comments
    make_id = next_id_maker([e["hunk"].get("id") for olds in old_by_file.values() for e in olds])

    row_maps, row_counts, updated, unchanged, gone = {}, {}, 0, 0, []
    lost_rows, placed = {}, set()

    for file, olds in old_by_file.items():
        news = new_by_file.get(file, [])
        pairs = match_hunks(olds, news)
        for i, old in enumerate(olds):
            hunk, hid = old["hunk"], old["hunk"].get("id")
            j = pairs.get(i)
            if j is None:
                gone.append(old)
                continue
            new = news[j]
            placed.add(id(new))
            rows, lost = row_map(old["body"], new["body"])
            row_maps[hid], row_counts[hid] = rows, len(new["body"])
            lost_rows[hid] = {i: old["body"][i] for i in lost}
            hunk.pop("gone", None)
            if new["body"] == old["body"] and new["header"] == old["header"]:
                hunk.pop("updated", None)
                unchanged += 1
            else:
                hunk["diff"] = join_diff(new["header"], new["body"])
                hunk["updated"] = True
                move_annotations(hunk, new["body"], rows, lost)
                updated += 1

    # A hunk that is no longer in the diff goes away, unless a comment is still pointing at it
    dropped = 0
    for old in gone:
        hunk = old["hunk"]
        if hunk.get("id") in commented:
            hunk["gone"] = True
            hunk.pop("updated", None)
        else:
            old["section"]["hunks"].remove(hunk)
            dropped += 1

    added = _place_new_hunks(data, [h for h in new_hunks if id(h) not in placed], make_id)
    # Once the agent has folded the newcomers into real sections, the catch-all has nothing to hold
    data["groups"] = [g for g in data.get("groups") or []
                      if g.get("id") != NEW_GROUP_ID
                      or any(s.get("hunks") for s in g.get("sections") or [])]

    # Comment anchors follow the lines they were written on
    keys = _line_keys(state.get("comments"), state.get("resolved"), state.get("commentSides"))
    key_map = build_key_map(keys, row_maps, row_counts)
    detached = _detached_notes(keys, lost_rows, key_map)
    if state and (key_map or detached != (state.get("detached") or {})):
        for store in ("comments", "resolved", "commentSides", "detached"):
            apply_key_map(state.get(store), key_map)
        for entry in replies.get("comments") or []:
            if isinstance(entry, dict) and entry.get("key") in key_map:
                entry["key"] = key_map[entry["key"]]
        # A thread whose line was taken away says so on the page instead of quietly pointing at
        # whatever moved into its place
        state["detached"] = {**(state.get("detached") or {}), **detached}
        for key in list(state["detached"]):
            hid = key[:key.rfind(":")] if ":" in key else ""
            if hid in row_maps and key not in detached:
                del state["detached"][key]          # this one found its line again
        # The page restores from whichever of localStorage and state.json is the later revision;
        # the browser still holds the anchors from before the fix, so mark this pass as the newer.
        state["_rev"] = int(state.get("_rev") or 0) + 1
        state["_savedAt"] = int(time.time() * 1000)
        _write_json(state_path, state)
        if replies and key_map:
            _write_json(replies_path, replies)

    stats = data.setdefault("stats", {})
    stats["files"] = len(files)
    stats["hunks"] = len(new_hunks)
    stats["additions"] = sum(1 for h in new_hunks for l in h["body"] if l.startswith("+"))
    stats["deletions"] = sum(1 for h in new_hunks for l in h["body"] if l.startswith("-"))
    data["refreshedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    _write_json(data_path, data)

    return {"updated": updated, "unchanged": unchanged, "added": added,
            "gone": len(gone) - dropped, "dropped": dropped,
            "message": (f"{updated} updated / {added} new / {len(gone)} no longer in the diff "
                        f"({unchanged} unchanged)")}


def _dir_parts(path: str) -> tuple:
    return tuple(str(path or "").split("/")[:-1])


def _shared(a: tuple, b: tuple) -> int:
    """How many leading directories two paths have in common."""
    count = 0
    for one, other in zip(a, b):
        if one != other:
            break
        count += 1
    return count


def _home_for(path, order, owners, dirs):
    """The section a new file belongs with, or None if nothing on the page is near it.

    A file some section already covers goes back to that section. A brand new file goes to whoever
    already reads that part of the tree: a new file under `libs/bff-kit/src` belongs to the story
    about `libs/bff-kit/src`, not to a pile of its own.

    The same directory always counts as near, however shallow it is — a repo whose code sits in
    `src/`, or at the root, has no deeper path to share. Short of that, two paths must share more
    than their top directory: everything in a monorepo shares `apps` or `libs`, and that says
    nothing about belonging together.
    """
    owner = owners.get(path)
    if owner:
        return max(owner, key=owner.get)
    want, best, best_score = _dir_parts(path), None, None
    for section in order:
        for directory, count in dirs[id(section)].items():
            shared = _shared(want, directory)
            if directory != want and shared < MIN_SHARED_DIRS:
                continue
            score = (directory == want, shared, count)
            if best_score is None or score > best_score:
                best, best_score = id(section), score
    return best


def _place_new_hunks(data, fresh, make_id) -> int:
    """File hunks that appeared since the review was written into the review tree.

    Most of them have a home already: the section covering that file, or failing that the section
    covering the part of the tree the file sits in. Only a file with no neighbour on the page has no
    explanation to belong to, and that one goes to a group of its own at the top of the reading
    order, where the agent can see it and fold it in.
    """
    if not fresh:
        return 0
    order = [section for _, section in iter_sections(data)]
    owners = defaultdict(lambda: defaultdict(int))     # file → section → how many hunks it holds
    dirs = {}                                          # section → directory → how many hunks it holds
    for section in order:
        counts = defaultdict(int)
        for h in section.get("hunks") or []:
            owners[h.get("file")][id(section)] += 1
            counts[_dir_parts(h.get("file"))] += 1
        dirs[id(section)] = counts
    sections_by_id = {id(s): s for s in order}

    unplaced = []
    for hunk in fresh:
        entry = {"id": make_id(), "file": hunk["file"],
                 "diff": join_diff(hunk["header"], hunk["body"]), "updated": True}
        home = _home_for(hunk["file"], order, owners, dirs)
        if home is None:
            unplaced.append(entry)
            continue
        hunks = sections_by_id[home]["hunks"]
        # Sit next to the nearest neighbour, so the file tree of the section stays readable
        want, near, at = _dir_parts(hunk["file"]), -1, -1
        for i, h in enumerate(hunks):
            if h.get("file") == hunk["file"]:
                near, at = len(want) + 1, i
            elif _shared(want, _dir_parts(h.get("file"))) >= near:
                near, at = _shared(want, _dir_parts(h.get("file"))), i
        hunks.insert(at + 1, entry)
        owners[hunk["file"]][home] += 1
        dirs[home][want] += 1
    if unplaced:
        catch_all(data)["sections"][0]["hunks"].extend(unplaced)
    return len(fresh)


def catch_all(data):
    """The group unexplained new files land in — reused across refreshes, made on the first one."""
    for group in data.get("groups") or []:
        if group.get("id") == NEW_GROUP_ID:
            return group
    ja = is_japanese(data)
    group = {
        "id": NEW_GROUP_ID,
        "title": "レビュー後に増えた変更" if ja else "Changes made since the review",
        "intent": ("レビューを作ったあとに触られたファイルです。まだどの意図にも割り当てられていません。"
                   if ja else
                   "Files touched after the review was written. They belong to no intent yet."),
        "importance": "high",
        "sections": [{
            "id": "s-new",
            "title": "未分類の変更" if ja else "Unsorted changes",
            "explain": ("差分を取り直したときに現れた変更です。解説はまだありません。"
                        if ja else
                        "Changes that appeared when the diff was re-taken. Not explained yet."),
            "hunks": [],
        }],
    }
    data.setdefault("groups", []).insert(0, group)
    return group


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path, payload):
    """Write whole or not at all — the server re-reads these files on every request."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser(description="re-take the diff of an open kaisetu review")
    ap.add_argument("data", help="path to review-data.json")
    args = ap.parse_args()
    try:
        print(refresh(args.data)["message"])
    except Refused as e:
        sys.exit(f"kaisetu refresh: {e}")


if __name__ == "__main__":
    main()
