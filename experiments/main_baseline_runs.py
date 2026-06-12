"""B7 (single-risk robust offering, eps=0.05) and B8 (context-free robust
envelope) at FULL main-table statistics: 10 weeks x 20 seeds with the complete
settlement ledger, for promotion into Table III (review response R4-revised)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))

import numpy as np
import pandas as pd

import phase5_weeks as p5
from encore.data.loaders import load_day_prices, load_day_weather, rtm_to_5min
from encore.data.residuals import RealRecordPool
from encore.market.baseline import baseline_day
from encore.market.dayrun import run_day
from encore.market.portfolio import load_market_config
from encore.market.settlement import settle_day
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import ConditionalBoxes
from encore.tighten.tube import lqr_gain
from encore.utils.stats import stable_seed
from paper_revision_experiments import offers_for_variant

OUT = REPO / "results" / "phase6"
SEED = 20260610
VARIANTS = ("single005", "ctxfree")


def main():
    p = load_params()
    cfg = load_market_config()
    pr = cfg["product"]
    K = lqr_gain(p, p5.N_STATES, r_u=1.0 / (p5.R_GAIN_KW * 1e3) ** 2)
    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=p5.SOURCE)
    feats, recs = pool_fit.features_records()
    cb03 = ConditionalBoxes(feats, recs, eps=p5.EPS, k=80, k_cal=150)
    cb005 = ConditionalBoxes(feats, recs, eps=p5.EPS_SAFE, k=80, k_cal=150)
    rows = []
    for week, start in p5.WEEKS.items():
        for DATE in p5.week_dates(start):
            prices = load_day_prices(DATE)
            weather = load_day_weather(DATE)
            pi_rt5 = rtm_to_5min(prices["rtm_15min"])
            base = baseline_day(p, p5.T_WB)
            offs = {v: offers_for_variant(v, p, cfg, cb03, cb005, prices, weather, K)
                    for v in VARIANTS}
            for seed in range(20):
                rng = np.random.default_rng(stable_seed(DATE, seed))
                pool = RealRecordPool(p.Q_IT_nom, seed=stable_seed("replay", seed),
                                      role="eval", source=p5.SOURCE)
                acts = rng.uniform(size=24) < pr["p_act"]
                w_day = np.array([pool.draw_hour(h)[0] for h in range(24)])
                dew = np.asarray(weather["dew_resid_hourly"], dtype=float)
                run_b1 = run_day(p, offs[VARIANTS[0]], acts, w_day, dew, K,
                                 controller="idle")
                led_b1 = settle_day(np.zeros(24), np.zeros(24),
                                    prices["pi_cap_hourly"], run_b1["P_cool_W"],
                                    base["P_base_W"], pi_rt5, run_b1["T_j"],
                                    gamma_mult=pr["gamma_mult"])
                for v in VARIANTS:
                    plans = offs[v]
                    run = run_day(p, plans, acts, w_day, dew, K, controller="mpc")
                    q = np.array([pl.q_W for pl in plans])
                    r = acts.astype(float) * 0.5 * (q > 0)
                    led = settle_day(q, r, prices["pi_cap_hourly"], run["P_cool_W"],
                                     base["P_base_W"], pi_rt5, run["T_j"],
                                     gamma_mult=pr["gamma_mult"])
                    obl = (r * q) > 0
                    req = r * q * 3600.0
                    rows.append({
                        "variant": v, "week": week, "date": DATE, "seed": seed,
                        "revenue_usd": led["revenue_usd"],
                        "rebound_usd": led["rt_cost_usd"] - led_b1["rt_cost_usd"],
                        "penalty_usd": led["penalty_usd"],
                        "dwear_usd": led["degradation_usd"]
                                     - led_b1["degradation_usd"],
                        "shortfall_kWh": led["shortfall_kWh_total"],
                        "mv": led["profit_usd"] - led_b1["profit_usd"],
                        "sum_q_kW": float(q.sum() / 1e3),
                        "delivery_ratio": float(1.0 - led["shortfall_J"].sum()
                                                / req.sum()) if req.sum() > 0
                                          else np.nan,
                        "warm": run["infeasible_starts"],
                        "viol_K": float(max(0.0, run["T_j"].max() - p.T_max))})
        print(f"  {week} done", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "mainline_b7b8.csv", index=False)
    print("B7/B8 mainline runs complete")


if __name__ == "__main__":
    main()
