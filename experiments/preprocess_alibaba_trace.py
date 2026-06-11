"""Data preprocessing — Alibaba PAI GPU-cluster 2020 -> 1 MW training-hall heat profile
(owner-approved real dedicated-ML-hall trace, D-050; replaces the kappa scenario).

Reconstruction: each worker contributes its measured average GPU usage
(sensor.gpu_wrk_util, in GPU-equivalents x100) over its [start_time, end_time] window
(instance table). Summing active workers on a 5-min grid yields the cluster busy-GPU
series G(t) — training jobs hold near-constant power within their lifetime, so hall
power dynamics are churn-driven (job starts/stops), which is exactly the dedicated-hall
mechanism. Affine power map as for Borg (idle 0.3 [est]); normalized by the q99.9 of G.

Outputs: data/traces/alibaba2020/hall_profile_5min.csv (+ stats incl. the implied
volatility relative to Borg cell-a), provenance JSON.
"""

import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json

import numpy as np
import pandas as pd

from encore.utils.provenance import write_manifest

D = REPO / "data" / "traces" / "alibaba2020"
DT = 300
P_HALL_KW = 1000.0
IDLE_FRAC = 0.3

# positional schemas verified against the raw files (no header rows):
# sensor:   col2 = worker_name, col7 = gpu_wrk_util [% of one GPU]
# instance: col3 = worker_name, col5 = status, col6 = start_time, col7 = end_time
SENS_USE = {2: "worker_name", 7: "gpu_wrk_util"}
INST_USE = {3: "worker_name", 5: "status", 6: "start_time", 7: "end_time"}


def read_member(tar_path: Path, colmap: dict) -> pd.DataFrame:
    with tarfile.open(tar_path) as tf:
        member = tf.getmembers()[0]
        df = pd.read_csv(tf.extractfile(member), header=None,
                         usecols=list(colmap.keys()))
    return df.rename(columns=colmap)


def main():
    sens = read_member(D / "pai_sensor_table.tar.gz", SENS_USE)
    sens = sens.dropna().groupby("worker_name", as_index=False)["gpu_wrk_util"].mean()
    print(f"sensor: {len(sens)} workers with gpu_wrk_util")

    inst = read_member(D / "pai_instance_table.tar.gz", INST_USE)
    inst = inst[(inst["status"] == "Terminated")
                & inst["start_time"].notna() & inst["end_time"].notna()]
    inst = inst[inst["end_time"] > inst["start_time"]]
    df = inst.merge(sens, on="worker_name", how="inner")
    print(f"joined: {len(df)} terminated workers with usage "
          f"(join rate {len(df)/max(len(inst),1):.1%} of terminated instances)")
    assert len(df) > 100_000, "join failed — column mapping wrong?"

    t0 = float(df["start_time"].min())
    t1 = float(df["end_time"].max())
    n_bins = int((t1 - t0) // DT) + 2
    busy = np.zeros(n_bins + 1)
    s_bin = ((df["start_time"].to_numpy() - t0) // DT).astype(int)
    e_bin = np.minimum(((df["end_time"].to_numpy() - t0) // DT).astype(int) + 1, n_bins)
    util = df["gpu_wrk_util"].to_numpy() / 100.0           # GPU-equivalents
    np.add.at(busy, s_bin, util)
    np.add.at(busy, e_bin, -util)
    G = np.cumsum(busy)[:n_bins]

    # trim the ramp-in/out edges where the trace is incomplete
    lo, hi = np.quantile(np.nonzero(G > G.max() * 0.2)[0], [0.0, 1.0]).astype(int)
    G = G[lo:hi]
    scale = np.quantile(G, 0.999)
    u = np.clip(G / scale, 0, 1.2)
    P_kW = P_HALL_KW * (IDLE_FRAC + (1 - IDLE_FRAC) * u)
    t_s = (np.arange(len(G)) * DT).astype(int)

    out = pd.DataFrame({"t_s": t_s, "n": np.round(G, 2), "u_mean": u,
                        "u_peak": u, "P_mean_kW": P_kW, "P_peak_kW": P_kW})
    out.to_csv(D / "hall_profile_5min.csv", index=False)

    # volatility statistics (comparable to the Borg pipeline's residual definition)
    hod = (t_s // 3600) % 24
    day = t_s // 86400
    clim_days = (2 * (int(day.max()) + 1)) // 3
    clim = pd.Series(P_kW).groupby(hod).transform("mean")
    mask_fit = day < clim_days
    resid = (P_kW - clim.to_numpy())
    hr = resid[: (len(resid) // 12) * 12].reshape(-1, 12)
    stats = {
        "windows": int(len(G)), "days": float(len(G) * DT / 86400),
        "P_mean_kW": float(P_kW.mean()),
        "P_minmax_kW": [float(P_kW.min()), float(P_kW.max())],
        "step_resid_std_kW": float(resid[mask_fit].std() / 1.0),
        "hourly_max_resid_q95_kW": float(np.quantile(hr.max(axis=1), 0.95)),
        "borg_comparison_note": "Borg cell-a step-resid std ~73 kW, hourly-max q95 ~222 kW",
        "idle_frac_est": IDLE_FRAC,
    }
    (D / "hall_profile_stats.json").write_text(json.dumps(stats, indent=2),
                                               encoding="utf-8")
    write_manifest(D / "provenance_alibaba_trace.json", seed=None,
                   extra={"experiment": "preprocess_alibaba_trace",
                          "source": "aliopentrace v2020GPUTraces instance+sensor tables",
                          **stats})
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
