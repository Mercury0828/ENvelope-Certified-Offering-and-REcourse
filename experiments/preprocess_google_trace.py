"""Data preprocessing — Google Borg 2019 (cell a) instance_usage -> 1 MW hall heat
profile (guide §9 recipe, owner-directed source switch D-034).

Input: 4 randomly-sharded parquet exports of the instance_usage table (~2.5M rows,
random sample of all (instance, 5-min window) records over the 31-day trace).
Aggregation: per 5-min window, the SUM of sampled normalized-CPU usage estimates the
fleet profile shape (row sampling is uniform, so the sum is proportional to fleet
usage; ~250-300 rows/window -> ~6% sampling noise, recorded). Mean profile from
average_usage.cpus; peak profile from maximum_usage.cpus (mean-of-instance-peaks is an
upper proxy for the hall peak — conservative for the Q-hat statistic).

Power map [est]: P_IT(t) = P_hall * (idle + (1-idle) * u(t)), idle = 0.3, u normalized
by the 99.9th percentile of the mean-profile sum. Outputs per-5-min mean AND peak kW
series for a 1 MW hall + burst-tail quantiles for overlay synthesis (replaces D-008's
placeholder magnitudes).
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json

import numpy as np
import pandas as pd

from encore.utils.provenance import write_manifest

D = REPO / "data" / "traces" / "google2019a"
WINDOW_US = 300_000_000
P_HALL_KW = 1000.0
IDLE_FRAC = 0.3            # [est] affine server power model


def main():
    frames = []
    for f in sorted(D.glob("instance_usage-*.parquet.gz")):
        df = pd.read_parquet(f, columns=["start_time", "average_usage", "maximum_usage"])
        frames.append(pd.DataFrame({
            "win": df["start_time"].to_numpy() // WINDOW_US,
            "cpu_avg": np.array([d["cpus"] if d else 0.0 for d in df["average_usage"]]),
            "cpu_max": np.array([d["cpus"] if d else 0.0 for d in df["maximum_usage"]]),
        }))
        print(f"{f.name}: {len(df)} rows")
    rows = pd.concat(frames, ignore_index=True)

    g = rows.groupby("win").agg(S_avg=("cpu_avg", "sum"), S_max=("cpu_max", "sum"),
                                n=("cpu_avg", "size")).reset_index()
    g = g[(g["win"] > 0) & (g["n"] > 50)].sort_values("win")   # drop boot/edge windows
    scale = np.quantile(g["S_avg"], 0.999)
    g["u_mean"] = np.clip(g["S_avg"] / scale, 0, 1.2)
    g["u_peak"] = np.clip(g["S_max"] / scale, 0, 2.0)
    g["P_mean_kW"] = P_HALL_KW * (IDLE_FRAC + (1 - IDLE_FRAC) * g["u_mean"])
    g["P_peak_kW"] = P_HALL_KW * (IDLE_FRAC + (1 - IDLE_FRAC) * g["u_peak"])
    g["t_s"] = g["win"] * 300

    out = g[["t_s", "n", "u_mean", "u_peak", "P_mean_kW", "P_peak_kW"]]
    out.to_csv(D / "hall_profile_5min.csv", index=False)

    burst_ratio = (g["P_peak_kW"] - g["P_mean_kW"]) / g["P_mean_kW"]
    tails = {f"q{q}": float(np.quantile(burst_ratio, q / 100))
             for q in (50, 90, 95, 99, 99.9)}
    stats = {
        "windows": int(len(g)),
        "days": float(len(g) * 300 / 86400),
        "rows_per_window_mean": float(g["n"].mean()),
        "sampling_noise_est": float(1 / np.sqrt(g["n"].mean())),
        "P_mean_kW_mean": float(out["P_mean_kW"].mean()),
        "P_mean_kW_minmax": [float(out["P_mean_kW"].min()), float(out["P_mean_kW"].max())],
        "burst_ratio_quantiles": tails,
        "idle_frac_est": IDLE_FRAC,
    }
    (D / "hall_profile_stats.json").write_text(json.dumps(stats, indent=2),
                                               encoding="utf-8")
    write_manifest(D / "provenance_google_trace.json", seed=None,
                   extra={"experiment": "preprocess_google_trace",
                          "source": "gs://clusterdata_2019_a instance_usage shards 0-3 (parquet)",
                          **stats})
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
