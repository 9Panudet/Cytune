# HOST_NOTES — Fedora host mechanics (roadmap §1.3 container is unchanged by anything here)

Scope: host-side facts and fixes only. The pinned environment is the Podman container
(`ubuntu:24.04@sha256:<digest>`, recorded in `IMAGE_DIGEST` at Step 0.1.1). Nothing in this
file alters the container pinning policy.

## Host facts (probed 2026-06-11T00:47Z, Step 0.1.1)

| Item | Value | Evidence |
|---|---|---|
| OS | Fedora Linux 44 (Xfce spin) | `/etc/os-release` |
| Kernel | 6.19.10-300.fc44.x86_64 | `uname -r` |
| SELinux | **Enforcing** (`/sys/fs/selinux/enforce` = 1) | read 2026-06-11 |
| cgroups | **v2** (unified; root controllers: cpuset cpu io memory hugetlb pids rdma misc dmem) | `/sys/fs/cgroup/cgroup.controllers` |
| systemd user delegation (uid 1000) | `cpuset cpu io memory pids` (after delegation fix, verified 2026-06-11) | `/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/cgroup.controllers` |
| Container tooling | **podman 5.8.2** (rootless=true, runtime=crun, storage=overlay, cgroups v2) — installed by human 2026-06-11, resolving blocker B-0.1.1-a | `podman info`, 2026-06-11 |

## BLOCKER B-0.1.1-a — RESOLVED 2026-06-11

podman was not installed at first probe. Human ran `sudo dnf install -y podman`
(→ podman 5.8.2) and applied the systemd user-delegation drop-in
(`/etc/systemd/system/user@.service.d/delegate.conf`, `Delegate=cpu cpuset io memory pids`)
followed by logout/login. Both re-verified by the orchestrator (table above).

## Delegation status (verified 2026-06-11)

- **memory**: delegated; rootless limit verified against the pinned digest:
  `podman run --rm --memory=512m docker.io/library/ubuntu@sha256:023f8a75... cat /sys/fs/cgroup/memory.max`
  → `536870912` (512 MiB). PASS. Evidence: `/logs/env/STEP_0.1.1_build_identity.log` §4.
- **cpuset**: delegated after the drop-in fix (controllers file now lists `cpuset`).
  Needed by rootless `--cpuset-cpus` for measurement-core pinning (Step 0.2.1).

## Measurement-rig host mechanics (Step 0.2.1)

- **kernel-tools/cpupower NOT installed** → `scripts/host_prep.sh` sets the performance
  governor by writing `scaling_governor` sysfs files directly (the same kernel
  interface cpupower wraps). No extra root install needed. Recorded deviation from the
  mission note "(package: kernel-tools)".
- **lm_sensors NOT installed** → `scripts/thermal_log.sh` reads coretemp via
  `/sys/class/hwmon` directly (same data source `sensors` parses). Recorded deviation.
- **SMT sibling idle-policy (revised at D4)**: with `isolcpus=3,7` boot args (adopted
  after the 0.2.4 pilot red gate, scripts/host_isolcpus_prep.sh), cpu7 stays
  **online+isolated**: the scheduler never places tasks there AND coretemp keeps the
  "Core 3" channel (offlining cpu7 de-registered it after the isolcpus reboot — D4).
  On a boot without isolcpus, host_prep falls back to offlining cpu7. The wrapper
  accepts either state (offline, or online with isolcpus covering 3 and 7).
- host_prep effects do NOT survive reboot; `measure_wrap.sh` re-verifies at every
  invocation and refuses with exit 78 + log entry otherwise (never assumes prep ran).

## SELinux bind-mount policy (standing rule)

SELinux stays **Enforcing** — never disabled. Every bind mount into a container gets a
private label `:Z`, e.g. `-v ./data:/data:Z`. Labels actually used per mount are recorded
here as they are introduced:

| Mount | Label | First used at Step |
|---|---|---|
| `-v ./data/env:/work:Z` (rw; lock resolution output) | `:Z` | 0.1.3 |
| `-v ./scripts:/probe:ro,Z` (probe scripts) | `:ro,Z` | 0.1.3 |
| `-v ./logs/env:/out:Z` (rw; probe raw outputs) | `:Z` | 0.1.5 |
