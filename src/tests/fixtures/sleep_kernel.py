"""Sleep-kernel fixture (Step 0.2.2 TDD; roadmap §5.1 / §4.4 timing-region rules).

Module import deliberately sleeps IMPORT_SLEEP_S: the harness must never time the
import ("no bare imports timed, ever"). The kernel sleeps a caller-chosen duration —
the only thing a correctly-placed timing region may measure.
"""
import time

IMPORT_SLEEP_S = 0.100
time.sleep(IMPORT_SLEEP_S)  # slow import — MUST stay outside any timed region


def kernel(duration_s, count_file=None):
    if count_file is not None:  # call-counting for warmup-discipline tests
        with open(count_file, "a") as fh:
            fh.write("x\n")
    time.sleep(duration_s)
