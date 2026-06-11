"""Loaders for the acquired real datasets (data/README.md) -> per-day model inputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..plant.params import REPO_ROOT

ERCOT = REPO_ROOT / "data" / "ercot"
WEATHER = REPO_ROOT / "data" / "weather"


def f_to_c(f):
    return (np.asarray(f, dtype=float) - 32.0) * 5.0 / 9.0


def load_day_prices(date: str) -> dict:
    """Hourly DAM SPP, hourly ECRS MCPC (pi^cap proxy), 15-min RTM SPP for one local day.

    Returns dict with 'dam_hourly' (24,), 'pi_cap_hourly' (24,), 'rtm_15min' (96,)
    in $/MWh ($/MW-h for capacity).
    """
    dam = pd.read_csv(ERCOT / "dam_spp_hb_houston_2023_2024.csv")
    dam["local"] = pd.to_datetime(dam["Interval Start"], utc=True).dt.tz_convert("US/Central")
    d = dam[dam["local"].dt.strftime("%Y-%m-%d") == date]
    dam_hourly = d.sort_values("local")["SPP"].to_numpy()

    rtm = pd.read_csv(ERCOT / "rtm_spp_hb_houston_2023_2024.csv")
    rtm["local"] = pd.to_datetime(rtm["Interval Start"], utc=True).dt.tz_convert("US/Central")
    r = rtm[rtm["local"].dt.strftime("%Y-%m-%d") == date]
    rtm_15 = r.sort_values("local")["SPP"].to_numpy()

    asd = pd.read_csv(ERCOT / "as_mcpc_2023_2024.csv")
    asd = asd[pd.to_datetime(asd["Delivery Date"]).dt.strftime("%Y-%m-%d") == date]
    asd = asd.sort_values("Hour Ending")
    pi_cap = asd["ECRS"].to_numpy(dtype=float)
    if np.isnan(pi_cap).all():            # pre-ECRS-launch dates: fall back to RRS
        pi_cap = asd["RRS"].to_numpy(dtype=float)

    if not (len(dam_hourly) == 24 and len(pi_cap) == 24 and len(rtm_15) == 96):
        raise ValueError(f"incomplete market day {date}: "
                         f"{len(dam_hourly)}/{len(pi_cap)}/{len(rtm_15)}")
    return {"dam_hourly": dam_hourly, "pi_cap_hourly": pi_cap, "rtm_15min": rtm_15}


def load_day_weather(date: str) -> dict:
    """Hourly T_amb / T_dew observations [degC] for one local (US/Central) day from
    KIAH ASOS, plus the REAL day-ahead NWP dew forecast and its residual where the
    forecast archive covers the date (2024+, D-050)."""
    w = pd.read_csv(WEATHER / "kiah_asos_2023_2024.csv", parse_dates=["valid"])
    w["local"] = w["valid"].dt.tz_localize("UTC").dt.tz_convert("US/Central")
    d = w[w["local"].dt.strftime("%Y-%m-%d") == date].sort_values("local")
    hourly = d.groupby(d["local"].dt.hour).agg(tmpf=("tmpf", "mean"),
                                               dwpf=("dwpf", "mean"))
    hourly = hourly.reindex(range(24)).interpolate(limit_direction="both")
    out = {"T_amb_hourly": f_to_c(hourly["tmpf"].to_numpy()),
           "T_dew_hourly": f_to_c(hourly["dwpf"].to_numpy())}

    fc_path = WEATHER / "kiah_dew_forecast_2024.csv"
    if fc_path.exists():
        fc = pd.read_csv(fc_path, index_col=0, parse_dates=True).reset_index(names="time")
        fc["local"] = fc["time"].dt.tz_convert("US/Central")
        f = fc[fc["local"].dt.strftime("%Y-%m-%d") == date].sort_values("local")
        if len(f) >= 20:
            g = f.groupby(f["local"].dt.hour)["dew_fc_day1_C"].mean()
            g = g.reindex(range(24)).interpolate(limit_direction="both")
            out["T_dew_fc_hourly"] = g.to_numpy()
            out["dew_resid_hourly"] = out["T_dew_hourly"] - out["T_dew_fc_hourly"]
    if "T_dew_fc_hourly" not in out:
        out["T_dew_fc_hourly"] = out["T_dew_hourly"]      # pre-archive fallback
        out["dew_resid_hourly"] = np.zeros(24)
    return out


def rtm_to_5min(rtm_15: np.ndarray) -> np.ndarray:
    """Hold each 15-min settlement price over its three 5-min steps -> (288,)."""
    return np.repeat(np.asarray(rtm_15, dtype=float), 3)
