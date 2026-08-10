#!/usr/bin/env python3
"""Find past reviews of the repository and branch you are standing on.

A review costs a lot to build and stays true for the length of the branch: the grouping, the
explanations and the comment threads outlive any single fix. So before building a new one, the
skill asks whether the branch already has a review to go back to. This script answers that.

It reads only the small meta.json next to each review, never review-data.json, and matches on the
branch the review was taken on plus the repository it was taken in — two clones of the same
repository, or two worktrees on the same branch, do not get mixed up. Reviews of a document
(`--doc`) and reviews of a diff are kept apart: neither is an answer to the other.

Usage:
  find_review.py [repo-root]           # diff reviews of the current branch
  find_review.py --doc docs/spec.md    # document reviews of that file on the current branch

Prints one tab-separated line per match, newest first:
  <review dir>\t<generatedAt>\t<open|finished>\t<title>
Nothing at all — and exit 0 — when there is nothing to reopen.

Dependencies: Python 3 standard library only.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys


def git(root: pathlib.Path, *args: str) -> str:
    """Run a git command in `root`, or return "" if git has nothing to say."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return out.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo_root", nargs="?", default=".", help="target repository (default: CWD)")
    ap.add_argument("--doc", help="look for document reviews of this file instead of diff reviews")
    args = ap.parse_args()

    root = git(pathlib.Path(args.repo_root), "rev-parse", "--show-toplevel")
    if not root:
        return 0  # not a git repository: nothing was ever filed under a branch here
    root = str(pathlib.Path(root).resolve())

    branch = git(pathlib.Path(root), "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD":
        return 0  # detached HEAD: there is no branch to match on

    home = pathlib.Path(os.environ.get("KAISETU_HOME", pathlib.Path.home() / ".kaisetu"))
    base = home / pathlib.Path(root).name
    if not base.is_dir():
        return 0

    doc = None
    if args.doc:
        doc = str((pathlib.Path(root) / args.doc).resolve())

    for entry in sorted(base.iterdir(), reverse=True):
        meta_path = entry / "meta.json"
        if not meta_path.is_file():
            continue  # a review written before meta.json, or a stray directory
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or meta.get("branch") != branch:
            continue
        if meta.get("repoRoot") and str(pathlib.Path(meta["repoRoot"]).resolve()) != root:
            continue

        meta_doc = meta.get("doc")
        if doc is None:
            if meta_doc:
                continue  # a document review is not an answer to "review this diff"
        else:
            if not meta_doc or str((pathlib.Path(root) / meta_doc).resolve()) != doc:
                continue

        status = "finished" if (entry / "review-data.result.json").is_file() else "open"
        title = str(meta.get("title") or "(untitled)").replace("\t", " ")
        print(f"{entry}\t{meta.get('generatedAt', '')}\t{status}\t{title}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
