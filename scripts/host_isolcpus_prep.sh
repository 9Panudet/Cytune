#!/usr/bin/env bash
# Pre-registered isolation hardening (logs/governor/CPU_MAP.md; trigger fired at the
# 0.2.4 pilot red gate — see results/prereg/PREREG_PILOT2.md).
# RUN BY THE HUMAN WITH SUDO, then REBOOT, then: sudo bash scripts/host_prep.sh
# Rollback: sudo grubby --update-kernel=ALL --remove-args="isolcpus=3,7 nohz_full=3 rcu_nocbs=3"
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "ERROR: run with sudo"; exit 1; }

grubby --update-kernel=ALL --args="isolcpus=3,7 nohz_full=3 rcu_nocbs=3"
echo "--- kernel args now ---"
grubby --info=DEFAULT | grep -m1 '^args'
echo "REBOOT REQUIRED. After reboot:"
echo "  1. sudo bash scripts/host_prep.sh        (volatile settings re-applied)"
echo "  2. cat /sys/devices/system/cpu/isolated  (must print 3,7)"
