#!/usr/bin/env python3
"""B2 — generate `src/cytune/_vendor/VENDOR_MANIFEST.json` from the live study tree.

The vendor drift check used to compare `_vendor/*` against `scripts/phasep/*` directly, and
`pytest.skip` whenever the study tree was absent. On a product-only branch that is EVERY comparison,
forever: 12 of 14 collected items skip, and the two that run test nothing about drift. This project
named that failure mode itself (D23: "a check that never runs leaves no trace"); this points it at
the check.

The manifest turns the expected hashes into DATA that ships inside the package, so:

  * on ANY branch, `_vendor/*` is verified against the manifest — no study tree required;
  * where the study tree IS present, the manifest is additionally verified against it, so the
    manifest cannot drift from the source it claims to represent either.

Run this only when the vendored files are deliberately re-synced from the study, and commit the
manifest in the same commit as the files it pins.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

from cytune import test_cytune_vendor as V                                # noqa: E402

OUT = os.path.join(REPO, "src", "cytune", "_vendor", "VENDOR_MANIFEST.json")


def main():
    missing = [rel for rel in list(V.WHOLE_FILE.values()) + list(V.DATA_FILES.values())
               + [v[0] for v in V.PER_FUNCTION.values()]
               if not os.path.exists(os.path.join(REPO, rel))]
    if missing:
        print("REFUSING: the study tree is incomplete; a manifest built from it would pin the "
              f"wrong thing.\nmissing: {missing}", file=sys.stderr)
        return 2

    man = {
        "schema": "cytune-vendor-manifest/1",
        "purpose": ("expected hashes for src/cytune/_vendor/*, committed AS DATA so the drift "
                    "check runs on a product-only branch with no study tree. See "
                    "src/cytune/test_cytune_vendor.py."),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generated_from_git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "whole_file": {}, "per_function": {}, "constants": {}, "data_files": {},
    }

    for vend, rel in sorted(V.WHOLE_FILE.items()):
        man["whole_file"][vend] = {"study_source": rel,
                                   "sha256": V._sha(os.path.join(V.VENDOR, vend))}

    for vend, (rel, funcs) in sorted(V.PER_FUNCTION.items()):
        entry = {"study_source": rel, "functions": {}}
        for fn in funcs:
            src = V._func_source(os.path.join(V.VENDOR, vend), fn)
            if src is None:
                print(f"REFUSING: {vend} does not define {fn}", file=sys.stderr)
                return 2
            entry["functions"][fn] = hashlib.sha256(src.encode()).hexdigest()
        man["per_function"][vend] = entry

    for vend, names in sorted(V.CONSTANTS.items()):
        man["constants"][vend] = {n: V._const_sha(os.path.join(V.VENDOR, vend), n) for n in names}

    for rel_in_pkg, rel in sorted(V.DATA_FILES.items()):
        man["data_files"][rel_in_pkg] = {
            "study_source": rel, "sha256": V._sha(os.path.join(V.HERE, rel_in_pkg))}

    with open(OUT, "w") as f:
        json.dump(man, f, indent=1, sort_keys=True)
        f.write("\n")
    n = (len(man["whole_file"]) + sum(len(e["functions"]) for e in man["per_function"].values())
         + sum(len(e) for e in man["constants"].values()) + len(man["data_files"]))
    print(f"{OUT}\n{n} pins written "
          f"({len(man['whole_file'])} files, "
          f"{sum(len(e['functions']) for e in man['per_function'].values())} functions, "
          f"{sum(len(e) for e in man['constants'].values())} constants, "
          f"{len(man['data_files'])} data files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
