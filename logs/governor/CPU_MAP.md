# CPU_MAP — core allocation for measurement (Step 0.2.1; roadmap §1.2/§5.1)

Probed 2026-06-11 (sysfs; raw values below). CPU: **Intel Core i3-10100F @ 3.60GHz**
(matches the §1.2 hardware budget), 4 cores / 8 threads, single package.

## SMT topology (probed, not assumed)

| Logical CPU | thread_siblings_list | Physical core |
|---|---|---|
| 0, 4 | `0,4` | core 0 |
| 1, 5 | `1,5` | core 1 |
| 2, 6 | `2,6` | core 2 |
| 3, 7 | `3,7` | core 3 |

## Allocation (binding for every container invocation)

| Role | cpuset | Notes |
|---|---|---|
| Orchestrator + 2 compile workers | `--cpuset-cpus=0,1,4,5` | cores 0–1 + their SMT siblings (§1.2) |
| OS / desktop slack | cpus 2, 6 | nothing of ours pinned here; absorbs host background load |
| **Measurement** | `--cpuset-cpus=3` | one benchmark at a time (§5.1); enforced by `scripts/measure_wrap.sh` |
| SMT sibling of measurement core | cpu 7 — **idle-guaranteed**, policy isolcpus-aware (D4) | With `isolcpus=3,7` (adopted post-0.2.4 red gate): cpu7 stays **online+isolated** — scheduler never uses it, and offlining it de-registers coretemp's "Core 3" channel. Without isolcpus: offline. `host_prep.sh` applies; wrapper verifies either state |

## Frequency-control state (set by host_prep.sh, verified by measure_wrap.sh)

- `intel_pstate/no_turbo = 1` (wrapper REFUSES otherwise — roadmap Step 0.2.1 check)
- `scaling_governor = performance` on all online CPUs (set via sysfs directly;
  kernel-tools/cpupower not installed — same kernel interface, recorded deviation)
- Held frequency is logged per invocation to `invocations.log` (§5.1 "documented in
  /logs/governor/").

## Probed baseline (unprepped host, 2026-06-11)

```
model name      : Intel(R) Core(TM) i3-10100F CPU @ 3.60GHz
no_turbo        : 0            (turbo ON -> wrapper refuses)
governor (cpu3) : schedutil
cpu3 cur freq   : 3102323 kHz
hwmon           : hwmon1=coretemp (temp1=Package id 0, temp2..5=Core 0..3); hwmon0 is a
                  peripheral battery sensor (ignored)
```

## Isolation level & accepted residual risk

taskset/cpuset is **soft** isolation: the kernel may still schedule other processes on
cpu 3. Mitigations in force: performance governor + no turbo (frequency invariance),
sibling offline (no SMT interference), one-benchmark-at-a-time, thermal/throttle
discard rule (§5.1), K-rep medians + IQR. Optional hardening, NOT adopted now
(requires grub edit + reboot; revisit only if pilot variance at 0.2.4 misses target):
`isolcpus=3,7 nohz_full=3 rcu_nocbs=3` kernel boot parameters.
