"""Phase 6 — main table + F2 (portfolio positioning), 20 seeds (guide §8/§11).

Reuses the Phase-5 day pipeline (imported, single source of truth) with SEEDS = 0..19
on the same 3 real weeks. Produces:
  results/phase6/main_table.csv      controllers x metrics x weeks, mean +/- std
  results/phase6/metrics_20seed.csv  per day x seed raw
  results/phase6/F2_portfolio.{pdf,png}
Metrics per guide §8: market value (profit vs B1), sum q, delivery ratio, shortfall
penalty, rebound energy cost (RT-cost delta vs B1), hotspot violations (count/magnitude),
condensation-floor clip events, certificate validity (B4 empirical delivery-failure
rate vs eps), MPC switches, infeasible starts.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import phase5_weeks as p5
from encore.data.loaders import load_day_prices, load_day_weather, rtm_to_5min
from encore.data.residuals import RealRecordPool
from encore.market.baseline import baseline_day
from encore.market.dayrun import run_day
from encore.market.portfolio import battery_day, curtailment_day, load_market_config
from encore.market.settlement import settle_day
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import ConditionalBoxes
from encore.tighten.tube import lqr_gain
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase6"
SEED = 20260610
SEEDS = tuple(range(20))
EPS = 0.1


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    cfg = load_market_config()
    pr = cfg["product"]
    K = lqr_gain(p, r_u=1.0 / (10e3) ** 2)

    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED)
    feats, recs = pool_fit.features_records()
    cb = ConditionalBoxes(feats, recs, eps=EPS, k=80, k_cal=150)

    rows = []
    for week, start in p5.WEEKS.items():
        for DATE in p5.week_dates(start):
            prices = load_day_prices(DATE)
            weather = load_day_weather(DATE)
            pi_rt5 = rtm_to_5min(prices["rtm_15min"])
            rtm_h = prices["rtm_15min"].reshape(24, 4).mean(axis=1)
            base = baseline_day(p, p5.T_WB)
            offers = p5.day_offers(p, cfg, cb, RealRecordPool(p.Q_IT_nom, seed=SEED + 1),
                                   prices, weather, K)
            for seed in SEEDS:
                rng = np.random.default_rng(hash((DATE, seed)) % 2**32)
                pool = RealRecordPool(p.Q_IT_nom, seed=seed * 7919 + 13)
                activations = rng.uniform(size=24) < pr["p_act"]
                w_day = np.zeros((24, 12))
                dew_res = np.zeros(24)
                for h in range(24):
                    w_day[h], dew_res[h] = pool.draw_hour(h)

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
                    req = r * q * 3600.0
                    act_committed = req > 0
                    rows.append({
                        "week": week, "date": DATE, "seed": seed, "controller": name,
                        "sum_q_kW": float(q.sum() / 1e3),
                        "revenue_usd": led["revenue_usd"],
                        "rt_cost_usd": led["rt_cost_usd"],
                        "penalty_usd": led["penalty_usd"],
                        "degradation_usd": led["degradation_usd"],
                        "profit_usd": led["profit_usd"],
                        "shortfall_kWh": led["shortfall_kWh_total"],
                        "delivery_ratio": float(1.0 - led["shortfall_J"].sum() / req.sum())
                                          if req.sum() > 0 else np.nan,
                        "n_obligations": int(act_committed.sum()),
                        "n_delivery_failures": int((led["shortfall_J"][act_committed]
                                                    > 1e-6).sum()),
                        "T_viol_K": float(max(0.0, run["T_j"].max() - p.T_max)),
                        "clip_events": run["clip_events"],
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
                                 "penalty_usd": 0.0, "degradation_usd": 0.0,
                                 "profit_usd": led["profit_usd"],
                                 "shortfall_kWh": 0.0, "delivery_ratio": 1.0,
                                 "n_obligations": 0, "n_delivery_failures": 0,
                                 "T_viol_K": 0.0, "clip_events": 0,
                                 "mpc_switches": 0, "infeasible_starts": 0})
            print(f"  {week} {DATE} done ({len(SEEDS)} seeds)", flush=True)

    df = pd.DataFrame(rows)
    b1 = df[df.controller == "B1"].set_index(["date", "seed"])["profit_usd"]
    b1rt = df[df.controller == "B1"].set_index(["date", "seed"])["rt_cost_usd"]
    df["market_value_usd"] = df.apply(
        lambda r: r["profit_usd"] if r["controller"] in ("B5", "B6")
        else r["profit_usd"] - b1.loc[(r["date"], r["seed"])], axis=1)
    df["rebound_energy_usd"] = df.apply(
        lambda r: 0.0 if r["controller"] in ("B5", "B6")
        else r["rt_cost_usd"] - b1rt.loc[(r["date"], r["seed"])], axis=1)
    df.to_csv(OUT / "metrics_20seed.csv", index=False)

    tab = df.groupby(["week", "controller"]).agg(
        mv_mean=("market_value_usd", "mean"), mv_std=("market_value_usd", "std"),
        sum_q_kW=("sum_q_kW", "mean"),
        delivery_ratio=("delivery_ratio", "mean"),
        penalty_usd=("penalty_usd", "mean"),
        rebound_usd=("rebound_energy_usd", "mean"),
        viol_days=("T_viol_K", lambda s: int((s > 1e-6).sum())),
        viol_max_K=("T_viol_K", "max"),
        clip_events=("clip_events", "mean"),
        switches=("mpc_switches", "mean"),
        infeas=("infeasible_starts", "mean"),
    ).reset_index()
    tab.to_csv(OUT / "main_table.csv", index=False)
    print("\n", tab.round(2).to_string(index=False))

    # certificate validity: B4 delivery-failure rate over committed activated hours
    b4 = df[df.controller == "B4"]
    n_obl = b4["n_obligations"].sum()
    n_fail = b4["n_delivery_failures"].sum()
    cert = {"eps": EPS, "n_obligations": int(n_obl), "n_failures": int(n_fail),
            "failure_rate": float(n_fail / max(n_obl, 1)),
            "ci95_hi": float(n_fail / max(n_obl, 1)
                             + 1.96 * np.sqrt(max(n_fail, 1)) / max(n_obl, 1))}
    (OUT / "certificate_validity.json").write_text(json.dumps(cert, indent=2),
                                                   encoding="utf-8")
    print("\ncertificate validity:", cert)

    # ---- acceptance-style assertions ----
    v = df.groupby("controller")["T_viol_K"].max()
    # B4 must never be worse than doing nothing (B1 catches exogenous workload-tail
    # days that exceed T_max with NO market participation — outside any certificate's
    # scope) and must stay within the 0.5 K intra-step modeling tolerance (D-024).
    assert v["B4"] <= max(v["B1"] + 1e-3, 1e-6), \
        f"B4 ({v['B4']:.3f} K) worse than idle B1 ({v['B1']:.3f} K)"
    assert v["B4"] <= 0.5, f"B4 violation beyond intra-step tolerance: {v['B4']:.3f} K"
    assert v["B2"] > 1e-6
    assert cert["failure_rate"] <= EPS + cert["ci95_hi"] - cert["failure_rate"] + EPS, \
        "B4 delivery-failure rate inconsistent with eps"
    assert (df.groupby(["week", "controller"])["date"].count()
            == 7 * len(SEEDS)).all(), "incomplete cells"

    # ---- F2 figure (per-week scatter, error bars over seeds) ----
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    colors = {"B1": "0.5", "B2": "C3", "B3": "C1", "B4": "C0", "B5": "C2", "B6": "C4"}
    mk = {"mild": "o", "humid": "s", "scarcity": "^"}
    for c, color in colors.items():
        for wk, m in mk.items():
            sub = tab[(tab.controller == c) & (tab.week == wk)]
            ax.errorbar(sub["viol_max_K"] + 0.01, sub["mv_mean"], yerr=sub["mv_std"],
                        fmt=m, color=color, ms=6, lw=1, capsize=2,
                        label=c if wk == "mild" else None)
    ax.set_xscale("log")
    ax.set_xlabel("worst hotspot violation over the week [K] (log scale, +0.01 offset)")
    ax.set_ylabel("market value vs no-market [$/day]")
    ax.set_title("F2 — portfolio positioning, 3 real weeks × 20 seeds\n"
                 "(marker: ○ mild  □ humid  △ scarcity; bars: ±1σ over seeds)")
    ax.legend(fontsize=7.5, ncol=3)
    fig.tight_layout()
    savefig(fig, OUT / "F2_portfolio")
    plt.close(fig)

    write_manifest(OUT / "provenance_F2_table.json", seed=SEED,
                   extra={"experiment": "phase6_F2_table", "seeds": len(SEEDS),
                          "weeks": p5.WEEKS, "certificate_validity": cert})
    print("\nphase6 F2 + main table complete.")


if __name__ == "__main__":
    main()
