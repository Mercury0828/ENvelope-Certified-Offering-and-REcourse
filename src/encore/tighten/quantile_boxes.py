"""Conditional (1-eps) quantile sets W(c) via k-NN (guide 6.2, D-026/D-031).

Historical records are HOURLY summaries of the disturbance channels:
    w_max = max over the hour's 5-min steps of the heat-load deviation [W]
    E_pos = sum of positive heat deviations x dt over the hour [J]
    w_D   = dew-point forecast residual for the hour [K]

W(c) is the POLYTOPE {w: w_t <= w_max_bar for all t, sum max(w_t,0) dt <= E_bar} x
{dew <= w_D_bar} — the energy-budget face encodes that bursts are short, which is what
keeps tube margins from treating a burst bound as a persistent load (D-031; a pure box
on w_max collapsed the tightened envelope, documented in results/phase3).

Construction (D-031/D-033): a raw k-NN per-face quantile box gives the SHAPE; a
localized split-conformal step then scales it: history is split into fit/calibration
halves, the box is fit on the fit half, and the multiplicative inflation lambda* is the
ceil((1-eps)(n+1))-th smallest inflation needed to contain each of the n nearest
calibration records. This removes the k-NN edge-smoothing bias that made raw quantile
boxes under-cover in bursty contexts (0.85 observed vs 0.90 target) using DATA ONLY —
the same recipe applies unchanged to the real datasets.
Containment of one hourly record == containment of the hour's disturbance trajectory.
Negative heat deviations are small-noise (right-skewed process); the symmetric per-step
bound w_max_bar dominates their magnitude at the levels used (logged, D-031).

Data-agnostic: refits on real (context, record) tables when datasets land.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Box:
    w_Q_hi: float          # per-step heat deviation bound [W]
    E_hi: float            # positive-deviation energy budget [J]
    w_D_hi: float          # dew residual bound [K]

    @property
    def w_Q_sym(self) -> float:
        return max(0.0, self.w_Q_hi)

    @property
    def w_D(self) -> float:
        return max(0.0, self.w_D_hi)

    def contains(self, rec_Q: float, rec_E: float, rec_D: float) -> bool:
        return (rec_Q <= self.w_Q_hi) and (rec_E <= self.E_hi) and (rec_D <= self.w_D_hi)


class ConditionalBoxes:
    """k-NN conditional quantile sets over (heat-max, energy, dew-residual) records,
    with localized split-conformal calibration (D-033)."""

    def __init__(self, features: np.ndarray, records: np.ndarray, eps: float = 0.1,
                 k: int = 150, k_cal: int = 300, split_seed: int = 0):
        if features.shape[0] != records.shape[0] or records.shape[1] != 3:
            raise ValueError("features (N,f) and records (N,3) required")
        X = np.asarray(features, dtype=float)
        Y = np.asarray(records, dtype=float)
        rng = np.random.default_rng(split_seed)
        perm = rng.permutation(X.shape[0])
        half = X.shape[0] // 2
        self.Xf, self.Yf = X[perm[:half]], Y[perm[:half]]       # fit half
        self.Xc, self.Yc = X[perm[half:]], Y[perm[half:]]       # calibration half
        self.eps = eps
        self.k = min(k, half)
        self.k_cal = min(k_cal, X.shape[0] - half)
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-12

    def _neighbors(self, X: np.ndarray, c_feat: np.ndarray, k: int) -> np.ndarray:
        z = (X - self.mu) / self.sd
        zq = (np.asarray(c_feat, dtype=float) - self.mu) / self.sd
        d2 = ((z - zq) ** 2).sum(axis=1)
        return np.argpartition(d2, k - 1)[:k]

    def _box_from(self, Y: np.ndarray) -> Box:
        lvl = 1 - self.eps / 4
        return Box(
            w_Q_hi=float(np.quantile(Y[:, 0], lvl)),
            E_hi=float(np.quantile(Y[:, 1], lvl)),
            w_D_hi=float(np.quantile(Y[:, 2], lvl)),
        )

    def raw_box(self, c_feat: np.ndarray) -> Box:
        """Uncalibrated k-NN quantile box (shape only)."""
        return self._box_from(self.Yf[self._neighbors(self.Xf, c_feat, self.k)])

    def _calibrate(self, shape: Box, Yc_local: np.ndarray) -> Box:
        """Per-face conformal inflation at level 1 - eps/3 (Bonferroni -> >= 1 - eps)."""
        denom = np.array([max(shape.w_Q_hi, 1e3), max(shape.E_hi, 1e5),
                          max(shape.w_D_hi, 1e-2)])
        n = Yc_local.shape[0]
        rank = min(n - 1, int(np.ceil((1 - self.eps / 3) * (n + 1))) - 1)
        lams = []
        for j in range(3):
            scores = np.sort(np.maximum(Yc_local[:, j], 0.0) / denom[j])
            lams.append(max(1.0, float(scores[rank])))
        return Box(w_Q_hi=denom[0] * lams[0], E_hi=denom[1] * lams[1],
                   w_D_hi=denom[2] * lams[2])

    def box(self, c_feat: np.ndarray) -> Box:
        """Conformally calibrated conditional box (per-face, localized)."""
        shape = self.raw_box(c_feat)
        idx = self._neighbors(self.Xc, c_feat, self.k_cal)
        return self._calibrate(shape, self.Yc[idx])

    def unconditional_box(self) -> Box:
        """Pooled-marginal comparator (the no-context baseline for F1), conformally
        calibrated on the pooled calibration half."""
        return self._calibrate(self._box_from(self.Yf), self.Yc)
