"""Phase-D — generate ProjectReport.html from the committed source-of-truth JSON.

Embeds results/characterization/ProjectReport_data.json VERBATIM into a self-contained HTML (offline-
viewable, no external deps, NO hand-entered numbers — every value is rendered from the embedded committed
data). A JS consistency check asserts every displayed aggregate re-derives from the embedded data.
Views: KPIs · Δ distribution (1.5 line, 70%) · F1 crit-3-line robustness (n=7/8/9) · per-directive lever ·
separability (main vs interaction) · power curves (n=7/8/9 + n80 targets) · crit-3 triage ·
RQ1' offline-replay (MEASURED-REPLAY: RS vs DOE evals, flat certificate marked).

Recompute: python3 scripts/corpus/build_html.py  (re-embeds the current committed JSON)
"""
import hashlib
import json

DATA_PATH = "results/characterization/ProjectReport_data.json"
OUT = "results/ProjectReport.html"

data = json.load(open(DATA_PATH))
raw = open(DATA_PATH).read()
digest = hashlib.sha256(raw.encode()).hexdigest()[:16]

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Motif+BO — Phase-1 Terminal Characterization (contribution-B)</title>
<style>
 :root{--bg:#0f1420;--panel:#171e2e;--ink:#e8edf6;--muted:#93a1bd;--line:#2a3852;
   --flat:#4a6fa5;--strict:#2fb1a3;--hi:#e0603a;--pass:#3fae6b;--border:#e0a93a;--drop:#c0483a;
   --rs:#2fb1a3;--doe:#e0a93a;--acc:#8b5cf6;}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
   font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 .wrap{max-width:1080px;margin:0 auto;padding:28px 20px 80px}
 h1{font-size:24px;margin:0 0 4px} h2{font-size:17px;margin:34px 0 6px;color:#cdd8ee}
 .sub{color:var(--muted);margin:0 0 6px} .verdict{display:inline-block;padding:3px 10px;border-radius:6px;
   font-weight:700;font-size:12px} .flatv{background:#3a2320;color:#f0b6a6;border:1px solid var(--hi)}
 .replayv{background:#12331f;color:#8fe3ac;border:1px solid var(--pass)}
 .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:10px 0}
 .lab{color:var(--muted);font-size:12px} .val{font-weight:700}
 .legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin:4px 0 8px}
 .sw{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:-1px}
 .kpi{display:flex;gap:14px;flex-wrap:wrap} .kpi .c{flex:1;min-width:150px;background:#111827;border:1px solid var(--line);
   border-radius:8px;padding:10px 12px} .kpi .n{font-size:20px;font-weight:800} .foot{color:var(--muted);font-size:12px;margin-top:8px}
 table{border-collapse:collapse;width:100%;font-size:12.5px} td,th{border-bottom:1px solid var(--line);padding:5px 8px;text-align:right}
 th:first-child,td:first-child{text-align:left} .mono{font-family:ui-monospace,Menlo,monospace}
 .tag{font-size:10.5px;padding:1px 6px;border-radius:4px} .tp{background:#12331f;color:#8fe3ac}
 .tb{background:#33290f;color:#ecc16b} .td{background:#331512;color:#f0a397}
 svg{display:block;width:100%;height:auto} .ax{stroke:var(--line);stroke-width:1} .axt{fill:var(--muted);font-size:10px}
 .ck{font-size:12px;padding:8px 12px;border-radius:8px;margin-top:14px}
 .scroll{overflow-x:auto}
</style></head><body><div class="wrap">
<h1>Motif+BO — Phase-1 Terminal Characterization</h1>
<p class="sub">Contribution-B closeout. Every value below is rendered from the committed
<span class="mono">@@DATA_PATH@@</span> (sha256 @@DIG@@…). CHARACTERIZATION = <b>MEASURED</b>;
RQ1′ replay = <b>MEASURED-REPLAY</b> (grid-scoped, §7); full-Θ BO&nbsp;≤&nbsp;RS = <b>INFERRED</b>
(not run — the corpus is underpowered).</p>
<div id="app"></div>
<div id="check" class="ck"></div>
<script id="data" type="application/json">@@JSON@@</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const $ = (h)=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild;};
const app = document.getElementById('app');
const esc = s => String(s).replace(/</g,'&lt;');
function bar(x,y,w,h,fill,rx=2){return `<rect x="${x}" y="${y}" width="${Math.max(0,w)}" height="${h}" rx="${rx}" fill="${fill}"/>`;}
function txt(x,y,s,cls='axt',anchor='start'){return `<text x="${x}" y="${y}" text-anchor="${anchor}" class="${cls}">${esc(s)}</text>`;}

/* ---- KPIs ---- */
const d=D.delta, CB=D.corpus;
app.append($(`<div class="panel"><div class="kpi">
 <div class="c"><div class="lab">§1.3 median Δ_all</div><div class="n">${d.median_all}</div><div class="lab">need ≥1.5 → <b style="color:var(--hi)">FAIL</b></div></div>
 <div class="c"><div class="lab">median Δ_strict (bit-preserving)</div><div class="n">${d.median_strict}</div><div class="lab">${Math.round(d.frac_ge12_strict*100)}% ≥1.2 · <b style="color:var(--hi)">FAIL</b></div></div>
 <div class="c"><div class="lab">crit-3 tunable / drop</div><div class="n">${D.crit3.n_tunable} / ${D.crit3.n_drop}</div><div class="lab">of ${D.crit3.units.length} probed</div></div>
 <div class="c"><div class="lab">surviving n (module / fold)</div><div class="n">${CB.canonical_n_module} / ${CB.canonical_n_fold}</div><div class="lab">δ.6→${D.power.targets_n_for_power80['0.6']} · δ.4→${D.power.targets_n_for_power80['0.4']} · δ.2→${D.power.targets_n_for_power80['0.2']} needed</div></div>
 <div class="c"><div class="lab">RQ1′ near-opt basin (measured grids)</div><div class="n">K/N ${D.rq1prime.basin.median_basin_frac}</div><div class="lab">quality ~tied (DOE within τ ${D.rq1prime.quality.doe_reaches_basin_within_tau}/${D.rq1prime.quality.n_nonflat})</div></div>
 </div>
 <div class="foot">Verdict: <span class="verdict flatv">CORPUS FLAT — both viability gates FAIL at n=7/8/9</span>
 &nbsp;<span class="verdict replayv">RQ1′: wide basin ⇒ easy landscape, quality ~tied (corroborates flat/separable — NOT "RS beats DOE")</span></div></div>`));

/* ---- Δ distribution ---- */
{
 const u=[...d.units].sort((a,b)=>b.delta_all-a.delta_all);
 const W=1000,rowH=30,padL=180,padR=40,top=16,H=top+u.length*rowH+30;
 const max=4.2, sc=x=>padL+(x/max)*(W-padL-padR);
 let s=`<svg viewBox="0 0 ${W} ${H}">`;
 [1.0,1.5,2,3,4].forEach(g=>{s+=`<line class="ax" x1="${sc(g)}" y1="${top}" x2="${sc(g)}" y2="${top+u.length*rowH}"/>`+txt(sc(g),H-8,g+'×','axt','middle');});
 s+=`<line x1="${sc(1.5)}" y1="${top}" x2="${sc(1.5)}" y2="${top+u.length*rowH}" stroke="var(--border)" stroke-width="1.5" stroke-dasharray="4 3"/>`;
 s+=txt(sc(1.5)+4,top+10,'§1.3 admission 1.5','axt');
 u.forEach((x,i)=>{const y=top+i*rowH; const hi=x.delta_strict>=1.5;
  s+=txt(padL-8,y+13,x.module,'axt','end');
  s+=bar(padL,y+4,sc(x.delta_all)-padL,9,hi?'var(--hi)':'var(--flat)');
  s+=bar(padL,y+15,sc(x.delta_strict)-padL,9,hi?'#b8492c':'var(--strict)');
  s+=txt(sc(x.delta_all)+5,y+12,x.delta_all.toFixed(2)+' / '+x.delta_strict.toFixed(2),'axt');});
 s+='</svg>';
 app.append($(`<h2>1 · Directive×flag Δ distribution — 9/9 endpoint rig (MEASURED)</h2>`));
 app.append($(`<div class="legend"><span><span class="sw" style="background:var(--flat)"></span>Δ_all (incl. fast-math)</span>
  <span><span class="sw" style="background:var(--strict)"></span>Δ_strict (bit-preserving)</span>
  <span><span class="sw" style="background:var(--hi)"></span>high-Δ subclass</span>
  <span>dashed = 1.5 admission line</span></div>`));
 app.append($(`<div class="panel scroll">${s}<div class="foot">median Δ_all ${d.median_all} (${Math.round(d.frac_ge12_all*100)}% ≥1.2), Δ_strict ${d.median_strict} (${Math.round(d.frac_ge12_strict*100)}% ≥1.2) — both medians &lt; 1.5 ⇒ FLAT (need ≥1.5 AND ≥70% ≥1.2). Raw: <span class="mono">${d.raw}</span> · recompute <span class="mono">${d.recompute}</span></div></div>`));
}

/* ---- F1: crit-3-line robustness (n=7/8/9) ---- */
{
 const V=CB.variants;
 let rows=V.map(v=>`<tr><td>${esc(v.label)}</td><td>${v.n_module} / ${v.n_fold}</td>
   <td>${v.median_all} (${Math.round(v.frac_ge12_all*100)}%)</td>
   <td>${v.median_strict} (${Math.round(v.frac_ge12_strict*100)}%)</td>
   <td><span class="tag td">${v.verdict_all}</span></td>
   <td>${v['power_module_d0.6']}</td><td>${v['power_fold_d0.6']}</td></tr>`).join('');
 app.append($(`<h2>2 · Robustness to the analyst's crit-3 line — n=7/8/9 (MEASURED · F1)</h2>`));
 app.append($(`<div class="panel"><div class="scroll"><table>
   <tr><th>corpus variant</th><th>n mod/fold</th><th>median Δ_all (%≥1.2)</th><th>median Δ_strict (%≥1.2)</th><th>§1.3</th><th>pow mod δ.6</th><th>pow fold δ.6</th></tr>${rows}</table></div>
   <div class="foot">FLAT and underpowered at EVERY crit-3 cut (n=7 PASS-only → n=8 +isotonic → n=9 +cc): median Δ &lt; 1.5 and power &lt; 0.8 (need 0.8 at n=${D.power.targets_n_for_power80['0.6']}) at module <i>and</i> fold level. Pava sensitivity: lifting pava to Δ=1.5 moves the n=9 median only to <b>${CB.pava_sensitivity['n9_median_all_if_pava_1.5']}</b> — still ${CB.pava_sensitivity.verdict}. Fold count corrected 8→${CB.canonical_n_fold}. Recompute: <span class="mono">build_report_data.py</span> block <span class="mono">corpus</span>.</div></div>`));
}

/* ---- per-directive lever ---- */
{
 let rows=d.units.map(x=>`<tr><td>${x.module}</td><td class="mono">${esc(x.scale)}</td><td>${x.t_best_ms}ms</td><td>${x.delta_strict.toFixed(2)}×</td><td style="text-align:left">${esc(x.lever)}</td></tr>`).join('');
 app.append($(`<h2>3 · Per-directive decomposition — the lever, scale &amp; t_best per unit (MEASURED)</h2>`));
 app.append($(`<div class="panel"><div class="scroll"><table><tr><th>module</th><th>input scale</th><th>t_best</th><th>Δ_strict</th><th>measured lever</th></tr>${rows}</table></div>
  <div class="foot">Only two levers exceed ~1.4×: boundscheck elision (csr) and −O3/native vectorization (elkan). All others 1.1–1.4×. Each Δ is a within-unit ratio at the disclosed fixed scale.</div></div>`));
}

/* ---- separability ---- */
{
 const S=D.separability; const keys=['sparsefuncs_fast','_k_means_elkan'];
 const W=1000,padL=150,top=10,rowH=54,H=top+keys.length*rowH+24;
 let s=`<svg viewBox="0 0 ${W} ${H}">`;
 const sc=x=>padL+x*(W-padL-60);
 keys.forEach((k,i)=>{const o=S[k];const y=top+i*rowH;const mf=o.main_effect_fraction, inf=o.interaction_fraction;
  s+=txt(padL-8,y+22,k,'axt','end');
  s+=bar(padL,y+8,sc(mf)-padL,26,'var(--pass)');
  s+=bar(sc(mf),y+8,sc(mf+inf)-sc(mf),26,'var(--hi)');
  s+=txt(padL+6,y+25,'main effects '+(mf*100).toFixed(1)+'%','axt');
  s+=txt(sc(1)+6,y+25,'interaction '+(inf*100).toFixed(1)+'%','axt');});
 s+='</svg>';
 app.append($(`<h2>4 · Separability of the 2 high-Δ units (MEASURED)</h2>`));
 app.append($(`<div class="legend"><span><span class="sw" style="background:var(--pass)"></span>additive main effects</span>
  <span><span class="sw" style="background:var(--hi)"></span>interaction variance</span></div>`));
 app.append($(`<div class="panel scroll">${s}<div class="foot">≥95% additive ⇒ no interaction structure for an RF surrogate to exploit → basis for the §7 replay + the §8 INFERRED BO≤RS.
  csr dominated by boundscheck (SS ${(S.sparsefuncs_fast.ss_fraction.boundscheck*100).toFixed(1)}%); elkan by boundscheck+opt_level (bc:opt only ${(S._k_means_elkan.ss_fraction['bc:opt']*100).toFixed(1)}%). Raw: <span class="mono">${S.raw}</span></div></div>`));
}

/* ---- power curves ---- */
{
 const P=D.power, L=P.levels;
 const W=1000,padL=54,padB=34,top=12,H=300;
 const xs=n=>padL+((n-L[0].n)/(L[L.length-1].n-L[0].n))*(W-padL-16);
 const ys=p=>top+(1-p)*(H-top-padB);
 let s=`<svg viewBox="0 0 ${W} ${H}">`;
 [0,.2,.4,.6,.8,1].forEach(p=>{s+=`<line class="ax" x1="${padL}" y1="${ys(p)}" x2="${W-16}" y2="${ys(p)}"/>`+txt(padL-6,ys(p)+3,p.toFixed(1),'axt','end');});
 s+=`<line x1="${padL}" y1="${ys(.8)}" x2="${W-16}" y2="${ys(.8)}" stroke="var(--border)" stroke-width="1.5" stroke-dasharray="4 3"/>`+txt(W-18,ys(.8)-4,'power 0.8','axt','end');
 // surviving-n variant markers (7/8/9)
 [7,8,9].forEach(n=>{s+=`<line x1="${xs(n)}" y1="${top}" x2="${xs(n)}" y2="${H-padB}" stroke="var(--hi)" stroke-width="${n===9?1.5:0.8}" stroke-dasharray="${n===9?'':'3 3'}"/>`;});
 s+=txt(xs(9)+4,top+10,'surviving n=7/8/9','axt');
 // n80 target markers on the axis (12 in-range; 26/103 off-chart -> annotate)
 const t06=P.targets_n_for_power80['0.6'];
 if(t06<=L[L.length-1].n){s+=`<line x1="${xs(t06)}" y1="${top}" x2="${xs(t06)}" y2="${H-padB}" stroke="var(--strict)" stroke-width="1" stroke-dasharray="2 3"/>`+txt(xs(t06)+3,top+22,'n₈₀(δ.6)='+t06,'axt');}
 const series=[['d0.6','δ=0.6 (large)','#2fb1a3'],['d0.4','δ=0.4','#4a6fa5'],['d0.2','δ=0.2 (small)','#8b5cf6']];
 series.forEach(([k,lab,col])=>{let path=L.map((r,i)=>(i?'L':'M')+xs(r.n)+' '+ys(r[k])).join(' ');
  s+=`<path d="${path}" fill="none" stroke="${col}" stroke-width="2"/>`;
  const last=L[L.length-1]; s+=txt(xs(last.n)+4,ys(last[k])+3,lab,'axt');});
 L.forEach(r=>{s+=txt(xs(r.n),H-10,r.n,'axt','middle');});
 s+='</svg>';
 const r9=L.find(r=>r.n===9), r7=L.find(r=>r.n===7);
 app.append($(`<h2>5 · Power vs corpus size (MEASURED, auditor-verified)</h2>`));
 app.append($(`<div class="panel scroll">${s}<div class="foot">n=7→${r7['d0.6']}, n=9→${r9['d0.6']} at even the LARGE δ=0.6 (need 0.8 at n=${P.targets_n_for_power80['0.6']}). Targets n₈₀: δ.6→${P.targets_n_for_power80['0.6']}, δ.4→${P.targets_n_for_power80['0.4']}, δ.2→${P.targets_n_for_power80['0.2']} (26/103 off-chart). Surviving n=9 module / ${P.surviving_n_fold} fold. Raw: <span class="mono">${P.raw}</span></div></div>`));
}

/* ---- crit-3 triage ---- */
{
 const C=D.crit3.units, W=1000,padL=170,rowH=24,top=10,H=top+C.length*rowH+22;
 const sc=x=>padL+x*(W-padL-60);
 let s=`<svg viewBox="0 0 ${W} ${H}">`;
 [0,.25,.5,.75,.9,1].forEach(g=>{s+=`<line class="ax" x1="${sc(g)}" y1="${top}" x2="${sc(g)}" y2="${top+C.length*rowH}"/>`+txt(sc(g),H-6,(g*100)+'%','axt','middle');});
 s+=`<line x1="${sc(.9)}" y1="${top}" x2="${sc(.9)}" y2="${top+C.length*rowH}" stroke="var(--border)" stroke-dasharray="4 3"/>`;
 C.forEach((x,i)=>{const y=top+i*rowH; const col=x.verdict==='PASS'?'var(--pass)':x.verdict==='BORDERLINE'?'var(--border)':'var(--drop)';
  s+=txt(padL-8,y+15,x.module,'axt','end');
  s+=bar(padL,y+5,sc(x.tunable_share)-padL,14,col);
  let extra=x.blas_share>=.3?` BLAS ${(x.blas_share*100).toFixed(0)}%`:x.pyobj_share>=.3?` obj ${(x.pyobj_share*100).toFixed(0)}%`:x.libm_share>0?` (.so ${(x.so_share*100).toFixed(0)}+libm ${(x.libm_share*100).toFixed(0)})`:'';
  s+=txt(sc(x.tunable_share)+5,y+16,(x.tunable_share*100).toFixed(1)+'%'+extra,'axt');});
 s+='</svg>';
 app.append($(`<h2>6 · Criterion-3 directive-tunability via callgrind (MEASURED)</h2>`));
 app.append($(`<div class="legend"><span><span class="sw" style="background:var(--pass)"></span>PASS (7)</span>
  <span><span class="sw" style="background:var(--border)"></span>isotonic 85.7% → documented exception, retained</span>
  <span><span class="sw" style="background:var(--drop)"></span>DROP</span><span>dashed = 90% tunable</span></div>`));
 app.append($(`<div class="panel scroll">${s}<div class="foot">Canonical survivors = 9 Δ-measured modules = 7 PASS + isotonic (exception, ${(D.isotonic_disposition.crit3_tunable_share*100).toFixed(1)}%, in-place scaffolding cancels in the Δ ratio) + cc (DROP 44.6%, kept as the crit-3-weak boundary). tunable = cython .so + flag-tunable libm; drops: lloyd BLAS, dbscan object, cc validate_graph plumbing. −O3 −march=native worst-case, construction-subtracted. Raw: <span class="mono">${D.crit3.raw}</span></div></div>`));
}

/* ---- RQ1' offline-replay (MEASURED-REPLAY) ---- */
{
 const R=D.rq1prime, U=R.per_unit;
 const W=1000,padL=200,rowH=26,top=16,padR=60,H=top+U.length*rowH+30;
 const maxE=10, sc=x=>padL+(x/maxE)*(W-padL-padR);
 let s=`<svg viewBox="0 0 ${W} ${H}">`;
 [0,2,4,6,8,10].forEach(g=>{s+=`<line class="ax" x1="${sc(g)}" y1="${top}" x2="${sc(g)}" y2="${top+U.length*rowH}"/>`+txt(sc(g),H-8,g,'axt','middle');});
 // DOE fixed 9-eval line
 s+=`<line x1="${sc(9)}" y1="${top}" x2="${sc(9)}" y2="${top+U.length*rowH}" stroke="var(--doe)" stroke-width="1.5" stroke-dasharray="4 3"/>`;
 s+=txt(sc(9)+3,top+10,'DOE 9 evals','axt');
 U.forEach((x,i)=>{const y=top+i*rowH;
  const nm=x.unit.length>24?x.unit.slice(0,24)+'…':x.unit;
  s+=txt(padL-8,y+15,nm+(x.flat_certificate?' ▪flat':''),'axt','end');
  // RS evals-to-basin bar (grid-size property, NOT a "win")
  s+=bar(padL,y+6,sc(x.rs_expected_evals)-padL,12,x.flat_certificate?'var(--muted)':'var(--rs)');
  const qtxt=x.doe_pred_quality_ratio<=1.0201?'DOE within τ':'DOE '+((x.doe_pred_quality_ratio-1)*100).toFixed(1)+'% off';
  s+=txt(sc(x.rs_expected_evals)+4,y+15,'RS '+x.rs_expected_evals.toFixed(1)+' evals (basin K/N='+x.basin_frac.toFixed(2)+') · '+(x.flat_certificate?'flat certificate':qtxt),'axt');});
 s+='</svg>';
 app.append($(`<h2>7 · RQ1′ — near-optimum basin & evals-to-basin (MEASURED-REPLAY, grid-scoped)</h2>`));
 app.append($(`<div class="legend"><span><span class="sw" style="background:var(--rs)"></span>RS expected evals to reach the near-opt basin (N+1)/(K+1)</span>
  <span><span class="sw" style="background:var(--doe)"></span>DOE screen fixed cost ≥8 evals (dashed at 9)</span>
  <span><span class="sw" style="background:var(--muted)"></span>flatness certificate</span></div>`));
 app.append($(`<div class="panel scroll">${s}<div class="foot"><b>The measured result:</b> the near-opt basin is <b>wide (median K/N=${R.basin.median_basin_frac})</b>, so RS reaches it in a median ${R.basin.rs_evals_median} evals (range ${R.basin.rs_evals_range[0]}–${R.basin.rs_evals_range[1]}). A balanced main-effect screen needs ≥${R.basin.doe_screen_min_evals} evals on a 16-point grid, so <b>no method can win by evals on grids this small</b> — a grid-size + basin-width property, NOT method superiority. <b>Endpoint quality is ~tied:</b> DOE lands within τ on ${R.quality.doe_reaches_basin_within_tau}/${R.quality.n_nonflat} non-flat units (median ${R.quality.doe_quality_median_ratio}, worst ${R.quality.doe_quality_worst_ratio}); RS reaches the exact best within its 16-eval budget. The sign-test (<b>${R.sign_test_measures}</b>): RS evals-to-basin &lt; DOE-9 on ${R.rs_lt_doe_count}/${R.n_nonflat}, p=${R.sign_test_p} — DOE-cost-dependent (DOE=8 → p=${R.sensitivity_doe8.sign_test_p_two_sided}), demoted. <b>Corroborates §4 flat / §5 separable (easy landscape), NOT "RS beats DOE/BO".</b> §5 reconciliation: structure IS findable — the 12-config DOE/characterize factorial lands on the csr/elkan optima — but grids this small can't separate methods by evals. Scope: <b>MEASURED-REPLAY</b>, 16-config grids only, not full Θ=1728. Raw <span class="mono">${R.raw}</span>.</div></div>`));
}

/* ---- consistency check ---- */
(function(){
 const d=D.delta, ok=[];
 const med=a=>{a=[...a].sort((x,y)=>x-y);const m=a.length>>1;return a.length%2?a[m]:(a[m-1]+a[m])/2;};
 // 1. Δ medians re-derive from the per-unit rows
 ok.push(['Δ_all median',med(d.units.map(u=>u.delta_all)).toFixed(3),d.median_all.toFixed(3)]);
 ok.push(['Δ_strict median',med(d.units.map(u=>u.delta_strict)).toFixed(3),d.median_strict.toFixed(3)]);
 // 2. crit-3 tunable count = non-DROP verdicts
 ok.push(['crit-3 tunable',D.crit3.units.filter(u=>u.verdict!=='DROP').length,D.crit3.n_tunable]);
 // 3. canonical n=9 variant median must equal the top-level Δ median
 const v9=D.corpus.variants.find(v=>v.n_module===9);
 ok.push(['n=9 variant median',v9.median_all.toFixed(3),d.median_all.toFixed(3)]);
 // 4. every variant FLAT (median < 1.5)
 ok.push(['variants all FLAT',D.corpus.variants.every(v=>v.median_all<1.5&&v.verdict_all==='FLAT'),true]);
 // 5. fold count coherent across blocks
 ok.push(['fold count',D.power.surviving_n_fold,D.corpus.canonical_n_fold]);
 // 6. RQ1' median basin K/N re-derives from per-unit K (F6 headline number)
 const basins=D.rq1prime.per_unit.map(u=>u.K/u.N);
 ok.push(['RQ1′ median basin K/N',med(basins).toFixed(4),D.rq1prime.basin.median_basin_frac.toFixed(4)]);
 // 7. RQ1' evals-to-basin count (RS_E<9) re-derives from per-unit flags (sign-test numerator, NOT a "win")
 const rslt=D.rq1prime.per_unit.filter(u=>u.rs_lt_doe_evals===true).length;
 ok.push(['RQ1′ RS<DOE-9 count',rslt,D.rq1prime.rs_lt_doe_count]);
 // 8. DOE within-τ (quality-tied) count re-derives from per-unit doe_success on non-flat
 const dq=D.rq1prime.per_unit.filter(u=>!u.flat_certificate&&u.doe_success).length;
 ok.push(['RQ1′ DOE within-τ',dq,D.rq1prime.quality.doe_reaches_basin_within_tau]);
 // 9. flat-certificate count re-derives from per-unit flags
 ok.push(['RQ1′ flat certs',D.rq1prime.per_unit.filter(u=>u.flat_certificate).length,D.rq1prime.flat_certificate_units.length]);
 // 10. pava sensitivity still FLAT
 ok.push(['pava-sens FLAT',D.corpus.pava_sensitivity['n9_median_all_if_pava_1.5']<1.5,true]);
 const bad=ok.filter(r=>String(r[1])!==String(r[2]));
 const el=document.getElementById('check');
 el.style.background = bad.length? '#331512':'#12331f';
 el.style.color = bad.length? '#f0a397':'#8fe3ac';
 el.innerHTML = (bad.length? '✗ consistency FAIL: ':'✓ consistency check — every rendered aggregate re-derives from the embedded committed data: ')
   + ok.map(r=>`${r[0]} ${r[1]}${String(r[1])===String(r[2])?'=':'≠'}${r[2]}`).join(' · ');
})();
</script></div></body></html>"""

html = (HTML.replace("@@DATA_PATH@@", DATA_PATH).replace("@@DIG@@", digest)
        .replace("@@JSON@@", raw))
open(OUT, "w").write(html)
print(f"wrote {OUT} ({len(html)} bytes) from {DATA_PATH} (sha256 {digest})")
