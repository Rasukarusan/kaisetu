#!/bin/bash
# Print the branch the current branch was forked from.
# Order: PR base branch -> branch-creation record in the reflog -> remote HEAD -> main/master.
# Prints "UNKNOWN" and exits 1 when nothing can be resolved.
set -euo pipefail

CURRENT=$(git rev-parse --abbrev-ref HEAD)

# Print a usable ref for a branch name: the local branch if it exists, else origin/<name>.
resolve() {
  local name="$1"
  if [ "$name" = "$CURRENT" ]; then
    return 1
  fi
  if git rev-parse --verify --quiet "refs/heads/$name" >/dev/null; then
    echo "$name"
    return 0
  fi
  if git rev-parse --verify --quiet "refs/remotes/origin/$name" >/dev/null; then
    echo "origin/$name"
    return 0
  fi
  return 1
}

# 1. PR base branch (the most reliable signal when a PR exists)
BASE=$(gh pr view --json baseRefName -q .baseRefName 2>/dev/null || true)
if [ -n "$BASE" ]; then
  if resolve "$BASE"; then exit 0; fi
fi

# 2. Reflog: the "Created from" record written when the branch was created
LINE=$(git reflog show --no-abbrev "$CURRENT" 2>/dev/null | tail -1 || true)
if echo "$LINE" | grep -q "Created from"; then
  FROM=$(echo "$LINE" | sed 's/.*Created from //; s/ *$//')
  FROM=${FROM#refs/heads/}
  if [ "$FROM" = "HEAD" ]; then
    # Created from a detached HEAD: find another branch containing that commit
    COMMIT=$(echo "$LINE" | awk '{print $1}')
    RESOLVED=$(git branch --contains "$COMMIT" --format='%(refname:short)' 2>/dev/null \
      | grep -vx "$CURRENT" | head -1 || true)
    if [ -n "$RESOLVED" ]; then
      echo "$RESOLVED"
      exit 0
    fi
  else
    if resolve "$FROM"; then exit 0; fi
  fi
fi

# 3. Remote HEAD (the repo's default branch)
DEFAULT=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || true)
if [ -n "$DEFAULT" ]; then
  if resolve "$DEFAULT"; then exit 0; fi
fi

# 4. Fallback
for name in main master; do
  if resolve "$name"; then exit 0; fi
done

echo "UNKNOWN"
exit 1
