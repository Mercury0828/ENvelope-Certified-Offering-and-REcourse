"""Real-data disturbance records: trace heat residuals + KIAH dew residuals (Phase 5).

Heat channel (Google Borg hall profile, D-034): forecast = 31-day hour-of-day
climatology of the 5-min mean profile (the best of the simple candidates tested:
std 73 kW vs 102/77 for lag-day/smoothed-lag); residuals used UNscaled — the
preprocessing's affine power map already places the hall in watts, and re-scaling to
the nominal would double-count (D-042). The PEAK channel is excluded from W(c) records
(non-simultaneity upper bound, data/README.md); it remains available for stress days.

Dew channel: day-ahead NWP-skill residual model N(0, 1.2 K [est, literature DA dew
RMSE]) clipped at ±4 K (D-042) — KIAH observations alone cannot reconstruct a real DA
forecast, and 24-h persistence (std 5.1 K measured) is a strawman that would triple the
residual and indict the product for a bad forecaster's sins. The measured persistence
residuals remain available via dew_residual_hours() for sensitivity work.

Hourly records (per D-026/D-031 schema): (max 5-min heat residual, positive-residual
energy, dew residual). Heat and dew sources are independent datasets paired by
hour-of-day with seeded random day-matching (D-042). Step-level residual vectors are
kept so simulations can replay REAL disturbance hours, not parametric draws.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..plant.params import REPO_ROOT

TRACE = REPO_ROOT / "data" / "traces" / "google2019a" / "hall_profile_5min.csv"
WEATHER = REPO_ROOT / "data" / "weather" / "kiah_asos_2023_2024.csv"


def heat_residual_hours(Q_nom_W: float) -> dict:
    """Per trace-hour 12-step heat residual vectors [W] + hour-of-day labels."""
    df = pd.read_csv(TRACE)
    df["hod"] = (df["t_s"] // 3600) % 24
    df["P_W"] = df["P_mean_kW"] * 1e3
    clim = df.groupby("hod")["P_W"].transform("mean")
    df["resid_W"] = df["P_W"] - clim          # unscaled (D-042)
    df["hour_idx"] = df["t_s"] // 3600
    vecs, hods = [], []
    for h, grp in df.groupby("hour_idx"):
        if len(grp) == 12:
            vecs.append(grp.sort_values("t_s")["resid_W"].to_numpy())
            hods.append(int(grp["hod"].iloc[0]))
    return {"vectors": np.array(vecs), "hod": np.array(hods)}


def dew_residual_hours() -> dict:
    """Hourly dew residuals [K] vs 24-h persistence + hour-of-day labels."""
    w = pd.read_csv(WEATHER, parse_dates=["valid"])
    w["local"] = w["valid"].dt.tz_localize("UTC").dt.tz_convert("US/Central")
    w = w.set_index("local").sort_index()
    dew = ((w["dwpf"] - 32) * 5 / 9).resample("1h").mean().interpolate()
    resid = (dew - dew.shift(24)).dropna()
    return {"resid": resid.to_numpy(), "hod": resid.index.hour.to_numpy()}


class RealRecordPool:
    """Joint (heat, dew) hourly records + replayable step vectors, by hour-of-day."""

    def __init__(self, Q_nom_W: float, dt_s: float = 300.0, seed: int = 0):
        self.heat = heat_residual_hours(Q_nom_W)
        self.dew = dew_residual_hours()
        self.dt = dt_s
        self.rng = np.random.default_rng(seed)

    DEW_SIGMA_K = 1.2      # [est] literature day-ahead dew-point RMSE (D-042)

    def _draw_dew(self) -> float:
        return float(np.clip(self.rng.normal(0.0, self.DEW_SIGMA_K), -4.0, 4.0))

    def regime_of(self, vec: np.ndarray) -> float:
        """Volatility-regime statistic of one hour: log1p(mean |step residual| [kW])."""
        return float(np.log1p(np.abs(vec).mean() / 1e3))

    def features_records(self, rich: bool = False) -> tuple[np.ndarray, np.ndarray]:
        """(features, records) table for ConditionalBoxes: one row per trace hour,
        dew residual from the NWP-skill model (D-042). rich=True appends the PREVIOUS
        hour's volatility regime (guide 6.2's 'recent forecast residuals' context,
        D-043) — regimes persist hour-to-hour, which is what makes them day-ahead
        usable as planned-job-mix proxies."""
        feats, recs = [], []
        vecs, hods = self.heat["vectors"], self.heat["hod"]
        for i in range(1, len(vecs)):
            f = [np.sin(2 * np.pi * hods[i] / 24), np.cos(2 * np.pi * hods[i] / 24)]
            if rich:
                f.append(self.regime_of(vecs[i - 1]))
            feats.append(f)
            recs.append([vecs[i].max(), np.maximum(vecs[i], 0).sum() * self.dt,
                         self._draw_dew()])
        return np.array(feats), np.array(recs)

    def regime_quantiles(self, qs=(0.25, 0.75)) -> list[float]:
        vals = [self.regime_of(v) for v in self.heat["vectors"]]
        return [float(np.quantile(vals, q)) for q in qs]

    @staticmethod
    def hour_features_rich(hod: int, regime: float) -> np.ndarray:
        return np.array([np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24),
                         regime])

    @staticmethod
    def hour_features(hod: int) -> np.ndarray:
        return np.array([np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24)])

    def draw_hour(self, hod: int) -> tuple[np.ndarray, float]:
        """Replay a disturbance hour: (REAL 12-step heat residual [W], NWP-skill dew
        residual [K])."""
        idx = np.where(self.heat["hod"] == hod)[0]
        vec = self.heat["vectors"][self.rng.choice(idx)]
        return vec, self._draw_dew()
