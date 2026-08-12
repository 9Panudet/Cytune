# Motif+BO — Phase-1 Terminal Report (Contribution-B)

**Categorical-native Bayesian Optimization for autotuning Cython compiler directives × GCC flags, under
verified correctness.** This is the project's terminal, run-grounded closeout. Every quantitative claim is
labeled **MEASURED** (committed raw + a recompute command + an auditor pass), **MEASURED-REPLAY** (computed
on the measured endpoint tables; grid-scoped — §7), or **INFERRED** (a landscape-grounded expectation,
explicitly not a measured result). Nothing here is asserted, projected, or hand-computed. Consolidated data:
`results/characterization/ProjectReport_data.json` (`scripts/corpus/build_report_data.py`, reads only
committed raw).

**Epistemic spine.** The CHARACTERIZATION is **MEASURED** — crit-3 directive-tunability (callgrind), the
§1.3 Δ-flatness on the production endpoint rig for all 9 survivors, the per-directive decomposition, the
separability/interaction structure of the high-Δ units, and the auditor-verified power analysis. The RQ1′
**offline-replay** (§7) is **MEASURED-REPLAY**: the near-optimum basin is measured **wide** (median K/N =
0.25) on the 16-config grids — the flatness/separability finding in search-trajectory terms — so on grids
this small **no search method separates by evaluations and endpoint quality is ~tied**; this corroborates
(never supersedes) the inference and holds **on those grids only, not on full Θ = 1728**. The full-Θ
**BO ≤ RS** conclusion (§8) is an **INFERENCE** from the measured structure — NOT a measured result. A
full-Θ BO-vs-RS experiment was **deliberately not run**: the power analysis proves n=9 cannot detect the
pre-registered effects, so any such run yields a statistically uninterpretable (hence refutable) null.

---

## 1. Objective & RQ1

**RQ1 (MEASURED question, pre-registered §5.3 / `results/prereg/PREREG_RQ1_UNIT_OF_ANALYSIS.md`):** *Does
categorical Bayesian Optimization (SMAC3-style RF surrogate + feasibility-weighted EI) beat Random Search
for autotuning the joint space of Cython compiler directives × GCC flags on real numeric hot loops, without
trading verified correctness for speed?*

Search space Θ (§2.3): 5 Cython directives (boundscheck, wraparound, cdivision, initializedcheck,
nonecheck) → 2⁵, × GCC (opt_level ∈ {−O1,−O2,−O3}, march, funroll, fast_math, ffp_contract conditional on
fast_math) → base |Θ| = 1728. Hardware: i3-10100F, 16 GB, GPU unused. Environment: pinned Podman image
(digest `/data/env/IMAGE_DIGEST`); `-ffp-contract` always explicit (§3.2).

RQ1 has TWO pre-registered viability gates that must both pass before a BO-vs-RS comparison is meaningful:
**power** (n ≥ the MDE target, §4.5) and **non-flatness** (§1.3: the directive/flag landscape must have
exploitable spread — median Δ ≥ 1.5 and ≥70% of units Δ ≥ 1.2). This report shows both gates fail on the
accessible corpus **at every reasonable definition of the corpus** (§4, §6), characterizes *why* at the
mechanism level, and derives the BO≤RS expectation from that measured structure.

**Canonical corpus (§3).** The canonical surviving corpus is the **9 modules with an endpoint-measured Δ**.
The criterion-3 line partitions them **7 PASS + 1 documented exception (isotonic) + 1 DROP (cc)**; every
verdict below is reported at all three cuts **n = 7 / 8 / 9** to prove it does not depend on where the
analyst draws that line. Fold count over the 9 survivors: **7 folds** (§6).

---

## 2. Instrument validation (MEASURED)

Before any RQ1 measurement, the instrument itself was validated. **Complete committed defect series
(nothing omitted).** "Silent" = the defect **reached a result** before detection (the report's own
standard); "caught-before-ship" = a hard failure surfaced *before* any result was produced.

| # | defect | project | home | class | fix |
|---|---|---|---|---|---|
| D1 | zero-embedding (graph front-end returned `None`→zero vectors) | predecessor | roadmap §0.2 | **SILENT** | hard-fail extraction + gate I-2 (non-degenerate features) |
| D2 | bare-import driver (timed interpreter/import, not the hot loop) | predecessor | roadmap §0.2 | **SILENT** | real hot-loop drivers + input-scaling regression + gate I-1 |
| D3 | `import smac` ImportError (private sklearn symbol removed) | this | `logs/defects/D3.md` | caught-before-ship | pin + shim; hard ImportError at 0.1.3, no result produced |
| D4 | rig died post-isolcpus (hotplug thermal + governor EBUSY) | this | `logs/defects/D4.md` | caught-before-ship | robust thermal channels + governor-loop retry; rig failed visibly |
| D5 | screen-vs-endpoint Δ contamination (floyd 3.188 artifact) | this | `logs/defects/D5.md` | **SILENT** | median-of-3-subprocess endpoint rig + enforced CF-1 |
| D6 | in-place re-callability (degenerate path on reps 2..K) | this | roadmap v1.4 §5.1 + `src/tests/test_per_rep_regen.py` | **SILENT** | per-rep input regen from committed recipe, UNTIMED (timing region preserved) |

**Four SILENT defects (each reached a result): D1, D2, D5, D6.** D3/D4 are committed post-mortems that
failed *visibly* before any result, listed here for completeness. The in-place re-callability defect is
numbered **D6** for consistency; its post-mortem home is the roadmap v1.4 §5.1 + `test_per_rep_regen.py`
(not a standalone `logs/defects/D6.md`). This complete accounting is the F3 fix — the prior table listed
D1/D2/(unnumbered)/D5 and silently omitted D3/D4.

**I-1 (known-good-beats-known-bad, on a REAL hot loop; guards D2). MEASURED = 9.425×.**
Raw: `results/calibration/i1/raw/horner_good_K30.json` (median 78.20 µs) vs `horner_bad_K30.json` (median
737.06 µs); K=30, paired, median-of-medians. Threshold: numeric-loop path ≥ 1.5× → **PASS by 6.3×
margin**. Recompute: `median(bad.result.samples_ns)/median(good.result.samples_ns)`. Pre-reg
`results/prereg/PREREG_I1.md`; kernel choice `results/characterization/I1_numeric_kernel_choice.md`.

**I-3 (tiered oracle + feasibility). MEASURED.** `src/motifbo/oracle/feasibility.py` + `src/motifbo/oracle/`
classify every candidate: bit-exact (int/label outputs), tolerance (float outputs, §3.1-derived), and
feasibility (sanitizer/oracle pass). Tests: `src/tests/test_oracle_{bitwise,tolerance,feasibility,
edge_suite,manifest,cpp_exceptions}.py`; independent recompute `results/audit/0.P/recompute_feasibility.py`.
Fast-math (FP=A) configs are **feasibility-gated** — they change floating-point results, so they are excluded
from the bit-preserving Δ_strict axis below (the "verified correctness, never traded" axis). Sanitizer
known-good evidence: `results/sanitize/known_good/REPORT.md`.

**Timing rig (MEASURED, v1.4).** Median-over-N=3-fresh-subprocesses endpoint; `perf_counter_ns` wraps ONLY
the kernel call; construction is outside the timed region; per-rep regen for in-place kernels (D6).
`src/motifbo/timing/{endpoint,_child,runtime_ns}.py`. **CF-1** (one container on the isolated core at a time)
+ **CF-4** (~8 ms page-fault/THP offset pinned) + `measure_wrap.sh` (verifies no_turbo=1, governor
performance, cpu3 isolated, THP ∈ {madvise,never}, refuses to measure otherwise). The D5 contamination
finding is itself a timing-rig methodology result: a single-shot in-process median on a memory-bound kernel
can be inflated 2.6× by a transient CF-1 violation — enough to invert a pre-registered admission decision —
and the median-of-3-subprocess endpoint rig + enforced isolation removes it.

---

## 3. Corpus construction & criterion-3 directive-tunability (MEASURED)

**Inventory → triage.** From the §4.3 sklearn/scipy inventory, units were vendored with full cimport/import
closures (`data/corpus/**`, per-unit MANIFEST + §4.2 checklist), import-confirmed, and passed through the
crit-3 gate: *is the hot loop directive-tunable cython, or a thin wrapper around a non-tunable library
(BLAS) / Python-object overhead?* Criterion-3 was **MEASURED via callgrind** at the fastest config
(−O3 −march=native — worst case for share), construction-subtracted (run B[N kernel calls] − run A[0 calls])
with per-object Ir attribution and thread pools pinned. Method: `scripts/corpus/crit3_callgrind_run.py` +
`crit3_callgrind_delta.py`; raw `results/characterization/crit3/<unit>__crit3.json` (+ `cgA/cgB` annotate +
dumps); recompute `python3 scripts/corpus/crit3_aggregate.py`. Directive-tunable share = (unit cython .so
Ir + libm Ir) / total per-call Ir — libm counts as tunable because the Θ flags (fast_math, march=native
libmvec) tune the transcendentals; BLAS (libopenblas) and Python-object overhead are non-tunable.

| module | tunable% | .so% | libm% | BLAS% | pyobj% | verdict |
|---|---|---|---|---|---|---|
| _predictor | 100.0 | 100.0 | 0.0 | 0.0 | 0.0 | PASS |
| _binning | 100.0 | 100.0 | 0.0 | 0.0 | 0.0 | PASS |
| _ppoly | 99.5 | 99.5 | 0.0 | 0.0 | 0.0 | PASS |
| _k_means_elkan | 99.3 | 99.3 | 0.0 | 0.0 | 0.1 | PASS |
| sparsefuncs_fast (csr) | 99.1 | 99.1 | 0.0 | 0.0 | 0.9 | PASS |
| _online_lda_fast | 96.0 | 55.0 | 41.0 | 0.0 | 0.0 | PASS |
| _shortest_path (floyd) | 94.8 | 94.8 | 0.0 | 0.0 | 3.9 | PASS |
| _isotonic (PAVA) | 85.7 | 85.7 | 0.0 | 0.0 | 14.3 | **exception (retained, §3.1)** |
| **_traversal (cc)** | **44.6** | 44.6 | 0.0 | 0.2 | 41.1 | **DROP** |
| _dbscan_inner *(drop ref)* | 40.4 | 40.4 | 0.0 | 0.0 | 57.9 | DROP (object) |
| _k_means_lloyd *(drop ref)* | 26.5 | 26.5 | 0.0 | 73.5 | 0.1 | DROP (BLAS) |

**MEASURED findings that corrected the source-triage:** (a) lda's psi/digamma splits 55% cython + 41% libm
(both tunable) → 96%, not the projected 98%; (b) **cc/_traversal is only 44.6% tunable** — driven at the
public `connected_components()` API, 41% of its instructions are `validate_graph` plumbing (installed scipy,
non-tunable), which at this kernel size rivals the cython SCC loop (floyd's heavier O(N³) compute dwarfs the
same plumbing → 94.8%). The DROP spot-checks confirm the two non-tunable mechanisms cleanly: **lloyd = BLAS
73.5%** (`_gemm`→libopenblas), **dbscan = object 57.9%** (`object[:]` memoryview per-neighbor overhead).

**§3.1 — isotonic (PAVA) disposition (F2, documented exception, not a floating "BORDERLINE").** Criterion-3
requires ≥ 90% kernel share; isotonic reads **85.7%** .so / **14.3%** non-kernel — below the line as written.
It is **retained as a documented exception**, for a specific, checkable reason: the 14.3% is **irreducible
in-place driver scaffolding**. PAVA is *not re-callable* (D6), so the rig regenerates the y/w buffers per rep;
that regen is real work in the callgrind denominator but is **not** the kernel. Crucially, **Δ is a
within-driver worst/best RATIO at a FIXED scale**, so the constant scaffolding cancels — the reported
Δ=1.178 is unaffected by the 14.3% share. The FLAT verdict is *additionally* shown robust to excluding
isotonic entirely: the n=7 variant (§4) drops it and stays FLAT. Raw:
`crit3/_inplace_contiguous_isotonic_regression__crit3.json`.

**Canonical partition.** Of the 9 endpoint-Δ-measured survivors: **7 PASS** (predictor, binning, ppoly,
elkan, csr, lda, floyd) + **1 documented exception** (isotonic) + **1 DROP** (cc, kept in the Δ set as the
crit-3-weak boundary case). This is the F1 canonicalization: §4/§6 report the verdict at n=7 (PASS only),
n=8 (+isotonic), n=9 (+cc) so no conclusion rides on the crit-3 cut.

---

## 4. Landscape characterization: the §1.3 Δ-flatness (MEASURED)

The 9 surviving modules were probed over a fixed 16-config factorial (CHK·DIV·OPT·FP,
`results/prereg/PREREG_DELTA_PROBE.md`, committed before any Δ observed). **All 9 were measured on the
production v1.4 median-of-3-subprocess ENDPOINT rig** (raw `delta_probe/<unit>__endpoint.json`; recompute
`python3 scripts/corpus/delta_aggregate_final.py`). Δ(unit) = t_worst / t_best. Δ_all uses all 16 configs;
Δ_strict uses only the 8 bit-preserving (FP=T, no fast-math) configs — the correctness-honest axis. The
**input scale** and **t_best** (F5) are shown per unit — note the light 61 ms pava and 53 ms elkan alongside
the heavy 1465 ms cc, so the reader sees each Δ is a within-unit ratio at a fixed, disclosed scale.

| module | fold | input scale | t_best | Δ_all | Δ_strict | measured lever |
|---|---|---|---|---|---|---|
| _k_means_elkan | cluster | n=500k, d=50, k=50 | 53 ms | **3.929** | **3.929** | −O3/native vectorization (2.5×) + boundscheck |
| sparsefuncs_fast (csr) | utils | n=3.5M, d=200, ρ=0.05 | 197 ms | **3.183** | **3.040** | boundscheck elision (3.0×) |
| _binning | ensemble | n=300k, d=30, bins=255 | 530 ms | 1.696 | 1.253 | fast-math *instability* (Δ_all from FP=A poles); strict flat |
| _predictor | ensemble | n=5M, d=20, depth=15 | 763 ms | 1.408 | 1.381 | −O3 (~1.2×); boundscheck ~1.0× |
| _shortest_path (floyd) | csgraph | N=700 | 251 ms | 1.338 | 1.179 | memory-bandwidth-bound (screen 3.19 was contamination, D5) |
| _online_lda_fast | decomposition | 120k×100 | 246 ms | 1.304 | 1.188 | flat; psi (.so + libm) |
| _traversal (cc) | csgraph | N=2M, deg=5 | 1465 ms | 1.212 | 1.209 | flat |
| _isotonic (PAVA) | isotonic | n=4M | 61 ms | 1.178 | 1.162 | flat |
| _ppoly | interpolate | k=4, m=2000, p=6M | 455 ms | 1.106 | 1.079 | flat |

`Δ_all sorted   = [1.106, 1.178, 1.212, 1.304, 1.338, 1.408, 1.696, 3.183, 3.929]` → **median 1.338**,
78% ≥ 1.2.
`Δ_strict sorted= [1.079, 1.162, 1.179, 1.188, 1.209, 1.253, 1.381, 3.040, 3.929]` → **median 1.209**,
56% ≥ 1.2.

**§1.3 admission (median ≥ 1.5 AND ≥70% ≥ 1.2) — FAILS on BOTH axes, at EVERY crit-3-line variant (F1).**

| corpus variant | n_module | n_fold | median Δ_all (%≥1.2) | median Δ_strict (%≥1.2) | §1.3 verdict |
|---|---|---|---|---|---|
| **n=7** (strict crit-3 PASS only) | 7 | 6 | 1.408 (85.7%) | 1.253 (57.1%) | **FLAT** |
| **n=8** (+ isotonic exception) | 8 | 7 | 1.373 (75.0%) | 1.220 (50.0%) | **FLAT** |
| **n=9** (+ cc; canonical) | 9 | 7 | 1.338 (77.8%) | 1.209 (55.6%) | **FLAT** |

The median is below the 1.5 line on both axes at every cut → the corpus is **FLAT**, and the verdict is
**robust to where the analyst draws the crit-3 line** (recompute: `build_report_data.py`, block `corpus`).

**Per-directive decomposition (MEASURED).** There are exactly **two** levers that ever exceed ~1.4×, and
neither is universal: (1) **boundscheck elision** on the index-streaming csr kernel (3.0×; a Cython
directive already in Θ); (2) **−O3/−march=native auto-vectorization** of the dense distance loop in elkan
(2.5×; GCC flags already in Θ). The other 7 units are latency/branch/memory-bound with neither lever — their
whole-Θ Δ is 1.1–1.4×. **binning's Δ_all 1.696 is fast-math instability, not exploitable structure** (best
AND worst configs are both FP=A; on the bit-preserving axis it is 1.253). The corpus is **bimodal**: 2
genuine high-Δ units + 7 flat, with the median firmly in the flat cluster.

**F5 — pava sensitivity.** The lightest-t_best unit (pava, 61 ms) is the natural "is a small unit inflating
flatness?" worry. It is *deflating*, not inflating: even lifting pava to a hypothetical Δ_all = 1.5 moves the
n=9 median only from 1.338 to **1.408** — still below the 1.5 line, **still FLAT** (recompute:
`build_report_data.py`, `corpus.pava_sensitivity`). The verdict does not hinge on any single light unit.

**F4 — elkan closure-completeness (MEASURED, verified from build artifacts).** `_euclidean_dense_dense` is a
plain (non-`inline`) `cdef floating … noexcept nogil` **defined in `_k_means_common.pyx`** and cimported by
elkan (`from ._k_means_common cimport _euclidean_dense_dense`); it compiles into the **co-built
`_k_means_common.so`**, *not* inlined into `_k_means_elkan.so`. But `_k_means_common` is in elkan's cobuild
list (dep-order: common **before** elkan), so it is **rebuilt under the same Θ flags as elkan under each of
the 16 matrix configs** — the euclidean kernel is matrix-built, not an installed helper. crit-3 attributes
its Ir to `_k_means_common.so` and counts **both** co-built .so's (`so_names=[_k_means_common., _k_means_elkan.]`
= 99.3% .so). Therefore the Δ=3.929 and the opt_level 52.6% SS attribution (§5) reflect matrix-built code.
The earlier "cimported-INLINE" phrasing was inaccurate; the co-built-sibling mechanism is the corrected
finding, and closure-completeness holds. Raw: `data/corpus/sklearn/_k_means_elkan/closure/**/_k_means_common.{pyx,pxd}`
+ `corpus_drivers.py` cobuild list + `crit3/elkan_iter_chunked_dense__crit3.json`.

**Opt-invariance (MEASURED, A4).** The high-Δ units' Δ_strict is a *speed* difference between
**bit-identical** results, not a fast-math correctness trade: elkan at −O1 −march=x86-64 strict vs −O3
−march=native strict produced identical `centers_new` (sha256 match, `results/characterization/
A4_opt_invariance.md`); csr opt-invariance established in the archetype campaign.

---

## 5. Separability of the high-Δ units (MEASURED)

For the 2 high-Δ units, a full factorial over their active knobs (**2 boundscheck × 3 opt_level × 2 march**,
FP=strict, endpoint rig) was run and the log-runtime response decomposed (saturated-model ANOVA) into main
effects + 2-/3-way interactions. Raw `results/characterization/separability/<unit>__separability.json`;
recompute `python3 scripts/corpus/separability_decompose.py <file>`.

| unit | main-effect variance | interaction variance | dominant terms (SS fraction) |
|---|---|---|---|
| sparsefuncs_fast (csr) | **99.7%** | **0.3%** | boundscheck 92.7%, opt_level 6.8%, march 0.2%; bc:opt 0.2% |
| _k_means_elkan | **95.4%** | **4.6%** | opt_level 52.6%, boundscheck 42.7%, march 0.1%; bc:opt 4.4% |

**MEASURED result: both high-Δ units are separable** — ≥95% of the runtime variance is additive main
effects; the largest interaction term anywhere is elkan's bc:opt at **4.4%**. csr is dominated by a *single
binary knob* (boundscheck); elkan by *two near-additive knobs* (boundscheck + opt_level). There is no
high-order interaction structure. This is the measured foundation of both the RQ1′ replay (§7) and the
BO≤RS inference (§8).

---

## 6. Viability: power analysis (MEASURED, auditor-verified)

The RQ1 unit of analysis is the module (primary) / fold (sensitivity), pre-registered
(`PREREG_RQ1_UNIT_OF_ANALYSIS.md`). Paired-Wilcoxon power was simulated (one-sample Cliff's δ of
cluster-median diffs; conservative rank-based; method `results/characterization/POWER_SIM_METHOD.md`).
Raw `results/power/power_table.json` + `power_table_extended.json`; independent recompute
`results/audit/1.2.4/recompute_power.py` (prior zero-diff, re-confirmed by the stats-auditor).

| n (clusters) | power @ δ=0.2 | @ δ=0.4 | @ δ=0.6 (large) |
|---|---|---|---|
| **6** | 0.122 | 0.273 | 0.521 |
| **7** | 0.123 | 0.288 | 0.561 |
| **8** | 0.127 | 0.322 | 0.633 |
| **9 (surviving module n)** | 0.168 | 0.410 | **0.727** |
| 12 | 0.194 | 0.482 | 0.834 |
| 17 | 0.253 | 0.652 | 0.941 |

**Smallest n for power ≥ 0.8: δ=0.6 → 12, δ=0.4 → 26, δ=0.2 → 103** (`power_table_extended.json`; the
δ=0.2 first-crossing is ±1-cluster MC-sensitive — n=102 gives 0.7985).

**F1 fold-count correction + per-variant power.** The surviving corpus is **n = 9 modules / 7 folds**. (The
prior "8 folds" was the optimistic upper bound of the SURVIVAL_LEDGER's "7–8" range recorded before the
crit-3 line was finalized; the canonical count over the 9 endpoint-measured survivors is **7** — the original
11 folds minus linear_model, tree, manifold, optimize, which dropped entirely.) Power is **< 0.8 at every
crit-3-line variant, at BOTH the module and the fold level:**

| variant | module n → power @δ=0.6 | fold n → power @δ=0.6 |
|---|---|---|
| n=7 | 7 → 0.561 | 6 → 0.521 |
| n=8 | 8 → 0.633 | 7 → 0.561 |
| n=9 | 9 → 0.727 | 7 → 0.561 |

**Both pre-registered gates fail, robustly:** power (n = 9/7 ≪ 12/26/103) AND non-flatness (§4, median Δ
1.34/1.21 < 1.5) — at n = 7, 8, and 9, at module and fold granularity.

---

## 7. RQ1′ offline-replay — search-trajectory corroboration of the flat/separable landscape (MEASURED-REPLAY, grid-scoped)

A **secondary, pre-registered analysis on already-measured data** (pre-reg
`results/prereg/PREREG_RQ1PRIME_REPLAY.md`, committed `2dc9efe` **before** any replay outcome was computed;
outcome committed `b5f3fb8`). It is **NOT** the roadmap's RQ1 (no BO surrogate, no new corpus, no new flag
space, **no new timing**) and does not consume the §1.3.3/B-12 amendment. It expresses the §4 flatness / §5
separability finding in **search-trajectory** terms: *how wide is the near-optimum basin on the measured
16-config grids, and does that leave room for a structured screen to beat Random Search by evaluations?*

**Protocol (frozen in the pre-reg).** Per unit, grid = the 16-config Δ-probe (N=16). Near-optimum = configs
with median ≤ t_best·(1+τ), **τ = max(endpoint_CI, 0.02)**; every unit's measured CI < 1.3% so **τ = 0.02**
for all 9. **RS** = uniform without replacement; **E[evals] = (N+1)/(K+1)** exact + a 10,000-seed MC check.
**DOE** = resolution-IV 8-run half fraction (I = CHK·DIV·OPT·FP) → additive main-effect predicted-best → +1
confirmation = **9 evals**. **Flat rule:** K ≥ N/2 ⇒ flatness certificate, excluded from the paired test.

| unit | near-opt K | **basin K/N** | RS E[evals] to basin | DOE pred | **DOE endpoint quality (pred/t_best)** |
|---|---|---|---|---|---|
| _k_means_elkan | 1 | 0.06 | 8.50 | UPHA | 1.036 (3.6% off; K=1 single-config basin) |
| sparsefuncs_fast (csr) | 4 | 0.25 | 3.40 | UCHA | 1.010 (within τ) |
| _binning | 1 | 0.06 | 8.50 | UCHT | 1.100 (10% off; fast-math-instability config) |
| _predictor | 4 | 0.25 | 3.40 | UPHA | 1.013 (within τ) |
| _shortest_path (floyd) | 8 | 0.50 | 1.89 | UPHT | 1.007 *(flat certificate)* |
| _online_lda_fast | 1 | 0.06 | 8.50 | UCHA | 1.000 (exact best) |
| _traversal (cc) | 4 | 0.25 | 3.40 | UPHT | 1.001 (within τ) |
| _isotonic (PAVA) | 5 | 0.31 | 2.83 | UPHA | 1.000 (exact best) |
| _ppoly | 2 | 0.12 | 5.67 | UCHA | 1.000 (exact best) |

**MEASURED-REPLAY result — the correct statement (this is NOT an "RS beats DOE/BO" result):**

1. **The near-optimum basin is wide.** Median **K/N = 0.25** (median K = 4 of 16; floyd 0.50; range 1–8),
   so RS reaches the basin in a **median 3.4 evals** (range 1.89–8.5). A balanced main-effect screen needs
   **≥ 8 evals** just to estimate the 4 factors on a 16-point grid. **On grids this small, with basins this
   wide, no search method can win by evaluations** — RS's short hitting time is below any structured screen's
   fixed cost as a matter of *grid size + basin width*, not method quality.
2. **Endpoint quality is ~tied.** DOE lands **within τ (near-optimum) on 6/8** non-flat units (median
   predicted/t_best = **1.006**); on the 2 single-config-basin units (K=1) its additive prediction lands
   within **3.6%** (elkan) / **10.0%** (binning — the fast-math-instability config, worst case). RS reaches
   the **exact best** within its full 16-eval budget. **Neither method meaningfully out-*finds* the other on
   these grids.**
3. **The sign-test measures evals-to-basin, not quality.** The paired sign-test (RS's expected evals-to-basin
   < DOE's fixed 9 on all 8 non-flat units, **p = 0.00781**) is a statement about **eval budgets on N=16
   grids** — and it is **DOE-cost-dependent** (**p = 0.07031** at the pre-registered DOE=8 sensitivity) and
   grid-scoped. It is **demoted**: the headline is the wide-basin / tied-quality *mechanism*, not a
   "significant win."

**Corroboration, not a separate result.** A wide near-optimum basin *is* the §4 flatness + §5 separability
finding expressed as a search trajectory: an easy landscape leaves little for any optimizer to gain. This
**reinforces the §8 INFERRED BO ≤ RS** (nothing for a surrogate to exploit); it does **not** show RS beating
DOE or BO.

**Reconciliation with §5 (explicit).** §5 shows the landscape is separable, which makes a structured screen
(`characterize` / DOE) the domain-appropriate tuner — and indeed the **12-config strict factorials confirm
structure is findable: the additive DOE screen lands on the csr and elkan optima** (csr→`BCF_-O3_G`,
elkan→`BCF_-O3_N`). Both statements hold together: **structure exists and is findable, *and* the 16-config
grids are too small / the basins too wide for evals-to-optimum to separate a structured screen from RS.** The
replay is a grid-size statement, not a contradiction of §5.

**Scope (binding).** **MEASURED-REPLAY** — holds **on the measured 16-config grids only, not on full
Θ = 1728**. It corroborates, and never supersedes, the §8 **INFERRED** BO ≤ RS. Raw
`results/characterization/rq1prime/` + `delta_probe/*__endpoint.json`; recompute
`python3 scripts/corpus/rq1prime_replay.py` (+ basin/quality via `build_report_data.py`).

---

## 8. Conclusion (INFERRED — explicitly not a measured full-Θ result)

**BO ≤ RS over full Θ is the EXPECTED outcome from the measured landscape structure — it was deliberately
not run.** The power analysis (§6) proves n=9/7 cannot detect the pre-registered effects, so a full-Θ
BO-vs-RS experiment would yield a statistically uninterpretable null (non-significant ≡ underpowered, hence
refutable). Running it would manufacture a false headline. Instead the expectation is **INFERRED** from the
measured structure, now with the §7 replay as measured corroboration on the accessible grids:

1. **Flat majority (7/9, Δ_strict ≤ 1.38, MEASURED §4):** no signal for any optimizer to find → BO and RS
   both return ≈ the baseline; any BO−RS difference is noise (null from *absence of signal*). §7 makes this
   concrete: floyd is a literal flatness certificate, and every flat unit's near-optimum basin is a large
   fraction of the grid.
2. **High-Δ minority (2/9) is separable (MEASURED §5):** where speedup exists it is ≥95% additive main
   effects — csr is one binary cliff (boundscheck), elkan is two near-additive knobs. An RF-surrogate BO
   beats RS only by modeling *interactions* the acquisition can exploit; with ≤4.6% interaction variance
   there is essentially nothing to exploit beyond the main-effect grid → BO ≈ RS (null from *no interaction
   structure*). §7 corroborates this **as measured data**: the near-optimum basin is wide (median K/N = 0.25),
   so on these small grids the landscape is easy — no search method separates by evaluations and endpoint
   quality is ~tied — which is exactly "nothing for a surrogate to exploit" in search-trajectory terms (this
   is corroboration of BO≈RS, **not** an "RS beats DOE/BO" result).

Both regimes on this corpus are RQ1-unfavorable, for measured reasons, independent of the power shortfall.
The full-Θ statement is a landscape-grounded expectation derived from measured separability + flatness + the
grid-scoped replay + BO theory — **not** a measured full-Θ BO≤RS result.

**§1.3.3 amendment (extended GCC flag space) — advised against.** The only ≥3× levers are boundscheck (a
Cython directive, already in Θ) and −O3/march vectorization (already in Θ); the per-directive decomposition
shows extra `-f` flags buy ≤1.4× anywhere. The flatness is in the kernels, not an under-explored flag set.

---

## 9. Contribution-B — what ships

A precisely-scoped, irrefutable **methodology + characterization** contribution:

1. **A validated measurement instrument** (the committed, tested COMPONENTS — not yet a packaged CLI): the
   v1.4 median-of-3-subprocess endpoint rig with its M-subprocess characterize path
   (`src/motifbo/timing/endpoint.py`) + CF-1/CF-4 isolation (`scripts/measure_wrap.sh`) + the tiered oracle
   / feasibility (I-3, `src/motifbo/oracle/`) + real-hot-loop drivers with the I-1 (9.425×) and D2
   input-scaling guards + the crit-3 / Δ / separability / **replay** harnesses (`scripts/corpus/*`). It
   measures directive/flag Δ and criterion-3 tunability reproducibly. *(Packaging these behind a single
   `motifbo validate` / `motifbo characterize` CLI is a Phase-5 deliverable, not yet built — claimed here as
   components, not a shipping command.)*
2. **A complete silent-defect methodology record** (D1 zero-embedding, D2 bare-import, D5 screen-vs-endpoint
   contamination, D6 in-place re-callability — four SILENT; D3/D4 caught-before-ship, listed for
   completeness) — including the contamination finding as a timing-rig result: a single-shot median can
   invert a pre-registered decision by 2.6× on a memory-bound kernel.
3. **The directive-flatness + separability characterization** of accessible pure-Cython numeric kernels,
   with a **measured-replay corroboration**: directive/flag tuning has no BO-exploitable structure here
   because the landscape is flat for 7/9 kernels and, where non-flat, dominated by 1–2 separable
   binary/discrete knobs — and on the measured grids the near-optimum basin is wide (median K/N = 0.25), so
   the landscape is easy enough that evals-to-optimum cannot separate a structured screen from RS and endpoint
   quality is ~tied (§7 — corroboration, not "RS beats DOE"). The **connective insight:** the §5 separability
   factorial **is** the DOE screen operating as the practical tuner — it finds the levers + effect estimates
   in 12 evals/unit and, on both high-Δ units, lands on the
   optimum. `motifbo characterize` is thus the domain-appropriate tuner; §7 quantifies what a model-based
   sequential optimizer would add beyond it on these landscapes (measured: nothing, on these grids).

The contribution's value is that it is *irrefutable*: it claims exactly what was measured, labels the
grid-scoped replay MEASURED-REPLAY, and labels the full-Θ BO≤RS expectation as an inference from that
measurement rather than a manufactured underpowered null.

---

## 10. Raw-data appendix — every figure traces to raw + recompute + auditor

| claim | raw | recompute | auditor |
|---|---|---|---|
| Δ 9/9 endpoint; median 1.338/1.209; FLAT | `results/characterization/delta_probe/*__endpoint.json` | `python3 scripts/corpus/delta_aggregate_final.py` | stats (Δ agg) |
| F1 variants n=7/8/9 (Δ + folds 6/7/7) | `delta_probe/*__endpoint.json` (`fold`) + `crit3/*` | `build_report_data.py` block `corpus` | stats |
| F5 pava sensitivity (→1.408, FLAT) | same Δ raw | `build_report_data.py` `corpus.pava_sensitivity` | stats |
| crit-3 tunable shares; 8 tunable/3 drop | `results/characterization/crit3/<unit>__crit3.json` (+ cgA/cgB) | `python3 scripts/corpus/crit3_aggregate.py` | measurement |
| F2 isotonic 85.7% documented exception | `crit3/_inplace_contiguous_isotonic_regression__crit3.json` | `crit3_aggregate.py` | measurement |
| F4 elkan closure (co-built sibling .so) | `data/corpus/sklearn/_k_means_elkan/closure/**/_k_means_common.{pyx,pxd}` + cobuild list | inspect + `crit3/elkan…__crit3.json` | validation |
| separability csr 99.7/0.3, elkan 95.4/4.6 | `results/characterization/separability/*__separability.json` | `python3 scripts/corpus/separability_decompose.py <f>` | stats (ANOVA) |
| power table; n80 12/26/103; n=9/7 | `results/power/power_table.json` + `_extended.json` | `results/audit/1.2.4/recompute_power.py` | stats (zero-diff) |
| **RQ1′ replay: RS 8/8, p=0.00781; DOE=8 sens p=0.07031** | `results/characterization/rq1prime/rq1prime_replay.json` | `python3 scripts/corpus/rq1prime_replay.py` | stats (zero-diff) |
| I-1 margin 9.425× | `results/calibration/i1/raw/horner_{good,bad}_K30.json` | `median(bad)/median(good)` | validation |
| opt-invariance (elkan bit-identical) | `results/characterization/A4_opt_invariance.md` | build L/H strict, sha256(centers_new) | measurement |
| complete D-series D1..D6 (4 silent) | roadmap §0.2 (D1/D2); `logs/defects/D3,D4,D5.md`; v1.4 §5.1 + `test_per_rep_regen.py` (D6) | — | validation |
| consolidated data | `results/characterization/ProjectReport_data.json` | `python3 scripts/corpus/build_report_data.py` | — |

**Audit for this pass.** Every headline statistic touched by F1–F5 + the RQ1′ replay was recomputed from
committed raw by an **independent reimplementation** (`results/audit/closeout_rq1prime/independent_reaudit.py`
— own parser, own res-IV enumeration, own sign test; does not import the project scripts) → **ALL ZERO-DIFF**,
and passed **scrutinize** (no residual "8 folds", no floating BORDERLINE, no "inline" overclaim, replay
consistently grid-scoped, DOE=8 sensitivity confirmed pre-registered in `2dc9efe` with zero outcomes). The
three dedicated §6.5 auditor subagents (stats/measurement/validation) were launched but **session-limited**
(API cap, resets 9:50 am Asia/Bangkok) before returning final verdicts — they are to be **re-run on capacity
reset** for belt-and-suspenders compliance; their partials were confirmatory. Full §-by-§ stamps + the honest
subagent status are in `results/resultNew.md` §4. Prior Phase-B zero-diff verdicts for the unchanged headline stats
stand (`results/characterization/PHASE_B_AUDIT.md`).

**Status: STOP for human review before declaring final — this report does not declare the project
closed.** Every quantitative claim above is MEASURED (committed raw + recompute + auditor zero-diff),
MEASURED-REPLAY (§7, grid-scoped), or explicitly INFERRED (full-Θ BO≤RS only). A full-Θ BO-vs-RS run was
deliberately not performed: n=9/7 is underpowered (§6), so the null would be uninterpretable.
