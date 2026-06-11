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
from encore.utils.stats import clopper_pearson, stable_seed

OUT = REPO / "results" / "phase6"
SEED = 20260610
SEEDS = tuple(range(20))
EPS = 0.1
# Two configurations (D-050 finding): the REAL ML-cluster trace (PAI — certification
# is honestly ~zero against its day-ahead-unforecastable sustained load swings) and
# the literature-anchored dedicated-training-hall scenario (near-constant training
# power; emulated as Borg residuals at half scale, labeled as scenario).
CONFIGS = [("alibaba", 1.0, "alibaba"), ("borg", 0.5, "trainhall")]


def run_source(source: str, scale: float, label: str, p, cfg, K):
    pr = cfg["product"]
    suffix = f"_{label}"
    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=source,
                              scale=scale)
    feats, recs = pool_fit.features_records()
    cb = ConditionalBoxes(feats, recs, eps=EPS, k=80, k_cal=150)
    print(f"[{label}] W(c) fit on {len(recs)} records ({source} x {scale}, causal "
          "clim); evaluation replays the held-out trace-day block (D-046/D-050)")

    rows = []
    for week, start in p5.WEEKS.items():
        for DATE in p5.week_dates(start):
            prices = load_day_prices(DATE)
            weather = load_day_weather(DATE)
            pi_rt5 = rtm_to_5min(prices["rtm_15min"])
            rtm_h = prices["rtm_15min"].reshape(24, 4).mean(axis=1)
            base = baseline_day(p, p5.T_WB)
            offers = p5.day_offers(p, cfg, cb,
                                   RealRecordPool(p.Q_IT_nom, seed=SEED + 1, role="fit",
                                                  source=source, scale=scale),
                                   prices, weather, K)
            b4_boxes = [cb.box(RealRecordPool.hour_features(h)) for h in range(24)]
            for seed in SEEDS:
                rng = np.random.default_rng(stable_seed(DATE, seed))
                pool = RealRecordPool(p.Q_IT_nom, seed=stable_seed("replay", seed),
                                      role="eval", source=source, scale=scale)
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
                    req = r * q * 3600.0
                    act_committed = req > 0
                    # failure attribution for the certificate claim (D-047): a delivery
                    # failure is theory-relevant only if the hour was IN-box and the
                    # event started inside the e0-ball (cold start)
                    n_fail_warm = n_fail_outbox = n_fail_clean = 0
                    if name == "B4":
                        for h in np.where(act_committed
                                          & (led["shortfall_J"] > 1e-6))[0]:
                            in_box = b4_boxes[h].contains(
                                w_day[h].max(),
                                float(np.maximum(w_day[h], 0).sum() * p.dt_ctrl),
                                dew_res[h])
                            if h in run["infeasible_hours"]:
                                n_fail_warm += 1
                            elif not in_box:
                                n_fail_outbox += 1
                            else:
                                n_fail_clean += 1
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
                        "n_fail_warm_start": n_fail_warm,
                        "n_fail_out_of_box": n_fail_outbox,
                        "n_fail_clean_in_box": n_fail_clean,
                        "n_warm_starts": run["infeasible_starts"],
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
                                 "n_fail_warm_start": 0, "n_fail_out_of_box": 0,
                                 "n_fail_clean_in_box": 0, "n_warm_starts": 0,
                                 "T_viol_K": 0.0, "clip_events": 0,
                                 "mpc_switches": 0, "infeasible_starts": 0})
            print(f"  [{label}] {week} {DATE} done ({len(SEEDS)} seeds)", flush=True)

    df = pd.DataFrame(rows)
    b1 = df[df.controller == "B1"].set_index(["date", "seed"])["profit_usd"]
    b1rt = df[df.controller == "B1"].set_index(["date", "seed"])["rt_cost_usd"]
    df["market_value_usd"] = df.apply(
        lambda r: r["profit_usd"] if r["controller"] in ("B5", "B6")
        else r["profit_usd"] - b1.loc[(r["date"], r["seed"])], axis=1)
    df["rebound_energy_usd"] = df.apply(
        lambda r: 0.0 if r["controller"] in ("B5", "B6")
        else r["rt_cost_usd"] - b1rt.loc[(r["date"], r["seed"])], axis=1)
    df["source"] = source
    df["scale"] = scale
    df.to_csv(OUT / f"metrics_20seed{suffix}.csv", index=False)

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
    tab.to_csv(OUT / f"main_table{suffix}.csv", index=False)
    print("\n", tab.round(2).to_string(index=False))

    # certificate validity (D-046/D-047): the Thm-2 claim covers COLD-start obligations
    # (event begins inside the e0-ball) — its eps budget is the out-of-box probability.
    # Warm starts are outside the theory and reported separately with attribution.
    b4 = df[df.controller == "B4"]
    n_obl = int(b4["n_obligations"].sum())
    n_warm = int(b4["n_warm_starts"].sum())
    n_fail = int(b4["n_delivery_failures"].sum())
    n_fail_warm = int(b4["n_fail_warm_start"].sum())
    n_fail_out = int(b4["n_fail_out_of_box"].sum())
    n_fail_clean = int(b4["n_fail_clean_in_box"].sum())
    n_cold = max(n_obl - n_warm, 1)
    cold_fail = n_fail - n_fail_warm
    ci_lo, ci_hi = clopper_pearson(cold_fail, n_cold)
    cert = {"eps": EPS, "n_obligations": n_obl, "n_warm_starts": n_warm,
            "n_failures_total": n_fail,
            "failures_by_cause": {"warm_start": n_fail_warm,
                                  "out_of_box": n_fail_out,
                                  "clean_in_box": n_fail_clean},
            "cold_start_failure_rate": float(cold_fail / n_cold),
            "cold_start_ci95": [ci_lo, ci_hi],
            "overall_failure_rate": float(n_fail / max(n_obl, 1)),
            "method": "Clopper-Pearson exact", "source": source, "scale": scale,
            "label": label, "n_states": p5.N_STATES}
    (OUT / f"certificate_validity{suffix}.json").write_text(json.dumps(cert, indent=2),
                                                            encoding="utf-8")
    print("\ncertificate validity:", json.dumps(cert, indent=2))

    # ---- acceptance-style assertions ----
    v = df.groupby("controller")["T_viol_K"].max()
    # B4 must never be worse than doing nothing (B1 catches exogenous workload-tail
    # days that exceed T_max with NO market participation — outside any certificate's
    # scope) and must stay within the 0.5 K intra-step modeling tolerance (D-024).
    assert v["B4"] <= max(v["B1"] + 1e-3, 1e-6), \
        f"B4 ({v['B4']:.3f} K) worse than idle B1 ({v['B1']:.3f} K)"
    assert v["B4"] <= 0.5, f"B4 violation beyond intra-step tolerance: {v['B4']:.3f} K"
    assert v["B2"] > 1e-6
    # Thm-2 gate (D-047): no clean in-box cold-start failure may exist (that would be a
    # broken certificate), and the data must not reject "cold-start failure prob <= eps".
    # where B4 rationally never offers (n_obligations = 0) the gate is vacuous.
    assert cert["failures_by_cause"]["clean_in_box"] == 0, \
        f"CERTIFICATE BROKEN: {cert['failures_by_cause']['clean_in_box']} in-box cold-start failures"
    if n_obl > 0:
        assert cert["cold_start_ci95"][0] <= EPS, \
            f"data rejects cold-start failure-rate <= eps: CP lower {cert['cold_start_ci95'][0]:.3f}"
    else:
        print("NOTE: B4 has zero obligations on this source — certificate gate vacuous "
              "(rational no-offer regime)")
    assert (df.groupby(["week", "controller"])["date"].count()
            == 7 * len(SEEDS)).all(), "incomplete cells"

    # ---- F2 figure (per-week scatter, error bars over seeds) ----
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    colors = {"B1": "0.5", "B2": "C3", "B3": "C1", "B4": "C0", "B5": "C2", "B6": "C4"}
    markers = ["o", "s", "^", "v", "D", "P", "X", "*", "<", ">"]
    weeks_sorted = sorted(tab["week"].unique())
    for c, color in colors.items():
        for wi, wk in enumerate(weeks_sorted):
            sub = tab[(tab.controller == c) & (tab.week == wk)]
            ax.errorbar(sub["viol_max_K"] + 0.01, sub["mv_mean"], yerr=sub["mv_std"],
                        fmt=markers[wi % len(markers)], color=color, ms=5, lw=1,
                        capsize=2, label=c if wi == 0 else None)
    ax.set_xscale("log")
    ax.set_xlabel("worst hotspot violation over the week [K] (log scale, +0.01 offset)")
    ax.set_ylabel("market value vs no-market [$/day]")
    ax.set_title(f"F2 — portfolio positioning, {len(p5.WEEKS)} real weeks × "
                 f"{len(SEEDS)} seeds ({label}, S2 product)\n"
                 "(markers by week; bars: ±1σ over seeds)")
    ax.legend(fontsize=7.5, ncol=3)
    fig.tight_layout()
    savefig(fig, OUT / f"F2_portfolio{suffix}")
    plt.close(fig)
    return cert


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    cfg = load_market_config()
    K = lqr_gain(p, p5.N_STATES, r_u=1.0 / (10e3) ** 2)
    certs = {}
    for source, scale, label in CONFIGS:
        certs[label] = run_source(source, scale, label, p, cfg, K)
    write_manifest(OUT / "provenance_F2_table.json", seed=SEED,
                   extra={"experiment": "phase6_F2_table", "seeds": len(SEEDS),
                          "weeks": p5.WEEKS, "configs": CONFIGS,
                          "n_states": p5.N_STATES, "certificate_validity": certs})
    print("\nphase6 F2 + main table complete (both configurations).")


if __name__ == "__main__":
    main()
