"""Provenance manifests: every experiment writes git hash, config hash, seed (guide 12)."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..plant.params import DEFAULT_CONFIG, REPO_ROOT, config_hash


def git_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else "no-commit-yet"
    except Exception:
        return "git-unavailable"


def manifest(seed: int | None = None, config_path=DEFAULT_CONFIG, extra: dict | None = None) -> dict:
    import numpy
    import scipy
    m = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_hash": git_hash(),
        "config_path": str(config_path),
        "config_sha256": config_hash(config_path),
        "seed": seed,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
    }
    if extra:
        m.update(extra)
    return m


def write_manifest(path: str | Path, seed: int | None = None, extra: dict | None = None) -> dict:
    m = manifest(seed=seed, extra=extra)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(m, indent=2), encoding="utf-8")
    return m
