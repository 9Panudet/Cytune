"""Positive and negative controls for the replay harness, BEFORE any of its readings count.

CLAUDE.md: "New instruments (generator, replay harness, probe) get positive AND negative controls
before their readings count (a planted 2x lever must be detected; a known-flat kernel must read
flat)." This harness is a new instrument. It reports regret numbers that will decide whether the
shipped engine changes, so a harness that silently reads zero regret on everything, or that leaks
the table to the engine, would produce a confident wrong answer.

Five controls, each falsifiable:
  C1 NEGATIVE  a synthetic FLAT table must route honest-flat and spend ONLY the probe.
  C2 POSITIVE  a synthetic planted 2x lever must be found, and regret must be ~0.
  C3 CHEAT     the engine must not be able to reach the table through the sealed object.
  C4 ACCOUNTING  configs_measured must equal the distinct non-reference configs actually queried.
  C5 REAL      on a real frozen table, the harness's emitted config must be one cytune could emit,
               and regret must be computed against a denominator the policy can actually reach.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import engine                                              # noqa: E402
import fleet                                               # noqa: E402
from cytune import plan, routing                           # noqa: E402
from cytune._vendor import theta                           # noqa: E402


def flat_table(base=1_000_000.0, jitter=0.0):
    """Every config within ±jitter of the same median. delta_probe -> ~1.0 -> R1 honest-flat."""
    return {c: (True, base * (1.0 + jitter * ((c % 7) - 3) / 3.0), "ok")
            for c in range(theta.N_CONFIGS)}


def planted_table(lever_factor=2.0, base=1_000_000.0):
    """A 2x lever on ONE factor level the strict policy can reach: opt_level == -O3.

    Planted on an EMITTABLE axis on purpose. A lever planted on fast-math would be a control the
    default policy is required to refuse, which tests the policy, not the instrument.
    """
    tbl = {}
    for c in range(theta.N_CONFIGS):
        cfg = theta.config_of(c)
        med = base / (lever_factor if cfg[5] == "-O3" else 1.0)
        tbl[c] = (True, med, "ok")
    return tbl


def _check(name, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return bool(ok)


def main():
    print("DOE-v2 replay harness controls")
    ok = True

    # ---- C1 NEGATIVE: a flat landscape must read flat.
    r = engine.run(flat_table())
    ok &= _check("C1 negative (flat reads flat)",
                 r["route"] == routing.HONEST_FLAT and r["n_screen"] == 0 and r["n_walk"] == 0,
                 f"route={r['route']} rule={r['rule']} screen={r['n_screen']} walk={r['n_walk']} "
                 f"measured={r['configs_measured']}")

    # ---- C2 POSITIVE: a planted 2x lever must be detected AND captured.
    r = engine.run(planted_table(2.0))
    found_o3 = r["emitted_id"] is not None and theta.config_of(r["emitted_id"])[5] == "-O3"
    ok &= _check("C2 positive (planted 2x lever is found)",
                 r["route"] != routing.HONEST_FLAT and found_o3 and r["regret_emittable"] < 1e-9,
                 f"route={r['route']} emitted opt_level="
                 f"{theta.config_of(r['emitted_id'])[5] if r['emitted_id'] is not None else None} "
                 f"regret={r['regret_emittable']:.6f} speedup={r['speedup']:.3f}")

    # ---- C2b POSITIVE CONTROL ON THE CONTROL: a 1.0x "lever" must NOT be found.
    #      Without this, C2 would pass for an engine that always emits -O3 regardless of evidence.
    r = engine.run(planted_table(1.0))
    ok &= _check("C2b negative (a 1.0x lever is not claimed)",
                 r["route"] == routing.HONEST_FLAT,
                 f"route={r['route']} rule={r['rule']}")

    # ---- C3 CHEAT: the sealed object must refuse everything but the interface.
    s = engine.Sealed(flat_table())
    leaked = []
    for attr in ("_tbl", "tbl", "table", "data", "values", "keys", "items"):
        try:
            getattr(s, attr)
            leaked.append(attr)
        except AttributeError:
            pass
    try:
        s[0]
        leaked.append("__getitem__")
    except AttributeError:
        pass
    ok &= _check("C3 cheat (table unreachable through the sealed object)",
                 not leaked, f"leaked={leaked or 'nothing'}")

    # ---- C4 ACCOUNTING: paid count == distinct non-reference queries.
    tbl = planted_table(2.0)
    s = engine.Sealed(tbl)
    for c in (theta.REFERENCE_ID, 5, 5, 9, theta.REFERENCE_ID):
        s.query(c)
    ok &= _check("C4 accounting (reference is free, repeats are free)",
                 s.paid == 2, f"paid={s.paid} (expected 2 for queries {{ref,5,5,9,ref}})")

    # ---- C5 REAL: on a real frozen table the answer must be emittable and the denominator real.
    man = fleet.manifest()
    ov = fleet.overlay()
    kid = next(k for k, v in sorted(man["kernels"].items()) if v["role"] == "R-anchor")
    tbl = fleet.load_table(kid, man, ov)
    r = engine.run(tbl)
    emit_ok = r["emitted_id"] is None or plan.STRICT.allows(r["emitted_id"])
    denom_ok = r["true_opt_emittable_ns"] is not None and (
        r["true_opt_emittable_ns"] >= r["true_opt_all_ns"])
    ok &= _check("C5 real (emitted config is emittable; denominator is reachable)",
                 emit_ok and denom_ok and r["regret_emittable"] >= -1e-12,
                 f"{kid}: emitted={r['emitted_id']} regret_emit={r['regret_emittable']:.4f} "
                 f"regret_all={r['regret_all']:.4f} measured={r['configs_measured']}")

    print("CONTROLS:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
