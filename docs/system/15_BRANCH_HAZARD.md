# Switching branches deletes the study documents from your working tree

**Read this before you `git checkout` between `main` and `research`.** It bit during the split
itself, within minutes of the branches being created.

## What happens

`.gitignore:43` is a bare `results/`, so **nothing under `results/` is tracked on `main` or `dev`**
(`git ls-files results/` returns 0 on both). The `research` branch carries 31 of those documents,
force-added past the ignore rule.

Git deletes a **tracked** file from the working tree when you switch to a branch that does not track
it. So:

```
git checkout research      # results/release/LAUNCH_REPORT.md appears (tracked here)
git checkout main          # ...and is DELETED from your working tree
```

The file is not lost — it is in the `research` branch's history — but it is gone from disk, and if
you had **uncommitted** edits to it under `main`, those are gone with it.

This is exactly what happened during the split: `LAUNCH_REPORT.md` was force-added on `research`,
the branch was switched back to `main`, and the file vanished mid-edit.

## What to do

**Recover a deleted document:**

```bash
git checkout research -- results/
git reset HEAD results/          # keep it untracked on this branch
```

**Before switching away from `main` or `dev` with work in `results/`:** commit it on `research`
first, or copy it outside the repo. An untracked-and-ignored file is safe; a file that is tracked on
*another* branch is not.

**Check what you are about to lose:**

```bash
git ls-tree -r --name-only research -- results/ | head
```

## Why the split is like this anyway

The alternative is to stop ignoring `results/`, and `results/` is **38 GB** — almost all of it build
caches and golden arrays. The 149 frozen tables alone are 215 MB against a 3 MB `.git`.

So the tracked set is deliberately narrow: the 816 KB of documents that a claim can be checked
against, plus the manifests that pin the bulk data by sha256. The hazard above is the price of that
choice, and it is written down rather than left to be discovered.

## The related trap

For the same reason, **every report in this project's history is pinned by sha256 in a commit
message** rather than being committed. If you are verifying a claim, check the hash in the commit
that introduced it against the file you are holding — that is what the pin is for, and it is the
only integrity check these documents have on `main` and `dev`.
