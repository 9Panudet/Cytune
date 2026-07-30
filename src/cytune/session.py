"""cytune session — workspace, ingest, and the three measured phases (roadmap §8.1 steps 1/2/4).

A session owns one workspace directory laid out exactly like the study's, so the SAME container
entrypoints work unchanged:

    <workspace>/_kernels/<name>/{kernel.pyx, driver.py}   the vendored module under test
    <workspace>/<name>/{build_manifest.jsonl, oracle.json, golden.npy, table.jsonl, ...}   raw

Every measurement lands in table.jsonl before anything is claimed about it, so every number in the
certificate has a raw pointer and a recompute path — the same rule the study lives under.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess

from . import rig


class IngestError(RuntimeError):
    pass


def _last_json(text):
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


class Session:
    def __init__(self, workspace, name, mode, mode_detail, log_path=None, target_ms=65.0):
        self.workspace = os.path.abspath(workspace)
        self.name = name
        self.mode = mode
        self.mode_detail = mode_detail
        self.target_ms = target_ms
        self.kdir = os.path.join(self.workspace, "_kernels", name)
        self.odir = os.path.join(self.workspace, name)
        self.log_path = log_path or os.path.join(self.workspace, f"{name}.log")
        os.makedirs(self.kdir, exist_ok=True)
        os.makedirs(self.odir, exist_ok=True)
        self.transcript = []

    # ---------------------------------------------------------------- plumbing
    def _run(self, cmd, phase):
        with open(self.log_path, "a") as f:
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            r = subprocess.run(cmd, capture_output=True, text=True)
            f.write(r.stdout)
            f.write(r.stderr)
        self.transcript.append({"phase": phase, "cmd": cmd, "rc": r.returncode})
        payload = _last_json(r.stdout)
        if r.returncode != 0 or payload is None:
            tail = (r.stdout + r.stderr)[-800:]
            raise IngestError(f"{phase} failed (rc={r.returncode}): {tail}")
        return payload

    def _ids_arg(self, ids):
        return "probe" if ids == "probe" else ",".join(str(i) for i in ids)

    # ------------------------------------------------------------------ ingest
    def vendor(self, pyx_path, driver_path):
        """Copy the user's module + driver into the workspace. We never build in-place: the build
        writes .c/.so next to sources and calibration may rewrite the driver knob, and doing either
        to a user's working tree would be rude and irreversible."""
        for src, dst in ((pyx_path, "kernel.pyx"), (driver_path, "driver.py")):
            if not os.path.exists(src):
                raise IngestError(f"not found: {src}")
            shutil.copy2(src, os.path.join(self.kdir, dst))
        missing = self._driver_contract_gaps(driver_path)
        if missing:
            raise IngestError(
                "driver does not satisfy the measurement contract, missing: " + ", ".join(missing) +
                "\n  a cytune driver must define: make_inputs(seed) -> inputs, call(mod, inputs) -> "
                "result, canon(result) -> numpy array, and OUTPUT_CLASS in {float,int,bool}")
        return {"pyx": os.path.abspath(pyx_path), "driver": os.path.abspath(driver_path),
                "vendored_to": self.kdir}

    @staticmethod
    def _driver_contract_gaps(driver_path):
        """Checked by source inspection, not import: importing a stranger's driver on the host runs
        arbitrary code outside the container. The container is where their code is allowed to run."""
        src = open(driver_path).read()
        gaps = [n for n in ("make_inputs", "call", "canon") if f"def {n}" not in src]
        if "OUTPUT_CLASS" not in src:
            gaps.append("OUTPUT_CLASS")
        return gaps

    def build(self, ids):
        return self._run(rig.build_cmd(self.workspace, self.name, self._ids_arg(ids)), "build")

    def golden(self):
        cmd = rig.measure_cmd(self.workspace, self.name, self.mode, "golden", [self.target_ms])
        res = self._run(cmd, "golden")
        if not res.get("ok"):
            raise IngestError(f"{res.get('error')} — {res.get('hint', '')}")
        return res

    def measure(self, ids):
        cmd = rig.measure_cmd(self.workspace, self.name, self.mode, "measure", [self._ids_arg(ids)])
        return self._run(cmd, "measure")

    def endpoint(self, ids):
        cmd = rig.measure_cmd(self.workspace, self.name, self.mode, "endpoint", [self._ids_arg(ids)])
        return self._run(cmd, "endpoint")

    # ------------------------------------------------------- pure compute (no timing)
    def features(self):
        return self._run(rig.compute_cmd(self.workspace, self.name, "features", []), "features")

    def screen_plan(self, budget):
        return self._run(rig.compute_cmd(self.workspace, self.name, "screen", [budget]), "screen")

    def walk_plan(self, budget, allow_fast_math=False):
        args = [budget] + (["--allow-fast-math"] if allow_fast_math else [])
        return self._run(rig.compute_cmd(self.workspace, self.name, "walk", args), "walk")

    # ------------------------------------------------------------------- state
    def table_rows(self):
        p = os.path.join(self.odir, "table.jsonl")
        if not os.path.exists(p):
            return {}
        out = {}
        for line in open(p):
            r = json.loads(line)
            out[r["config_id"]] = r
        return out

    def feasible_medians(self):
        return {cid: r["screen"]["median_ns"] for cid, r in self.table_rows().items()
                if r.get("feasible") and r.get("screen")}

    @property
    def table_path(self):
        return os.path.join(self.odir, "table.jsonl")
