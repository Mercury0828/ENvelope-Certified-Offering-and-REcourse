"""Data acquisition — archived day-ahead dew-point forecasts for KIAH (Open-Meteo
previous-runs API; owner-approved item 3 of the pre-paper backlog, D-050).

`dew_point_2m_previous_day1` is the value the model forecast ~24 h earlier for each
hour — a REAL day-ahead forecast archive (available from 2024). Paired with KIAH ASOS
observations it yields real DA forecast residuals, replacing the N(0, 1.2 K) [est]
model of D-042. Writes data/weather/kiah_dew_forecast_2024.csv + residual stats.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json
import time
import urllib.request

import numpy as np
import pandas as pd

from encore.utils.provenance import write_manifest

OUT = REPO / "data" / "weather"
LAT, LON = 29.9844, -95.3414     # KIAH


def fetch_chunk(start, end):
    url = ("https://previous-runs-api.open-meteo.com/v1/forecast"
           f"?latitude={LAT}&longitude={LON}"
           "&hourly=dew_point_2m_previous_day1"
           f"&start_date={start}&end_date={end}&timezone=UTC")
    req = urllib.request.Request(url, headers={"User-Agent": "encore-research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return pd.DataFrame({"time": d["hourly"]["time"],
                         "dew_fc_day1_C": d["hourly"]["dew_point_2m_previous_day1"]})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chunks = []
    months = pd.date_range("2024-01-01", "2025-01-01", freq="MS")
    for a, b in zip(months[:-1], months[1:]):
        end = (b - pd.Timedelta(days=1)).date()
        chunks.append(fetch_chunk(a.date(), end))
        print(f"{a.date()}..{end}: {len(chunks[-1])} rows")
        time.sleep(1.0)                      # be polite to the free API
    fc = pd.concat(chunks, ignore_index=True)
    fc["time"] = pd.to_datetime(fc["time"], utc=True)
    fc = fc.dropna().set_index("time")

    obs = pd.read_csv(OUT / "kiah_asos_2023_2024.csv", parse_dates=["valid"])
    dew_obs = ((obs.set_index(obs["valid"].dt.tz_localize("UTC"))["dwpf"] - 32) * 5 / 9)
    dew_obs = dew_obs.resample("1h").mean().interpolate()

    df = fc.join(dew_obs.rename("dew_obs_C"), how="inner").dropna()
    df["resid_K"] = df["dew_obs_C"] - df["dew_fc_day1_C"]
    df.to_csv(OUT / "kiah_dew_forecast_2024.csv")
    stats = {"n_hours": int(len(df)),
             "resid_std_K": float(df["resid_K"].std()),
             "resid_bias_K": float(df["resid_K"].mean()),
             "resid_q95_K": float(df["resid_K"].quantile(0.95)),
             "resid_q99_K": float(df["resid_K"].quantile(0.99))}
    print(json.dumps(stats, indent=2))
    write_manifest(OUT / "provenance_dew_forecast.json", seed=None,
                   extra={"experiment": "fetch_nwp_dew",
                          "source": "open-meteo previous-runs API, dew_point_2m_previous_day1",
                          **stats})


if __name__ == "__main__":
    main()
