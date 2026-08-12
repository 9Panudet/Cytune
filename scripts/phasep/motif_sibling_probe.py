"""RQ-P3 construct-validity probe — is Motif's advantage TRANSFER, or sibling leakage?

Motif+BO won 13 of 20 routing cells and beat BO at p=1.7e-17, Cliff's delta 0.77. That is a
FAVOURABLE SURPRISE, and this campaign treats those as alarms: investigate before celebrating.

The hypothesis to falsify: Motif's LOKO warm start is picking source kernels that are SIBLINGS of
the target — same generated template, different parameters — so it is effectively warm-starting
from a near-copy of the target's own landscape. If so the advantage is a property of a synthetic
corpus with ~4 kernels per template, not evidence that motif transfer works on real code, where
no such sibling exists.

This replicates §8.4's own source ordering (descending cosine on standardized feature vectors) and
counts how many of the 8 selected sources share the target's template, against the baseline you
would get by picking 8 sources at random from the same corpus.

RESULT: 3.74 of 8 vs a 0.39 baseline — 9.7x enrichment. The hypothesis SURVIVES.
Committed as `results/study/MOTIF_SIBLING_PROBE.json`; see PHASEP_REPORT.md.
"""
import json,os,sys
import numpy as np
sys.path.insert(0,'/w/scripts/phasep')
import run_study as rst, motif, theta
man=rst.load_manifest('/w/results/fleet')
kids=rst.study_set(man)
feats,excl=rst.motif_sources('/w/results/fleet',man,kids,'/tmp/x.jsonl')
def tmpl(k):
    p=f'/w/results/fleet/_kernels/{k}/spec.json'
    return json.load(open(p)).get('template') if os.path.exists(p) else None

# Replicate §8.4's OWN source ordering: descending cosine on standardized feature vectors.
avail=[k for k in kids if k in feats]
same=[]; contribs=[]
for kid in avail:
    srcs=[s for s in avail if s!=kid]
    F=np.vstack([motif.feature_vector(feats[s]) for s in srcs])
    zS,zt,_=motif._standardize_S(F, motif.feature_vector(feats[kid]))
    def cos(a,b):
        na,nb=np.linalg.norm(a),np.linalg.norm(b)
        return float(a@b/(na*nb)) if na>0 and nb>0 else 0.0
    order=sorted(range(len(srcs)), key=lambda i:(-cos(zS[i],zt), srcs[i]))
    top8=[srcs[i] for i in order[:8]]
    t=tmpl(kid)
    same.append(sum(1 for s in top8 if tmpl(s)==t))
import statistics as st
from collections import Counter
print(f"kernels probed: {len(same)}")
print(f"of the 8 HIGHEST-COSINE LOKO sources, how many share the target's TEMPLATE:")
print(f"  mean {st.mean(same):.2f}/8  median {st.median(same)}  max {max(same)}  "
      f"zero-same in {sum(1 for x in same if x==0)} kernels")
print(f"  distribution: {dict(sorted(Counter(same).items()))}")
# baseline: if sources were picked at random, how many same-template would you expect?
tc=Counter(tmpl(k) for k in avail)
exp=st.mean([8*(tc[tmpl(k)]-1)/(len(avail)-1) for k in avail])
print(f"  RANDOM-PICK BASELINE (same corpus): {exp:.2f}/8")
print(f"  enrichment over chance: {st.mean(same)/exp:.1f}x")

import json as _json
_out = {
    "schema": "phasep-motif-sibling-probe-v1",
    "question": "Is Motif+BO's RQ-P3 win transfer, or leakage from same-template siblings?",
    "method": "replicates §8.4's source ordering (descending cosine on standardized feature "
              "vectors); counts same-template sources among the 8 selected, vs a random-pick "
              "baseline over the same corpus",
    "kernels_probed": len(same),
    "same_template_sources_mean_of_8": st.mean(same),
    "same_template_sources_median": st.median(same),
    "kernels_with_zero_same_template": sum(1 for x in same if x == 0),
    "distribution": {str(k): v for k, v in sorted(Counter(same).items())},
    "random_pick_baseline_of_8": exp,
    "enrichment_over_chance": st.mean(same) / exp,
    "verdict": "LEAKAGE HYPOTHESIS SURVIVES — Motif's sources are ~9.7x enriched for siblings of "
               "the target template. The measured win is real ON THIS BENCHMARK; it does not "
               "license a claim that motif transfer helps on real code, where a synthetic corpus's "
               "~4-kernels-per-template structure does not exist. Dataset R's 9 anchors are 9 "
               "distinct real kernels with no siblings at all.",
}
with open('/w/results/study/MOTIF_SIBLING_PROBE.json', 'w') as _f:
    _json.dump(_out, _f, indent=1)
print("\n-> results/study/MOTIF_SIBLING_PROBE.json")
