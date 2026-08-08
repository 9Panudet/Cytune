"""I4 — ARTIFACT BINDING. Tying every claim to the bytes that produced it.

THE GAP THIS CLOSES, stated by the adversary who found it: *every check verifies the DOCUMENT
against the config_id, and nothing verifies the config_id against the ARTIFACT actually built,
gated and timed.* H12, H6 and H1 are three instances of that one gap:

  H12  a `# cython:` file header overrode the -X flags, so all 32 directive combinations compiled
       identically. The document described directives that were never applied.
  H6   a stub image printed `clean: true`. The document reported a gate that never ran the rig.
  H1   the driver owns the clock. The document reported times the artifact never took.

I1 could not see any of them, because I1's ground truth is `theta.config_of(config_id)` — a pure
function of the id. It proves the document is internally consistent. It cannot prove the document
is about the run that happened.

WHAT BINDING ADDS. Four facts, recorded where they are produced and checked where they are claimed:

  artifact_sha256          the .so that was compiled, hashed at build and re-hashed at measure
  source_sha256            the generated C it was compiled from, per directive combo
  toolchain_image_digest   the image the compiler and the sanitizer actually ran in
  rig_fingerprint          the verified host state under which the timing was taken

None of it is derived from the config id. All of it is a hash of something on disk. That is the
whole point: a check whose ground truth is recomputable from the id can only ever confirm the id.

THE FOUR INVARIANTS (registered in invariants.py, each with a test that makes it fire):

  I4.1  EMISSION BINDING       the emitted config's artifact is the one that was measured
  I4.2  FACTOR DEGENERACY      the factors cytune varies actually change the generated code
  I4.3  GATE SOURCE BINDING    the gate built the same source, for the same config, in the
                               pinned image
  I4.4  RIG BINDING            a timing claimed as quiesced carries a verified rig fingerprint

HONEST SCOPE. Binding proves the document describes the artifacts this run produced. It cannot
prove those artifacts do what their source says — that is the compiler's job — and it cannot prove
the numbers the driver reported are the times the artifact took. See `certify.corroborate_ratio`
for how far the second one can be pushed, and SECURITY.md for where it stops.
"""
from __future__ import annotations

import hashlib
import json
import os

from ._vendor import theta

ARTIFACTS = "artifacts.jsonl"

# The five directives cytune varies, in theta's canonical order. Named here as well as in session
# because this module is the one that decides whether they DID anything.
DIRECTIVES = theta.FACTOR_NAMES[:5]


class BindingViolation(AssertionError):
    """A claim that is not bound to the artifact behind it. Never emitted, never written."""

    def __init__(self, invariant, detail):
        self.invariant = invariant
        super().__init__(f"{invariant}: {detail}")


def _violation(inv, detail):
    raise BindingViolation(inv, detail)


# ------------------------------------------------------------------------------------- hashing
def sha256_file(path):
    """Full-file sha256, streamed. None if the file is not there — an absent artifact is a
    binding failure, not an exception to be swallowed at the call site."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def sha256_files(paths):
    """One digest over several files, path-qualified and order-independent.

    A cobuild config produces several .so files and a closure produces several .c files; hashing
    them individually would give a set to compare rather than a value, and hashing them in
    filesystem order would make the digest depend on readdir. Sorted by relative name, with the
    name mixed in so a rename counts.
    """
    h = hashlib.sha256()
    for name, path in sorted(paths):
        h.update(name.encode())
        h.update(b"\0")
        h.update((sha256_file(path) or "<missing>").encode())
        h.update(b"\0")
    return h.hexdigest()


# Build OUTPUT, not build INPUT. Excluded from the source-tree digest so that hashing a kernel
# directory gives the same answer before and after something has compiled in it — otherwise the
# host and the container could never agree on what "the same source" means.
_TREE_SKIP_DIRS = ("_so", "_ccache", "__pycache__", ".git")
_TREE_SKIP_EXT = (".pyc", ".so", ".c", ".o", ".npy")


def tree_sha256(root):
    """Content digest of a kernel source tree — every input file, path-qualified.

    Used on BOTH sides of the sanitizer gate: the container hashes what it built from, the host
    hashes what it measured, and I4.3 compares them. Relative paths, so the same tree hashes the
    same whether it is mounted at /kdir or sitting in a workspace.
    """
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _TREE_SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(_TREE_SKIP_EXT):
                continue
            p = os.path.join(dirpath, fn)
            files.append((os.path.relpath(p, root), p))
    return sha256_files(files)


def short(digest):
    """First 12 hex characters. The `sha256:` prefix podman puts on image ids is stripped first,
    because otherwise half the shown characters are the word `sha256` and two different images
    print the same string."""
    if not digest:
        return "?"
    return digest.split(":", 1)[-1][:12]


def combo_key(config_id):
    """The 5-directive combo string — the cythonize cache key, and the unit of I4.2."""
    return "".join("1" if v else "0" for v in theta.directive_combo(theta.config_of(config_id)))


# ---------------------------------------------------------------------------- the record store
def path(odir):
    return os.path.join(odir, ARTIFACTS)


def read(odir):
    """{config_id: record}. Last write wins, so a rebuild supersedes its predecessor."""
    p = path(odir)
    if not os.path.exists(p):
        return {}
    out = {}
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "config_id" in r:
            out[r["config_id"]] = r
    return out


def append(odir, records):
    """Append-only, like the table and the manifest: a crashed build leaves what it had."""
    if not records:
        return path(odir)
    os.makedirs(odir, exist_ok=True)
    with open(path(odir), "a") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path(odir)


def drop(odir):
    """Called by the cache invalidation that discards builds — an artifact record whose .so has
    been deleted is worse than no record, because it would satisfy a binding check for a file that
    is gone."""
    p = path(odir)
    if os.path.exists(p):
        os.remove(p)


# ------------------------------------------------------------------ I4.2  factor degeneracy
def degeneracy(records):
    """Compare the partition the ARTIFACTS fall into with the partition the FACTORS predict.

    THE MECHANISM THIS GENERALISES. H12 was one way to neutralise a factor: a `# cython:` header
    overrides -X, so every directive combination generates identical C. The header is now refused
    at ingest by name — but a blacklist only catches the mechanism someone already found. A
    `setup.py` `compiler_directives=` block, a cythonize wrapper, an `include`d .pxi with its own
    header, or a Cython version that ignores a directive would all do the same thing and none of
    them is on any list.

    So this does not look for the mechanism. It looks for the CONSEQUENCE: cytune varied a factor
    and the generated code did not change. That is observable without knowing why.

    TWO OUTCOMES, deliberately different:

      TOTAL collapse — every directive combination built produced byte-identical C. Then cytune's
      five directive factors are doing nothing at all, and it cannot tell whether that is because
      something is overriding them (in which case every directive claim it makes is false) or
      because the kernel contains no code they affect (in which case the claims are true and
      useless). It refuses, and says both.

      PARTIAL collapse — some directive never changed the C. That is a real, useful fact about the
      user's kernel: `initializedcheck` costs nothing here because there is nothing to check. It is
      reported, not refused, and it goes in the certificate.
    """
    built = {cid: r for cid, r in (records or {}).items() if r.get("source_sha256")}
    by_combo = {}
    for cid, r in built.items():
        by_combo.setdefault(combo_key(cid), set()).add(r["source_sha256"])

    # A combo whose representatives disagree means the .c cache was not honoured — a real defect,
    # but not a degeneracy one. Collapse it to a sorted tuple so it is visible rather than lost.
    combos = {k: sorted(v)[0] for k, v in by_combo.items()}
    distinct_sources = sorted(set(combos.values()))
    artifacts = sorted({r["artifact_sha256"] for r in built.values() if r.get("artifact_sha256")})

    inert, live, undetermined = [], [], []
    for i, name in enumerate(DIRECTIVES):
        pairs = same = 0
        for combo, src in combos.items():
            flipped = combo[:i] + ("0" if combo[i] == "1" else "1") + combo[i + 1:]
            if flipped in combos:
                pairs += 1
                same += int(combos[flipped] == src)
        if not pairs:
            undetermined.append(name)
        elif same == pairs:
            inert.append(name)
        else:
            live.append(name)

    total = len(combos) >= 2 and len(distinct_sources) == 1
    return {
        "n_configs_built": len(built),
        "n_distinct_artifacts": len(artifacts),
        "n_directive_combos_built": len(combos),
        "n_distinct_generated_sources": len(distinct_sources),
        "directives_live": live,
        "directives_inert": inert,
        "directives_undetermined": undetermined,
        "total_collapse": total,
        "basis": ("the generated C is hashed per directive combination; a directive is INERT when "
                  "every pair of built combinations differing only in it produced byte-identical "
                  "C. Only combinations this run actually built are compared."),
    }


def assert_no_total_degeneracy(report, module_hint=""):
    """I4.2. Raise when every directive combination built produced identical code."""
    if not report.get("total_collapse"):
        return report
    _violation("I4.2",
               f"all {report['n_directive_combos_built']} directive combinations cytune built "
               f"produced BYTE-IDENTICAL generated C ({report['n_distinct_generated_sources']} "
               f"distinct source hash). The five directives it varies "
               f"({', '.join(DIRECTIVES)}) changed nothing, so every statement it could make "
               f"about them would be untestable.\n"
               f"  Two things produce this and cytune cannot tell them apart:\n"
               f"    1. something outside cytune is pinning the directives — a `# cython:` header "
               f"in this module or in one it cimports, a `compiler_directives=` block in setup.py, "
               f"a cythonize wrapper, or an included .pxi. In this case the -X flags cytune builds "
               f"with are OVERRIDDEN and every directive in every certificate would be a false "
               f"statement about what was compiled (this is defect H12).\n"
               f"    2. your kernel genuinely contains no code these directives affect. In that "
               f"case the claims would be true and worth nothing.\n"
               f"  It refuses rather than guess.{module_hint}")


# --------------------------------------------------------------- I4.1  emission binding
def assert_emission_bound(*, config_id, artifacts, endpoint):
    """I4.1. The config being emitted must name the artifact that was actually timed.

    THE DEFECT SHAPE. `confirm_winner` and the whole certificate pipeline pass a config_id around.
    Every downstream check re-derives what config_id MEANS. Nothing asked what was in the file the
    measurement process opened. A stale .so left behind by an earlier build, a manifest row
    pointing at a path that was rewritten, or an artifact replaced between the build phase and the
    measure phase all produce a certificate that is internally perfect and describes a binary that
    was never run.
    """
    rec = (artifacts or {}).get(config_id)
    if not rec:
        _violation("I4.1", f"config {config_id} is being emitted but there is no build record for "
                           f"it. Nothing ties the certificate to a compiled artifact.")
    built = rec.get("artifact_sha256")
    if not built:
        _violation("I4.1", f"the build record for config {config_id} carries no artifact hash.")
    timed = (endpoint or {}).get("artifact_sha256")
    if not timed:
        _violation("I4.1", f"the endpoint measurement of config {config_id} did not record which "
                           f"artifact it timed, so the speedup cannot be tied to a binary.")
    if timed != built:
        _violation("I4.1",
                   f"config {config_id} was BUILT as {short(built)} but the endpoint tier timed "
                   f"{short(timed)}. The certificate would describe one binary and report another "
                   f"binary's time. Nothing is emitted.")
    return built


# --------------------------------------------------------------- I4.3  gate source binding
def assert_gate_bound(*, config_id, gate, source_tree_sha256, pinned_image_digest):
    """I4.3. The sanitizer verdict must be about this config, this source, in the pinned image.

    THE DEFECT SHAPE (H6). `gate()` parses whatever JSON the image prints on stdout. The first fix
    compared the image NAME against the pinned name, which a `podman tag` defeats in one command.
    A digest cannot be re-pointed by tagging.

    The gate REBUILDS the config with -fsanitize, so its artifact is a different binary by
    construction and its hash cannot equal the timed one. What is bindable is what it built FROM:
    the same config id, the same source tree, the same toolchain. That is checked here; the
    sanitizer build's own hash is recorded for provenance rather than compared.
    """
    if not gate:
        return None
    if gate.get("ran") and gate.get("config_id") not in (None, config_id):
        _violation("I4.3", f"the sanitizer gate reports config {gate.get('config_id')} but the "
                           f"emitted config is {config_id}.")
    gate_src = gate.get("source_tree_sha256")
    if gate.get("ran") and gate_src and source_tree_sha256 and gate_src != source_tree_sha256:
        _violation("I4.3",
                   f"the sanitizer gate built source tree {short(gate_src)} but the configuration "
                   f"being emitted was built and timed from {short(source_tree_sha256)}. A clean "
                   f"gate on a different source is not a gate on this one.")
    # A gate that OMITS the attestation must not bind more loosely than one that supplies it.
    # Found by the focused adversarial re-run as Attack A's secondary defect: the stub image simply
    # did not print `source_tree_sha256`, so this check compared nothing and passed. Silence is not
    # agreement — the same rule the sanitizer gate itself lives under, one level up.
    if gate.get("clean") is True and source_tree_sha256 and not gate_src:
        gate["authoritative"] = False
        gate.setdefault("warning", (
            "the §1.4 gate returned CLEAN without attesting which source tree it built. A verdict "
            "that does not say what it was about is not treated as a pass: the 'safe' wording is "
            "withheld and --apply refuses."))
    # NOT a violation — a gate from an unpinned image is a WEAKER guarantee, and the design is that
    # it degrades and says so. The refusal that matters (`--apply`, the "safe" wording) is
    # downstream, and `authoritative` is what carries it.
    digest = gate.get("image_digest")
    if gate.get("clean") is True and pinned_image_digest and digest != pinned_image_digest:
        gate["authoritative"] = False
        gate["image_overridden"] = True
        gate.setdefault("warning", (
            f"the §1.4 gate ran in image digest {short(digest)}, which is NOT the pinned "
            f"{short(pinned_image_digest)}. A clean result from an unpinned image is not treated "
            f"as a pass: the 'safe' wording is withheld and --apply refuses. Re-tagging an image "
            f"with the pinned NAME does not change this — the digest is what is compared."))
    return gate


# ------------------------------------------------------------------- I4.4  rig binding
UNGATED = "UNGATED"


def assert_rig_bound(*, rig_mode, endpoint_records):
    """I4.4. A timing claimed as decision-grade must carry the host state that was verified.

    `measure_wrap.sh` exports RIG_FINGERPRINT only after its asserts pass, and every measured row
    stamps it; a row written outside the wrapper reads `UNGATED`. So the certificate's rig_mode and
    the rows' fingerprints are two independent records of the same fact, and they must agree. They
    could not disagree by accident — only by a measurement taken outside the rig being reported as
    if it were taken inside it.
    """
    fps = {r.get("rig") for r in (endpoint_records or {}).values() if r}
    fps.discard(None)
    if not fps:
        return None
    if rig_mode == "quiesced" and any(f == UNGATED for f in fps):
        _violation("I4.4", "the certificate claims the quiesced rig but an endpoint measurement "
                           "carries rig=UNGATED, which means it was taken outside measure_wrap and "
                           "no host assert was verified for it.")
    if rig_mode == "portable" and any(f != UNGATED for f in fps):
        _violation("I4.4", f"the certificate claims portable measurement but an endpoint row "
                           f"carries a verified rig fingerprint ({sorted(fps)[0][:60]!r}). The "
                           f"timings are better than the document says they are, which is still a "
                           f"document that does not describe its run.")
    return sorted(fps)


# --------------------------------------------------------------------- the certificate block
def provenance(*, config_id, artifacts, endpoint, gate, degeneracy_report, rig_fingerprints,
               image_digest, source_tree_sha256, n_measured):
    """A4 — the PROVENANCE block. Short, and every line is a hash of something on disk."""
    rec = (artifacts or {}).get(config_id) or {}
    deg = degeneracy_report or {}
    return {
        "emitted_artifact_sha256": rec.get("artifact_sha256"),
        "emitted_source_sha256": rec.get("source_sha256"),
        "build_argv": rec.get("build_argv"),
        "endpoint_artifact_sha256": (endpoint or {}).get("artifact_sha256"),
        "toolchain_image_digest": image_digest,
        "sanitizer_image_digest": (gate or {}).get("image_digest"),
        "sanitizer_source_tree_sha256": (gate or {}).get("source_tree_sha256"),
        "module_source_tree_sha256": source_tree_sha256,
        "rig_fingerprints": rig_fingerprints,
        "configs_measured": n_measured,
        "distinct_artifacts_built": deg.get("n_distinct_artifacts"),
        "directive_combinations_built": deg.get("n_directive_combos_built"),
        "distinct_generated_sources": deg.get("n_distinct_generated_sources"),
        "directives_inert_for_this_kernel": deg.get("directives_inert"),
        "note": ("every hash here is of a file this run produced, not a value derived from the "
                 "configuration id. The emitted artifact hash is the FILE the endpoint tier was "
                 "pointed at, hashed before and after the measurement; if they had differed, "
                 "nothing would have been emitted (I4.1). It does not bind against a driver that "
                 "hijacks its own interpreter's module loader — that is the stated trust boundary "
                 "(GUARANTEES N8), not something a hash can reach."),
    }


def render_provenance(prov):
    """The lines the user reads. Kept here rather than in `render` so the block and the fields it
    prints cannot drift apart."""
    if not prov:
        return []
    L = ["PROVENANCE — what these claims are bound to"]
    L.append(f"  emitted artifact      : {short(prov.get('emitted_artifact_sha256'))} "
             f"(timed: {short(prov.get('endpoint_artifact_sha256'))})")
    L.append(f"  toolchain image       : {short(prov.get('toolchain_image_digest'))}")
    if prov.get("sanitizer_image_digest"):
        L.append(f"  sanitizer image       : {short(prov.get('sanitizer_image_digest'))}")
    fps = prov.get("rig_fingerprints") or []
    L.append(f"  rig fingerprint       : {(fps[0] if fps else 'none recorded')}")
    L.append(f"  measured              : {prov.get('configs_measured')} configs, "
             f"{prov.get('distinct_artifacts_built')} distinct binaries from "
             f"{prov.get('distinct_generated_sources')} distinct generated sources "
             f"({prov.get('directive_combinations_built')} directive combinations)")
    inert = prov.get("directives_inert_for_this_kernel")
    if inert:
        L.append(f"  no effect on this kernel: {', '.join(inert)} — flipping these never changed "
                 f"the generated C")
    return L
