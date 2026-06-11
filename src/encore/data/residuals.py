"""Real-data disturbance records (Phase 5/6; reworked per D-046/D-050).

Heat channel: a hall power profile from a real cluster trace —
  source="borg":    Google Borg 2019 cell-a (mixed batch, deliberately volatile)
  source="alibaba": Alibaba PAI GPU cluster 2020 (dedicated ML training/inference —
                    the owner-approved "real training hall", D-050)
Forecast = hour-of-day climatology fit CAUSALLY on the first 2/3 of trace days; the
day-block split (fit = first 2/3, eval = last 1/3) removes validation circularity.

Dew channel (D-050, replaces D-042's N(0,1.2 K) [est] model): REAL day-ahead NWP
forecast residuals for KIAH (Open-Meteo previous-runs archive, 2024; measured std
2.01 K, q95 3.7 K), sampled conditioned on hour-of-day.

Hourly records per D-026/D-031: (max 5-min heat residual, positive-residual energy,
dew residual). Step-level vectors are kept so simulations replay REAL hours.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..plant.params import REPO_ROOT

TRACES = {
    "borg": REPO_ROOT / "data" / "traces" / "google2019a" / "hall_profile_5min.csv",
    "alibaba": REPO_ROOT / "data" / "traces" / "alibaba2020" / "hall_profile_5min.csv",
}
WEATHER = REPO_ROOT / "data" / "weather" / "kiah_asos_2023_2024.csv"
DEW_FC = REPO_ROOT / "data" / "weather" / "kiah_dew_forecast_2024.csv"


def heat_residual_hours(source: str = "borg",
                        days: tuple[int, int] | None = None) -> dict:
    """Per trace-hour 12-step heat residual vectors [W] + hour-of-day labels.
    Climatology (the day-ahead forecast model) is fit on the first 2/3 of trace days
    only (causal); `days` filters which days' hours are returned."""
    df = pd.read_csv(TRACES[source])
    df["hod"] = (df["t_s"] // 3600) % 24
    df["P_W"] = df["P_mean_kW"] * 1e3
    df["day"] = df["t_s"] // 86400
    n_days = int(df["day"].max()) + 1
    clim_days = (2 * n_days) // 3
    clim_map = df[df["day"] < clim_days].groupby("hod")["P_W"].mean()
    df["resid_W"] = df["P_W"] - df["hod"].map(clim_map)
    df["hour_idx"] = df["t_s"] // 3600
    if days == "fit":
        df = df[df["day"] < clim_days]
    elif days == "eval":
        df = df[df["day"] >= clim_days]
    vecs, hods = [], []
    for h, grp in df.groupby("hour_idx"):
        if len(grp) == 12:
            vecs.append(grp.sort_values("t_s")["resid_W"].to_numpy())
            hods.append(int(grp["hod"].iloc[0]))
    return {"vectors": np.array(vecs), "hod": np.array(hods),
            "n_days": n_days, "clim_days": clim_days}


def dew_residual_pool() -> dict:
    """REAL day-ahead dew forecast residuals [K] + hour-of-day labels (D-050)."""
    df = pd.read_csv(DEW_FC, index_col=0, parse_dates=True)
    return {"resid": df["resid_K"].to_numpy(),
            "hod": df.index.hour.to_numpy()}


class RealRecordPool:
    """Joint (heat, dew) hourly records + replayable step vectors, by hour-of-day.

    role: "fit" (first 2/3 of trace days — calibration/offering), "eval" (last 1/3 —
    held-out closed-loop replay), "all". scale: workload-volatility factor kappa
    (D-047) applied to heat vectors; fit and replay must share it.
    """

    def __init__(self, Q_nom_W: float, dt_s: float = 300.0, seed: int = 0,
                 role: str = "all", scale: float = 1.0, source: str = "borg"):
        days = {"fit": "fit", "eval": "eval", "all": None}[role]
        self.heat = heat_residual_hours(source, days=days)
        if scale != 1.0:
            self.heat["vectors"] = self.heat["vectors"] * float(scale)
        self.dew = dew_residual_pool()
        self.dt = dt_s
        self.rng = np.random.default_rng(seed)

    def _draw_dew(self, hod: int | None = None) -> float:
        pool = self.dew["resid"] if hod is None else \
            self.dew["resid"][self.dew["hod"] == hod]
        return float(self.rng.choice(pool))

    def regime_of(self, vec: np.ndarray) -> float:
        return float(np.log1p(np.abs(vec).mean() / 1e3))

    def features_records(self, rich: bool = False) -> tuple[np.ndarray, np.ndarray]:
        feats, recs = [], []
        vecs, hods = self.heat["vectors"], self.heat["hod"]
        for i in range(1, len(vecs)):
            f = [np.sin(2 * np.pi * hods[i] / 24), np.cos(2 * np.pi * hods[i] / 24)]
            if rich:
                f.append(self.regime_of(vecs[i - 1]))
            feats.append(f)
            recs.append([vecs[i].max(), np.maximum(vecs[i], 0).sum() * self.dt,
                         self._draw_dew(int(hods[i]))])
        return np.array(feats), np.array(recs)

    def regime_quantiles(self, qs=(0.25, 0.75)) -> list[float]:
        vals = [self.regime_of(v) for v in self.heat["vectors"]]
        return [float(np.quantile(vals, q)) for q in qs]

    @staticmethod
    def hour_features(hod: int) -> np.ndarray:
        return np.array([np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24)])

    @staticmethod
    def hour_features_rich(hod: int, regime: float) -> np.ndarray:
        return np.array([np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24),
                         regime])

    def draw_hour(self, hod: int) -> tuple[np.ndarray, float]:
        """Replay a disturbance hour: (REAL heat residual steps [W], REAL dew residual [K])."""
        idx = np.where(self.heat["hod"] == hod)[0]
        vec = self.heat["vectors"][self.rng.choice(idx)]
        return vec, self._draw_dew(hod)
