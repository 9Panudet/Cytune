"""Busy-spin fixture (Step 0.2.3). Burns CPU for a wall-clock duration — unlike the
sleep kernel, which idles: the cycles counter must tell them apart."""
import time


def kernel(duration_s):
    deadline = time.perf_counter_ns() + int(duration_s * 1e9)
    x = 0
    while time.perf_counter_ns() < deadline:
        x += 1
    return x
