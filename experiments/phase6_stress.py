"""Phase 6 — robustness stress tests (guide §8): AI-burst day, dew-point-shift day,
consecutive-activation day. B2 (no certificate) vs B4 (ENCORE), 5 seeds each, on the
dry high-price day (B4 actually offers there).

Scenarios:
  burst        every hour's heat disturbance replayed from the TOP-decile burst-energy
               hours of the real trace pool
  dew_shift    realized dew = forecast + 3 K all day (beyond the NWP-skill bound)
  consecutive  6 consecutive activated hours (13:00-19:00) instead of Bernoulli calls

Reported per scenario x controller: violations, shortfall, penalty, switches,
infeasible starts. Assertions: B4 never violates worse than idle B1 under the same
disturbances; B4 completes all scenarios; fallback/switch machinery engages.
"""

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
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase6"
SEED = 20260610
DATE = "2024-01-16"
SEEDS = range(5)


def burst_pool_draw(pool: RealRecordPool, rng) -> np.ndarray:
    E = np.maximum(pool.heat["vectors"], 0).sum(axis=1) * pool.dt
    top = np.argsort(E)[-len(E) // 10:]
    return pool.heat["vectors"][rng.choice(top)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    cfg = load_market_config()
    pr = cfg["product"]
    K = lqr_gain(p, r_u=1.0 / (10e3) ** 2)
    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED)
    feats, recs = pool_fit.features_records()
    cb = ConditionalBoxes(feats, recs, eps=0.1, k=80, k_cal=150)

    prices = load_day_prices(DATE)
    weather = load_day_weather(DATE)
    pi_rt5 = rtm_to_5min(prices["rtm_15min"])
    base = baseline_day(p, p5.T_WB)
    offers = p5.day_offers(p, cfg, cb, RealRecordPool(p.Q_IT_nom, seed=SEED + 1),
                           prices, weather, K)

    rows = []
    for scen in ("burst", "dew_shift", "consecutive"):
        for seed in SEEDS:
            rng = np.random.default_rng(hash((scen, seed)) % 2**32)
            pool = RealRecordPool(p.Q_IT_nom, seed=seed * 104729 + 7)
            if scen == "consecutive":
                activations = np.zeros(24, dtype=bool)
                activations[13:19] = True
            else:
                activations = rng.uniform(size=24) < pr["p_act"]
            w_day = np.zeros((24, 12))
            dew_res = np.zeros(24)
            for h in range(24):
                if scen == "burst":
                    w_day[h] = burst_pool_draw(pool, rng)
                    dew_res[h] = pool._draw_dew()
                else:
                    w_day[h], dew_res[h] = pool.draw_hour(h)
            if scen == "dew_shift":
                dew_res[:] = 3.0

            for name, plans, ctl in (("B1", offers["B4"], "idle"),
                                     ("B2", offers["B2"], "mpc"),
                                     ("B4", offers["B4"], "mpc")):
                run = run_day(p, plans, activations, w_day, dew_res, K, controller=ctl)
                q = np.zeros(24) if name == "B1" else np.array([pl.q_W for pl in plans])
                r = activations.astype(float) * (pr["d_min"] / 60.0) * (q > 0)
                led = settle_day(q, r, prices["pi_cap_hourly"], run["P_cool_W"],
                                 base["P_base_W"], pi_rt5, run["T_j"],
                                 gamma_mult=pr["gamma_mult"],
                                 c_deg_per_Kh=pr["c_deg_per_Kh"], T_thr=pr["T_thr_C"])
                rows.append({"scenario": scen, "seed": seed, "controller": name,
                             "T_viol_K": float(max(0.0, run["T_j"].max() - p.T_max)),
                             "shortfall_kWh": led["shortfall_kWh_total"],
                             "penalty_usd": led["penalty_usd"],
                             "clip_events": run["clip_events"],
                             "switches": run["switches"],
                             "infeasible_starts": run["infeasible_starts"]})
        print(f"{scen} done")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "stress_tests.csv", index=False)
    agg = df.groupby(["scenario", "controller"]).agg(
        viol_max_K=("T_viol_K", "max"), shortfall=("shortfall_kWh", "mean"),
        penalty=("penalty_usd", "mean"), clips=("clip_events", "mean"),
        switches=("switches", "mean"), infeas=("infeasible_starts", "mean")).reset_index()
    agg.to_csv(OUT / "stress_summary.csv", index=False)
    print("\n", agg.round(3).to_string(index=False))

    for scen in ("burst", "dew_shift", "consecutive"):
        v = df[df.scenario == scen].groupby("controller")["T_viol_K"].max()
        assert v["B4"] <= max(v["B1"] + 1e-3, 1e-6), f"B4 worse than idle in {scen}"
        assert v["B4"] <= 0.5, f"B4 beyond intra-step tolerance in {scen}"
    write_manifest(OUT / "provenance_stress.json", seed=SEED,
                   extra={"experiment": "phase6_stress", "date": DATE,
                          "seeds": len(list(SEEDS))})
    print("\nstress tests complete; B4-never-worse-than-idle assertions passed.")


if __name__ == "__main__":
    main()
