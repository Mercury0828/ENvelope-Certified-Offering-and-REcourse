"""Small statistics/reproducibility helpers (D-046)."""

from __future__ import annotations

import zlib

from scipy.stats import beta


def stable_seed(*parts) -> int:
    """Deterministic cross-process seed from arbitrary parts.

    Python's built-in hash() is salted per process (PYTHONHASHSEED), which silently
    made every experiment that seeded with hash((date, seed)) non-reproducible across
    runs — caught in the pre-paper audit (D-046). CRC32 is stable everywhere.
    """
    return zlib.crc32("|".join(str(p) for p in parts).encode()) & 0x7FFFFFFF


def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Exact binomial CI for k successes in n trials."""
    if n == 0:
        return 0.0, 1.0
    a = (1 - conf) / 2
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a, k + 1, n - k))
    return lo, hi
