# Motif+BO pinned environment — pinning policy: roadmap §1.3 (digest, never tag).
# Digest recorded at the one-time pull, Step 0.1.1 (2026-06-11). Full digest set
# (OCI index, amd64 manifest, image ID, layers) + evidence: /data/env/IMAGE_DIGEST.
# The tag before '@' is documentation only; the digest governs resolution.
FROM docker.io/library/ubuntu:24.04@sha256:023f8a753c22258c9fe2d0005a7d28258038da7d620e9f93e9ad78aa266f9f11

# ---- Step 0.1.2: GCC 13.x via apt version pin (roadmap §1.3; TOOLCHAIN.lock) ----
# Versions discovered from the pinned base on 2026-06-11 (apt-cache policy).
# The preferences file makes the pin binding for all later apt operations; the
# explicit =version below makes this install fail loudly if the archive drops it.
# libc6-dev is explicit (pinned) because --no-install-recommends suppresses it and
# gcc cannot compile hosted C without libc headers.
COPY data/env/apt-pin-gcc13.pref /etc/apt/preferences.d/motifbo-gcc13
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        gcc-13=13.3.0-6ubuntu2~24.04.1 \
        gcc=4:13.2.0-7ubuntu1 \
        libc6-dev=2.39-0ubuntu8.7 \
    && rm -rf /var/lib/apt/lists/*

# ---- Step 0.1.3: Python 3.12.x pinned via apt; deps via hash-pinned lock (§1.3) ----
COPY data/env/apt-pin-python312.pref /etc/apt/preferences.d/motifbo-python312
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3.12=3.12.3-1ubuntu0.13 \
        python3.12-venv=3.12.3-1ubuntu0.13 \
        python3.12-dev=3.12.3-1ubuntu0.13 \
    && rm -rf /var/lib/apt/lists/*

# Hash-pinned Python deps (requirements.lock resolved in-image; see data/env/). pip
# refuses anything whose sha256 differs from the lock (--require-hashes).
COPY data/env/requirements.lock /opt/requirements.lock
RUN python3.12 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /opt/requirements.lock
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH

# ---- Step 1.1.1 (Phase-0->Phase-1 image transition X->X'): C++ toolchain — ADDITIVE ----
# Required so C++ Cython corpus units build (sklearn tree/_tree,_splitter,_criterion;
# cluster/_dbscan_inner,_hierarchical_fast — roadmap §4.3). Versions EXACTLY match the pinned
# gcc-13 (13.3.0-6ubuntu2~24.04.1): cc1plus ships from the same gcc-13 family. This layer is
# APPENDED LAST so every layer above (gcc/cc1/libc6-dev/libasan, python3.12, pip deps) stays
# cache-identical -> cc1/gcc/libasan.so/python3.12 byte-identity is structurally preserved and
# PROVEN post-rebuild (condition 2). The gcc-13 apt preference pin COPYed above is still active.
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        g++-13=13.3.0-6ubuntu2~24.04.1 \
        libstdc++-13-dev=13.3.0-6ubuntu2~24.04.1 \
    && rm -rf /var/lib/apt/lists/*
