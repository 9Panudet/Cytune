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

## The instance that matters most: it disarmed a standing gate

Everything above is about losing a *document*. On 2026-08-13 the same mechanism was found to have
been silently disabling **B1, the fleet replay gate**, on `dev`.

`fleet_gate.py` needs two small freeze artifacts — `results/fleet/FREEZE_MANIFEST_V2.json` (71 KB)
and `results/fleet/SANITIZER_INFEASIBLE_OVERLAY.json` (16 KB). Both had been force-added to
**`research` only**, so a checkout of `dev` deleted them from the working tree. `smoke.sh` then took
its `else` branch and printed:

```
NOT RUN  B1 fleet gate — results/fleet is absent on this branch.
         Run it on `dev` or `research` before tagging.
```

…on `dev`. **The gate's own advice named the branch it could not run on**, and the yellow line reads
like a property of the branch layout rather than of a deleted file. `dev` is where engine changes
are made, and B1 is the gate that catches engine regressions the nine live anchors cannot see — it
found a 516 % worst case that no anchor contained. It could not run where it was needed.

Fixed two ways: both manifests are now force-added to `dev` as well (88 KB total, against the
215 MB of tables they pin, which stay uncommitted), and `smoke.sh` tests for **both** files and
tells the reader to check for a deleted file before believing the branch.

**The general lesson.** The hazard is not "documents disappear". It is that *a missing input turns a
gate into a pass-shaped message*, and this project has now paid for that shape three times: B2's
vendor check skipping forever on a product-only branch, D25's script dead on import, and this. When
a gate reports NOT RUN, find out **why** before accepting it.

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
