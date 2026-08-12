"""A3 rules 3 and 4: H offline and the fleet gate, for --probe-as-screen."""
import os, sys, json, statistics as st, importlib
REPO='/home/beimfedora/Documents/Motif+BO'
sys.path.insert(0, os.path.join(REPO,'src')); sys.path.insert(0, os.path.join(REPO,'scripts','doe_v2'))
sys.path.insert(0, os.path.join(REPO,'scripts','release'))
import fleet, engine, fleet_gate
from cytune import plan

BUDGETS = fleet_gate.BUDGETS

def replay(second_screen):
    orig = plan.SECOND_SCREEN
    plan.SECOND_SCREEN = second_screen
    try:
        return fleet_gate.replay(BUDGETS, engine_note=f"second_screen={second_screen}")
    finally:
        plan.SECOND_SCREEN = orig

D = replay(True); P = replay(False)

def by(rows, role=None):
    o={}
    for r in rows:
        if role and r['role']!=role: continue
        o.setdefault(str(r['budget']),{})[r['kernel']]=r
    return o

for role,label in ((None,'ALL 149'),('holdout-H','holdout-H (11)'),('R-anchor','R-anchors (9)'),('training','training (129)')):
    d,p = by(D['rows'],role), by(P['rows'],role)
    print(f"\n=== {label} ===")
    print(f"{'budget':>7} {'D median':>10} {'P median':>10} {'delta':>9} {'D worst':>9} {'P worst':>9} {'D cfg':>7} {'P cfg':>7}")
    for b in BUDGETS:
        k=str(b); ks=sorted(set(d[k])&set(p[k]))
        dr=[d[k][x]['regret_emittable'] for x in ks if d[k][x]['regret_emittable'] is not None]
        pr=[p[k][x]['regret_emittable'] for x in ks if p[k][x]['regret_emittable'] is not None]
        if not dr: continue
        dc=sum(d[k][x]['configs_measured'] for x in ks); pc=sum(p[k][x]['configs_measured'] for x in ks)
        print(f"{k:>7} {st.median(dr):>9.4%} {st.median(pr):>9.4%} {(st.median(pr)-st.median(dr))*100:>+8.3f}p "
              f"{max(dr):>8.3%} {max(pr):>8.3%} {dc:>7} {pc:>7}")

# fleet gate verdict: P engine vs the committed D baseline
base=json.load(open(fleet_gate.BASELINE))
f,t=fleet_gate.compare(base,P)
print(f"\n=== B1 fleet gate, probe-as-screen vs the committed default baseline ===")
codes={}
for c,b,kk,w in f: codes.setdefault(c,[]).append((b,kk,w))
for c in sorted(codes): print(f"  {c}: {len(codes[c])} finding(s)   e.g. {codes[c][0][2][:100]}")
print("  verdict:", "FAIL" if f else "PASS")

print("\n=== the 17 F3 cells in full ===")
for c,b,kk,w in f:
    if c=='F3': print(f"   budget={b:>6} {w}")
print("\n=== F2 ===")
for c,b,kk,w in f:
    if c=='F2': print(f"   budget={b:>6} {w}")
roles={r['kernel']:r['role'] for r in P['rows']}
hit=sorted({kk for c,b,kk,w in f if kk})
print(f"\n  distinct kernels harmed: {len(hit)}   roles: {sorted({roles[k] for k in hit})}")
print(f"  any R-anchors harmed? {[k for k in hit if roles[k]=='R-anchor'] or 'NONE'}")
print(f"  any holdout-H harmed? {[k for k in hit if roles[k]=='holdout-H'] or 'NONE'}")
