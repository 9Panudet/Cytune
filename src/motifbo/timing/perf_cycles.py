"""Self-process CPU-cycle counter via perf_event_open(2) — Step 0.2.3 (§5.1).

Counting event, USER-SPACE ONLY: exclude_kernel=1 is mandatory — at
kernel.perf_event_paranoid=2 unprivileged processes may not observe kernel cycles
(EACCES with no AVC; see logs/env/STEP_0.2.3_perf_feasibility.log). Recorded
semantics: cycle counts cover user-space execution of the timed region.

Requires (containers): the committed seccomp profile data/env/seccomp-perf-events.json
AND the host SELinux module motifbo_perf (scripts/host_perf_prep.sh). The default
candidate-containment profile keeps perf_event_open DENIED.
"""
import ctypes
import fcntl
import os
import struct

_SYS_perf_event_open = 298            # x86_64
_PERF_TYPE_HARDWARE = 0
_PERF_COUNT_HW_CPU_CYCLES = 0
_PERF_EVENT_IOC_ENABLE = 0x2400
# perf_event_attr (128 bytes): type, size, config, sample_period, sample_type,
# read_format, flags. flags = disabled(bit0) | exclude_kernel(bit5) | exclude_hv(bit6).
_ATTR = struct.pack("IIQQQQQ", _PERF_TYPE_HARDWARE, 128, _PERF_COUNT_HW_CPU_CYCLES,
                    0, 0, 0, 1 | 32 | 64) + b"\x00" * 80

_libc = ctypes.CDLL(None, use_errno=True)


class PerfCycleCounter:
    """Counts this process's user-space CPU cycles. Use as a context manager."""

    def __init__(self):
        fd = _libc.syscall(_SYS_perf_event_open, _ATTR, 0, -1, -1, 0)
        if fd < 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err) + (
                " — perf_event_open denied; cycle runs need the seccomp profile "
                "data/env/seccomp-perf-events.json and the motifbo_perf SELinux "
                "module (logs/env/STEP_0.2.3_perf_feasibility.log)"))
        self._fd = fd
        fcntl.ioctl(fd, _PERF_EVENT_IOC_ENABLE, 0)

    def read(self):
        return int.from_bytes(os.read(self._fd, 8), "little")

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
