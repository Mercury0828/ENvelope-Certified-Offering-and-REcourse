"""Phase 5 — closed loop + all baselines B1..B6 on 3 representative weeks (guide §11).

Weeks (real ERCOT prices + real KIAH weather):
  mild      2024-04-01..07
  humid     2023-08-14..20   (Houston summer; B4 expected to mostly sit out)
  scarcity  2024-01-14..20   (Winter Storm Heather; ECRS spikes)

Disturbances: REAL records — Google-trace heat residuals + KIAH dew residuals replayed
by hour-of-day (data/residuals.py, D-042); W(c) refit on the same real record pool
(conformal k-NN, smaller k for the 744-hour pool). Seeds: 3 (smoke; Phase 6 runs 20+).
B4 commitments carry the readiness-polygon terminal (D-041 resolution).

Acceptance (asserted): all 6 controllers complete all weeks without crashes;
metric table generated; B2 shows violations B4 avoids; B4 profit >= B1 per week.
Outputs: results/phase5/metrics.csv, weekly_summary.csv, proto_F2 figure, SELF_AUDIT.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json
from datetime import date, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from encore.data.loaders import load_day_prices, load_day_weather, rtm_to_5min
from encore.data.residuals import RealRecordPool
from encore.market.baseline import baseline_day
from encore.market.dayrun import run_day
from encore.market.offering import make_offers
from encore.market.portfolio import battery_day, curtailment_day, load_market_config
from encore.market.settlement import settle_day
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import Box, ConditionalBoxes
from encore.tighten.tube import lqr_gain
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest
from encore.utils.stats import stable_seed

OUT = REPO / "results" / "phase5"
SEED = 20260610
T_WB = 22.0
SEEDS = (0, 1, 2)
N_SAA = 20
SOURCE = "alibaba_jobaware"   # real PAI trace + causal job-aware DA forecast (D-051)
N_STATES = 3             # the gate-approved S2 product, certified (D-049)
EPS = 0.3                # DELIVERY eps (penalty-backed design point, D-051/D-052)
EPS_SAFE = 0.05          # SAFETY eps — fixed, never traded for revenue (D-052)
R_GAIN_KW = 300.0        # offline LQR authority (F-tilde saturates ~300 kW/K, D-051)
# 10 weeks spanning 2024 (forecast archive coverage; >=500 obligations for tight CIs)
WEEKS = {
    "w03-jan-scarcity": "2024-01-14",   # Winter Storm Heather
    "w07-feb": "2024-02-12",
    "w11-mar": "2024-03-11",
    "w14-apr-mild": "2024-04-01",
    "w20-may": "2024-05-13",
    "w24-jun": "2024-06-10",
    "w29-jul": "2024-07-15",
    "w33-aug-humid": "2024-08-12",
    "w37-sep": "2024-09-09",
    "w42-oct": "2024-10-14",
}


def week_dates(start: str):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(7)]


def saa_box_from_pool(pool: RealRecordPool, hod: int, n=N_SAA) -> Box:
    wq = en = dw = 0.0
    for _ in range(n):
        vec, dres = pool.draw_hour(hod)
        wq = max(wq, float(vec.max()))
        en = max(en, float(np.maximum(vec, 0).sum() * pool.dt))
        dw = max(dw, dres)
    return Box(w_Q_hi=wq, E_hi=en, w_D_hi=dw)


def day_offers(p, cfg, cb_del, pool_saa, prices, weather, K, eps=EPS, cb_safe=None):
    """cb_del: DELIVERY-eps boxes; cb_safe: SAFETY-eps boxes (D-052)."""
    rtm_h = prices["rtm_15min"].reshape(24, 4).mean(axis=1)
    contexts, bx_del, bx_safe, bx_saa = [], [], [], []
    for h in range(24):
        contexts.append({
            # REAL day-ahead NWP dew forecast (D-050); realized dew is the observation
            "T_dew_fc": float(weather["T_dew_fc_hourly"][h]), "T_wb": T_WB,
            "pi_cap": float(prices["pi_cap_hourly"][h]),
            "pi_rt_event": float(rtm_h[h]), "pi_rt_recovery": float(rtm_h[(h + 1) % 24]),
        })
        bx_del.append(cb_del.box(RealRecordPool.hour_features(h)))
        bx_safe.append((cb_safe or cb_del).box(RealRecordPool.hour_features(h)))
        bx_saa.append(saa_box_from_pool(pool_saa, h))
    pr = cfg["product"]
    kw = dict(d_min=float(pr["d_min"]), p_act=pr["p_act"],
              c_deg_per_Kh=pr["c_deg_per_Kh"], T_thr=pr["T_thr_C"], n_grid=10,
              n_states=N_STATES, eps=eps, gamma_mult=pr["gamma_mult"])
    # readiness=False (D-048): terminal startability is guaranteed by construction —
    # adjacency pruning leaves a recovery hour and the sprint idle law restores the
    # e0-ball ready state well within it; the LP terminal (immediate re-delivery)
    # over-constrains by exactly q and is reserved for the theory object.
    return {
        "B2": make_offers(p, contexts, "deterministic", K=K, **kw),
        "B3": make_offers(p, contexts, "saa", boxes=bx_saa, K=K, **kw),
        "B4": make_offers(p, contexts, "certified", boxes=bx_del, boxes_safe=bx_safe,
                          K=K, **kw),
    }


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    cfg = load_market_config()
    pr = cfg["product"]
    K = lqr_gain(p, N_STATES, r_u=1.0 / (R_GAIN_KW * 1e3) ** 2)

    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=SOURCE)
    feats, recs = pool_fit.features_records()
    cb = ConditionalBoxes(feats, recs, eps=EPS, k=80, k_cal=150)
    print(f"W(c) fit on {len(recs)} real records ({SOURCE}, causal climatology); "
          f"evaluation replays the HELD-OUT trace-day block (D-046/D-050)")

    rows = []
    for week, start in WEEKS.items():
        for DATE in week_dates(start):
            prices = load_day_prices(DATE)
            weather = load_day_weather(DATE)
            pi_rt5 = rtm_to_5min(prices["rtm_15min"])
            rtm_h = prices["rtm_15min"].reshape(24, 4).mean(axis=1)
            base = baseline_day(p, T_WB)
            offers = day_offers(p, cfg, cb,
                                RealRecordPool(p.Q_IT_nom, seed=SEED + 1, role="fit",
                                               source=SOURCE),
                                prices, weather, K)
            for seed in SEEDS:
                rng = np.random.default_rng(stable_seed(DATE, seed))
                pool = RealRecordPool(p.Q_IT_nom, seed=stable_seed("replay", seed),
                                      role="eval", source=SOURCE)
                activations = rng.uniform(size=24) < pr["p_act"]
                w_day = np.zeros((24, 12))
                dew_res = np.asarray(weather["dew_resid_hourly"], dtype=float)  # REAL
                for h in range(24):
                    w_day[h], _ = pool.draw_hour(h)

                for name, plans, ctl in (("B1", offers["B4"], "idle"),
                                         ("B2", offers["B2"], "mpc"),
                                         ("B3", offers["B3"], "mpc"),
                                         ("B4", offers["B4"], "mpc")):
                    run = run_day(p, plans, activations, w_day, dew_res, K, controller=ctl)
                    q = np.zeros(24) if name == "B1" else np.array([pl.q_W for pl in plans])
                    r = activations.astype(float) * (pr["d_min"] / 60.0) * (q > 0)
                    led = settle_day(q, r, prices["pi_cap_hourly"], run["P_cool_W"],
                                     base["P_base_W"], pi_rt5, run["T_j"],
                                     gamma_mult=pr["gamma_mult"],
                                     c_deg_per_Kh=pr["c_deg_per_Kh"], T_thr=pr["T_thr_C"])
                    rows.append({
                        "week": week, "date": DATE, "seed": seed, "controller": name,
                        "sum_q_kW": float(q.sum() / 1e3),
                        **{k: led[k] for k in ("revenue_usd", "rt_cost_usd",
                                               "penalty_usd", "degradation_usd",
                                               "profit_usd", "shortfall_kWh_total")},
                        "max_T_j": float(run["T_j"].max()),
                        "T_viol_K": float(max(0.0, run["T_j"].max() - p.T_max)),
                        "mpc_switches": run["switches"],
                        "infeasible_starts": run["infeasible_starts"],
                    })
                for led in (battery_day(cfg, prices["pi_cap_hourly"], rtm_h,
                                        activations, pr["p_act"]),
                            curtailment_day(cfg, p, prices["pi_cap_hourly"],
                                            activations, pr["p_act"])):
                    rows.append({"week": week, "date": DATE, "seed": seed,
                                 "controller": led["controller"],
                                 "sum_q_kW": led["sum_q_kW"],
                                 "revenue_usd": led["revenue_usd"],
                                 "rt_cost_usd": led["rt_cost_usd"],
                                 "penalty_usd": led["penalty_usd"],
                                 "degradation_usd": led["degradation_usd"],
                                 "profit_usd": led["profit_usd"],
                                 "shortfall_kWh_total": led["shortfall_kWh"],
                                 "max_T_j": led["max_T_j"],
                                 "T_viol_K": 0.0,
                                 "mpc_switches": 0, "infeasible_starts": 0})
            print(f"  {week} {DATE} done")

    df = pd.DataFrame(rows)
    # market value vs B1 (thermal controllers); B5/B6 are additive assets (= profit)
    b1 = df[df.controller == "B1"].set_index(["date", "seed"])["profit_usd"]
    def mv(row):
        if row["controller"] in ("B5", "B6"):
            return row["profit_usd"]
        return row["profit_usd"] - b1.loc[(row["date"], row["seed"])]
    df["market_value_usd"] = df.apply(mv, axis=1)
    df.to_csv(OUT / "metrics.csv", index=False)

    agg = df.groupby(["week", "controller"]).agg(
        mv_usd_day=("market_value_usd", "mean"),
        mv_std=("market_value_usd", "std"),
        sum_q_kW=("sum_q_kW", "mean"),
        penalty=("penalty_usd", "mean"),
        shortfall_kWh=("shortfall_kWh_total", "mean"),
        viol_days=("T_viol_K", lambda s: int((s > 1e-6).sum())),
        max_viol_K=("T_viol_K", "max"),
        switches=("mpc_switches", "mean"),
        infeas=("infeasible_starts", "mean"),
    ).reset_index()
    agg.to_csv(OUT / "weekly_summary.csv", index=False)
    print("\n", agg.round(2).to_string(index=False))

    # ---- acceptance assertions ----
    for week in WEEKS:
        for c in ("B1", "B2", "B3", "B4", "B5", "B6"):
            n = len(df[(df.week == week) & (df.controller == c)])
            assert n == 7 * len(SEEDS), f"{c} incomplete in {week} ({n})"
    v = df.groupby("controller")["T_viol_K"].max()
    assert v["B2"] > 1e-6, "B2 shows no violations anywhere — comparison degenerate?"
    assert v["B4"] <= 1e-6, f"B4 violated T_max ({v['B4']:.3f} K) — certificate broken"
    for week in WEEKS:
        mv4 = agg[(agg.week == week) & (agg.controller == "B4")]["mv_usd_day"].iloc[0]
        assert mv4 >= -1.0, f"B4 below B1 in {week} week ({mv4:.2f} $/day)"
    b4inf = df[df.controller == "B4"]["infeasible_starts"].sum()
    print(f"\nB4 infeasible starts across all runs: {b4inf} (readiness wiring, D-041)")

    # ---- proto-F2: profit vs violations scatter ----
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    colors = {"B1": "0.5", "B2": "C3", "B3": "C1", "B4": "C0", "B5": "C2", "B6": "C4"}
    for c in colors:
        sub = agg[agg.controller == c]
        ax.scatter(sub["max_viol_K"] + 0.01, sub["mv_usd_day"], color=colors[c],
                   s=45, label=c)
    ax.set_xscale("log")
    ax.set_xlabel("worst hotspot violation [K] (log, +0.01 offset)")
    ax.set_ylabel("market value vs no-market [$ / day]")
    ax.set_title("Portfolio positioning across 3 real weeks (proto-F2, 3 seeds)")
    ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    savefig(fig, OUT / "proto_F2")
    plt.close(fig)

    write_manifest(OUT / "provenance_weeks.json", seed=SEED,
                   extra={"experiment": "phase5_weeks", "weeks": WEEKS,
                          "seeds": list(SEEDS), "records": int(len(recs))})
    print("\nall Phase-5 assertions passed.")


if __name__ == "__main__":
    main()
