import json,sys
sys.path.insert(0,'/w/scripts/phasep')
d=json.load(open('/w/results/study/P3_ANALYSIS.json'))
sib=json.load(open('/w/results/study/MOTIF_SIBLING_PROBE.json'))
POWERED={'INT'}          # only cell at/above the n=26 floor (P-2)
POWER={'FLAT+FM':0.708,'MID':0.776,'LEVER-SEP':0.708,'INT':0.853}
NCONF={'FLAT+FM':20,'MID':24,'LEVER-SEP':20,'INT':29}
cells={}
for k in sorted(d['routing_matrix'], key=lambda x:(x.split('|')[0],int(x.split('|')[1]))):
    cell,B=k.split('|'); B=int(B)
    r=d['routing_matrix'][k]; m=r['median_regret']
    nm={a:m[a] for a in ('rs','doe','bo') if m.get(a) is not None}
    best=min(nm,key=lambda a:(nm[a],['rs','doe','bo'].index(a)))
    fam=d['families'][k]
    cells.setdefault(cell,{})[str(B)]={
      "installed_engine":best,
      "installed_median_regret":nm[best],
      "study_winner_all_arms":r['winner'],
      "study_verdict":r['verdict'],
      "median_regret_by_arm":m,
      "n_kernels":fam['n_inferential'],
      "seed_mean_sem":fam['seed_mean_sem'],
      "friedman_p":fam.get('friedman_p'),
    }
out={
 "schema":"phasep-routing-matrix-v1",
 "provenance":"P3-validated on the Phase-P SYNTHETIC benchmark, 20-seed prefix (amendment A-10). "
              "NOT validated on real code: RQ-P2 acceptance has not run.",
 "seeds_used":d['seeds_used'],"seeds_prereg":200,
 "sem_inflation_vs_prereg":d['sem_inflation_vs_prereg'],
 "powered_cells":sorted(POWERED),
 "underpowered_cells":{c:{"n_conformant":NCONF[c],"exact_power_at_delta_0.4":POWER[c],
                          "floor":26,"label":"UNDERPOWERED at δ=0.4"}
                       for c in ('FLAT+FM','MID','LEVER-SEP')},
 "motif_NOT_installed":{
   "decision":"Motif+BO won 13 of 20 cells and passes the §3.4 gate (p=3.46e-17, δ=0.772), and is "
              "NEVERTHELESS NOT INSTALLED in the product.",
   "reason_1_structural":"Motif+BO requires a corpus of previously-tuned SIBLING kernels to warm "
                         "start from. `cytune tune <one module>` has no such corpus — the LOKO "
                         "setting that produced the win does not exist at the point of use. The "
                         "arm is not runnable in the product as shipped.",
   "reason_2_validity":f"Its warm-start sources are {sib['enrichment_over_chance']:.1f}x enriched "
                       f"for kernels of the target's OWN generated template "
                       f"({sib['same_template_sources_mean_of_8']:.2f} of 8 vs a "
                       f"{sib['random_pick_baseline_of_8']:.2f} baseline). The measured advantage "
                       f"is substantially warm-starting from a near-copy of the target's own "
                       f"landscape — a property of a synthetic corpus with ~4 kernels per "
                       f"template. Dataset R's 9 real anchors have no siblings at all.",
   "what_would_change_this":"RQ-P2 acceptance on H + eligible R showing the advantage survives "
                            "where siblings do not exist.",
 },
 "headline_negative":"DOE — a deterministic D-optimal screen — is the best product-runnable arm in "
                     "18 of 20 cells. BO is beaten by DOE in 18 of 20 and is worse than RANDOM "
                     "SEARCH in several. The expensive Bayesian arm does not earn its cost on this "
                     "benchmark.",
 "cells":cells,
 "raw":"results/study/P3_ANALYSIS.json, results/study/regret*.jsonl",
 "recompute":"podman run ... python3 scripts/phasep/analyze_study.py",
}
json.dump(out,open('/w/results/study/ROUTING_MATRIX.json','w'),indent=1)
nonmotif=[v['installed_engine'] for c in cells.values() for v in c.values()]
from collections import Counter
print("installed engine distribution:",dict(Counter(nonmotif)))
print("-> results/study/ROUTING_MATRIX.json")
