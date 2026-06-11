"""Synthetic contextual disturbance ground truth (Phase 3, D-025).

A seeded, known-by-construction conditional process standing in for the real
(trace, weather) data until the owner's files land (data/DATA_REQUEST.md). Because the
ground truth is known, quantile-box coverage is verifiable exactly — which is the point
of running the tightening machinery on synthetic data first.

Context c = (hour, burst_share s, T_dew_forecast, sigma_regime rho)  (guide 6.2 subset).
Disturbance channels per market hour:
    per-5-min-step heat deviations dQ_t [W]  (burst-driven, right-skewed)
    one dew-point forecast residual dD [K]
Historical records for box fitting are HOURLY summaries (max_t dQ_t, dD) — see D-026.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Context:
    hour: int            # 0..23
    burst_share: float   # 0..1 (job-mix burstiness)
    T_dew_fc: float      # degC
    sigma_regime: int    # 0 calm / 1 volatile humidity

    def features(self) -> np.ndarray:
        return np.array([
            np.sin(2 * np.pi * self.hour / 24.0),
            np.cos(2 * np.pi * self.hour / 24.0),
            self.burst_share,
            self.T_dew_fc,
            float(self.sigma_regime),
        ])


def _daytime(hour: int) -> float:
    return 1.0 if 8 <= hour < 20 else 0.3


def draw_step_heat_devs(rng: np.random.Generator, c: Context, Q_nom: float,
                        n_steps: int = 12) -> np.ndarray:
    """Per-step heat-load deviations [W] (peak-over-interval statistics, guide 6.2)."""
    base = rng.normal(0.0, 0.02 * Q_nom, size=n_steps)
    p_burst = 0.02 + 0.18 * c.burst_share * _daytime(c.hour)
    bursts = rng.uniform(0.05, 0.25, size=n_steps) * Q_nom * (rng.uniform(size=n_steps) < p_burst)
    return base + bursts


def draw_dew_residual(rng: np.random.Generator, c: Context) -> float:
    """Dew-point forecast residual [K]."""
    sigma = 0.4 + 0.8 * c.sigma_regime + 0.2 * _daytime(c.hour)
    return float(np.clip(rng.normal(0.0, sigma), -4.0, 4.0))


def hourly_record(rng: np.random.Generator, c: Context, Q_nom: float,
                  dt_s: float = 300.0) -> np.ndarray:
    """One historical record (D-026/D-031):
    (max-step heat deviation [W], positive-deviation energy over the hour [J],
     dew residual [K])."""
    devs = draw_step_heat_devs(rng, c, Q_nom)
    return np.array([devs.max(), np.maximum(devs, 0.0).sum() * dt_s,
                     draw_dew_residual(rng, c)])


def sample_context(rng: np.random.Generator) -> Context:
    return Context(
        hour=int(rng.integers(0, 24)),
        burst_share=float(rng.uniform(0.0, 1.0)),
        T_dew_fc=float(rng.uniform(10.0, 25.0)),
        sigma_regime=int(rng.integers(0, 2)),
    )


def generate_history(rng: np.random.Generator, Q_nom: float, n: int = 6000):
    """Historical (features, records) table for fitting ConditionalBoxes."""
    feats, recs = [], []
    for _ in range(n):
        c = sample_context(rng)
        feats.append(c.features())
        recs.append(hourly_record(rng, c, Q_nom))
    return np.array(feats), np.array(recs)
