"""Job-aware day-ahead forecast for the PAI hall (C3 optimization, D-051).

At day-ahead issue time (12:00 of day D for day D+1), the operator KNOWS the running
workers, their elapsed runtimes and utilizations (guide 6.2's "planned job mix"
context). Forecast for hour h of D+1:

    persistent(h) = sum over workers running at issue of util_w * S_hat(Delta_h | e_w)
    churn_clim(hod) = mean over FIT days of [actual(h) - persistent(h)]
    forecast(h)   = persistent(h) + churn_clim(hod)

S_hat = empirical survival P(remaining > Delta | elapsed e), fit on the FIT block only
(log-binned elapsed). Fully causal: issue-time info + fit-block statistics.

Outputs data/traces/alibaba2020/jobaware_residuals.npz (per-hour 12-step residual
vectors + hod + day + block flags) and comparison stats vs the climatology forecast.
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
ISSUE_HOUR = 12          # day-ahead market issue time (trace-relative clock)

SENS_USE = {2: "worker_name", 7: "gpu_wrk_util"}
INST_USE = {3: "worker_name", 5: "status", 6: "start_time", 7: "end_time"}


def read_member(tar_path: Path, colmap: dict) -> pd.DataFrame:
    with tarfile.open(tar_path) as tf:
        member = tf.getmembers()[0]
        df = pd.read_csv(tf.extractfile(member), header=None,
                         usecols=list(colmap.keys()))
    return df.rename(columns=colmap)


def load_workers():
    sens = read_member(D / "pai_sensor_table.tar.gz", SENS_USE)
    sens = sens.dropna().groupby("worker_name", as_index=False)["gpu_wrk_util"].mean()
    inst = read_member(D / "pai_instance_table.tar.gz", INST_USE)
    inst = inst[(inst["status"] == "Terminated")
                & inst["start_time"].notna() & inst["end_time"].notna()]
    inst = inst[inst["end_time"] > inst["start_time"]]
    df = inst.merge(sens, on="worker_name", how="inner")
    t0 = float(df["start_time"].min())
    df["start"] = df["start_time"] - t0
    df["end"] = df["end_time"] - t0
    df["u"] = df["gpu_wrk_util"] / 100.0
    return df[["start", "end", "u"]].reset_index(drop=True)


def busy_series(df, n_bins):
    busy = np.zeros(n_bins + 1)
    s = (df["start"].to_numpy() // DT).astype(int).clip(0, n_bins)
    e = ((df["end"].to_numpy() // DT).astype(int) + 1).clip(0, n_bins)
    np.add.at(busy, s, df["u"].to_numpy())
    np.add.at(busy, e, -df["u"].to_numpy())
    return np.cumsum(busy)[:n_bins]


def survival_fit(df, fit_end_s, elapsed_bins, horizons):
    """S_hat[b, k] = P(remaining > horizons[k] | elapsed in bin b), from completed
    spells observed inside the FIT window only (sampled at hourly snapshots)."""
    counts = np.zeros((len(elapsed_bins) - 1, len(horizons)))
    totals = np.zeros(len(elapsed_bins) - 1)
    snaps = np.arange(3600 * 12, fit_end_s - 3600 * 40, 3600 * 6)
    for t in snaps:
        run = df[(df["start"] <= t) & (df["end"] > t)]
        e = (t - run["start"]).to_numpy()
        rem = (run["end"] - t).to_numpy()
        b = np.clip(np.digitize(e, elapsed_bins) - 1, 0, len(elapsed_bins) - 2)
        for k, hz in enumerate(horizons):
            np.add.at(counts, (b, np.full(len(b), k)), (rem > hz).astype(float))
        np.add.at(totals, b, 1.0)
    return counts / np.maximum(totals[:, None], 1.0)


def main():
    df = load_workers()
    horizon_s = float(df["end"].max())
    n_bins_raw = int(horizon_s // DT)
    G_raw = busy_series(df, n_bins_raw)
    # trim the trace ramp-in/out (jobs running before trace start are absent -> the
    # first days systematically under-count load; standard trace hygiene): keep whole
    # days where G sustainedly exceeds 60% of its q99
    thr = 0.6 * np.quantile(G_raw, 0.99)
    ok_days = [d_ for d_ in range(int(n_bins_raw * DT // 86400))
               if np.median(G_raw[d_ * 288:(d_ + 1) * 288]) > thr]
    day_lo, day_hi = min(ok_days), max(ok_days)
    t_shift = day_lo * 86400
    df = df.assign(start=df["start"] - t_shift, end=df["end"] - t_shift)
    df = df[df["end"] > 0]
    n_days = day_hi - day_lo + 1
    n_bins = n_days * 288
    G = busy_series(df, n_bins)
    print(f"trimmed to trace days {day_lo}..{day_hi} ({n_days} days)")
    scale = np.quantile(G, 0.999)
    P_actual = P_HALL_KW * 1e3 * (IDLE_FRAC + (1 - IDLE_FRAC) * np.clip(G / scale, 0, 1.2))

    fit_days = (2 * n_days) // 3
    fit_end_s = fit_days * 86400

    elapsed_bins = np.array([0, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600,
                             48 * 3600, 1e12])
    horizons = np.arange(12, 37) * 3600.0      # 12..36 h ahead (D+1 hours)
    S = survival_fit(df, fit_end_s, elapsed_bins, horizons)
    print("survival S(rem>24h | elapsed) by elapsed bin:",
          np.round(S[:, 12], 3))

    # persistent component for every day D+1 (issue at 12:00 of D)
    persistent = np.zeros(n_bins)
    for day in range(0, n_days - 1):
        t_issue = day * 86400 + ISSUE_HOUR * 3600
        run = df[(df["start"] <= t_issue) & (df["end"] > t_issue)]
        e = (t_issue - run["start"]).to_numpy()
        u = run["u"].to_numpy()
        b = np.clip(np.digitize(e, elapsed_bins) - 1, 0, len(elapsed_bins) - 2)
        day1 = (day + 1) * 86400
        for h in range(24):
            val = float((u * S[b, h]).sum())   # horizons[h] = (12+h) hours from issue
            lo = (day1 + h * 3600) // DT
            persistent[int(lo):int(lo) + 12] = val
    P_persist = P_HALL_KW * 1e3 * (IDLE_FRAC + (1 - IDLE_FRAC)
                                   * np.clip(persistent / scale, 0, 1.2))

    t_s = np.arange(n_bins) * DT
    hod = (t_s // 3600) % 24
    day = t_s // 86400
    valid = day >= 1                          # day 0 has no prior issue
    fit_mask = valid & (day < fit_days)

    # level-aware churn model (still causal): the day's churn rides on the load level
    # KNOWN at issue time (mean load of day D up to 12:00). churn(h) for day D+1 =
    # alpha(hod) + beta * level(D), fit on the FIT block.
    level = np.zeros(n_days)                  # mean P of day d in [0, 12:00)
    for d_ in range(n_days):
        m = (t_s >= d_ * 86400) & (t_s < d_ * 86400 + ISSUE_HOUR * 3600)
        level[d_] = float(P_actual[m].mean())
    lev_of_bin = level[np.maximum(day - 1, 0)]            # issue-day level for each bin
    churn_target = P_actual - P_persist
    lev_fit = lev_of_bin[fit_mask]
    ct_fit = churn_target[fit_mask]
    lev_c = lev_fit - lev_fit.mean()
    beta = float((lev_c * (ct_fit - ct_fit.mean())).sum() / (lev_c ** 2).sum())
    alpha = np.zeros(24)
    for h in range(24):
        m = fit_mask & (hod == h)
        alpha[h] = float((churn_target[m] - beta * (lev_of_bin[m] - lev_fit.mean())).mean())
    print(f"churn level-regression: beta = {beta:.3f}, "
          f"day-level autocorr(1) = "
          f"{np.corrcoef(level[1:fit_days], level[:fit_days-1])[0, 1]:.3f}")
    forecast = P_persist + alpha[hod] + beta * (lev_of_bin - lev_fit.mean())
    resid = P_actual - forecast

    # package per-hour residual vectors
    vecs, hods, days_, blocks = [], [], [], []
    for hr in range(24 * 1, 24 * n_days):
        sl = slice(hr * 12, hr * 12 + 12)
        if sl.stop <= n_bins:
            vecs.append(resid[sl])
            hods.append(int(hod[sl.start]))
            d_ = int(day[sl.start])
            days_.append(d_)
            blocks.append("fit" if d_ < fit_days else "eval")
    np.savez(D / "jobaware_residuals.npz", vectors=np.array(vecs),
             hod=np.array(hods), day=np.array(days_),
             block=np.array(blocks), fit_days=fit_days)

    # comparison vs climatology forecast (same fit-block clim)
    clim = np.zeros(24)
    for h in range(24):
        m = fit_mask & (hod == h)
        clim[h] = float(P_actual[m].mean())
    resid_clim = P_actual - clim[hod]

    def stats(r, mask):
        hr = r[mask][: (mask.sum() // 12) * 12].reshape(-1, 12)
        return {"std_kW": float(r[mask].std() / 1e3),
                "hourly_max_q95_kW": float(np.quantile(hr.max(axis=1), .95) / 1e3),
                "hourly_Epos_q95_MJ": float(np.quantile(
                    np.maximum(hr, 0).sum(axis=1) * DT, .95) / 1e6)}

    eval_mask = valid & (day >= fit_days)
    out = {"jobaware_eval": stats(resid, eval_mask),
           "climatology_eval": stats(resid_clim, eval_mask),
           "fit_days": int(fit_days), "n_days": int(n_days)}
    print(json.dumps(out, indent=2))
    (D / "jobaware_stats.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    write_manifest(D / "provenance_jobaware.json", seed=None,
                   extra={"experiment": "build_jobaware_forecast", **out})


if __name__ == "__main__":
    main()
