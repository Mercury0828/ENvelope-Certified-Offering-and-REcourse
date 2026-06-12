"""Review-revision experiments (R1-R4, 2026-06-11):
R2 premise accounting: nested design rerun (20 seeds) logging start errors vs
   the e0 ball; cross-tab failures by (in-ball, in-W_del).
R4 ablations (5 seeds each): single-set eps=0.3, single-set eps=0.05,
   context-free nested, window-only certification (no hour-energy row).
R3 model sensitivity: envelope-level parameter grid + closed-loop mismatch
   (perturbed plant vs nominal certificates, scarcity week).
R1 product sensitivity: offering value/commitment vs p_act and gamma.
Outputs: results/phase6/revision_{ablation,premise,sensitivity,product}.{csv,json}
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))

import dataclasses
import json

import numpy as np
import pandas as pd

import phase5_weeks as p5
from encore.control.fallback import certified_max_q
from encore.data.loaders import load_day_prices, load_day_weather, rtm_to_5min
from encore.data.residuals import RealRecordPool
from encore.envelope.reachability import EnvelopeSpec
from encore.market import offering as offmod
from encore.market.baseline import baseline_day
from encore.market.dayrun import run_day
from encore.market.offering import make_offers, ready_state_for
from encore.market.portfolio import load_market_config
from encore.market.settlement import settle_day
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import Box, ConditionalBoxes
from encore.tighten.tube import build_tube, lqr_gain
from encore.utils.provenance import write_manifest
from encore.utils.stats import clopper_pearson, stable_seed

OUT = REPO / "results" / "phase6"
SEED = 20260610
E0_BALL = 1.25


def uniform_boxes(cb):
    sample = [cb.box(RealRecordPool.hour_features(h)) for h in range(24)]
    uni = Box(w_Q_hi=max(b.w_Q_hi for b in sample), E_hi=max(b.E_hi for b in sample),
              w_D_hi=max(b.w_D_hi for b in sample))
    return [uni] * 24


def offers_for_variant(variant, p, cfg, cb03, cb005, prices, weather, K):
    rtm_h = prices["rtm_15min"].reshape(24, 4).mean(axis=1)
    contexts, bx3, bx5 = [], [], []
    for h in range(24):
        contexts.append({"T_dew_fc": float(weather["T_dew_fc_hourly"][h]),
                         "T_wb": p5.T_WB,
                         "pi_cap": float(prices["pi_cap_hourly"][h]),
                         "pi_rt_event": float(rtm_h[h]),
                         "pi_rt_recovery": float(rtm_h[(h + 1) % 24])})
        bx3.append(cb03.box(RealRecordPool.hour_features(h)))
        bx5.append(cb005.box(RealRecordPool.hour_features(h)))
    pr = cfg["product"]
    kw = dict(d_min=float(pr["d_min"]), p_act=pr["p_act"],
              c_deg_per_Kh=pr["c_deg_per_Kh"], T_thr=pr["T_thr_C"], n_grid=10,
              n_states=p5.N_STATES, gamma_mult=pr["gamma_mult"])
    if variant == "nested":
        return make_offers(p, contexts, "certified", boxes=bx3, boxes_safe=bx5,
                           K=K, eps=p5.EPS, **kw)
    if variant == "single03":
        return make_offers(p, contexts, "certified", boxes=bx3, K=K, eps=p5.EPS, **kw)
    if variant == "single005":
        return make_offers(p, contexts, "certified", boxes=bx5, K=K,
                           eps=p5.EPS_SAFE, **kw)
    if variant == "ctxfree":
        return make_offers(p, contexts, "certified", boxes=uniform_boxes(cb03),
                           boxes_safe=uniform_boxes(cb005), K=K, eps=p5.EPS, **kw)
    if variant == "windowonly":
        orig = offmod.EnvelopeSpec
        offmod.EnvelopeSpec = lambda **kws: orig(delivery="sustained", **kws)
        try:
            return make_offers(p, contexts, "certified", boxes=bx3, boxes_safe=bx5,
                               K=K, eps=p5.EPS, **kw)
        finally:
            offmod.EnvelopeSpec = orig
    raise ValueError(variant)


def closed_loop(variants):
    p = load_params()
    cfg = load_market_config()
    pr = cfg["product"]
    K = lqr_gain(p, p5.N_STATES, r_u=1.0 / (p5.R_GAIN_KW * 1e3) ** 2)
    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=p5.SOURCE)
    feats, recs = pool_fit.features_records()
    cb03 = ConditionalBoxes(feats, recs, eps=p5.EPS, k=80, k_cal=150)
    cb005 = ConditionalBoxes(feats, recs, eps=p5.EPS_SAFE, k=80, k_cal=150)
    rows, premise = [], []
    for week, start in p5.WEEKS.items():
        for DATE in p5.week_dates(start):
            prices = load_day_prices(DATE)
            weather = load_day_weather(DATE)
            pi_rt5 = rtm_to_5min(prices["rtm_15min"])
            base = baseline_day(p, p5.T_WB)
            offs = {v: offers_for_variant(v, p, cfg, cb03, cb005, prices, weather, K)
                    for v in variants}
            bx3 = [cb03.box(RealRecordPool.hour_features(h)) for h in range(24)]
            max_seeds = max(s for _, s in variants.items())
            for seed in range(max_seeds):
                rng = np.random.default_rng(stable_seed(DATE, seed))
                pool = RealRecordPool(p.Q_IT_nom, seed=stable_seed("replay", seed),
                                      role="eval", source=p5.SOURCE)
                acts = rng.uniform(size=24) < pr["p_act"]
                w_day = np.array([pool.draw_hour(h)[0] for h in range(24)])
                dew = np.asarray(weather["dew_resid_hourly"], dtype=float)
                run_b1 = run_day(p, offs["nested"], acts, w_day, dew, K,
                                 controller="idle")
                led_b1 = settle_day(np.zeros(24), np.zeros(24),
                                    prices["pi_cap_hourly"], run_b1["P_cool_W"],
                                    base["P_base_W"], pi_rt5, run_b1["T_j"],
                                    gamma_mult=pr["gamma_mult"])
                for v, n_seeds in variants.items():
                    if seed >= n_seeds:
                        continue
                    plans = offs[v]
                    run = run_day(p, plans, acts, w_day, dew, K, controller="mpc")
                    q = np.array([pl.q_W for pl in plans])
                    r = acts.astype(float) * 0.5 * (q > 0)
                    led = settle_day(q, r, prices["pi_cap_hourly"],
                                     run["P_cool_W"], base["P_base_W"], pi_rt5,
                                     run["T_j"], gamma_mult=pr["gamma_mult"])
                    obl = (r * q) > 0
                    fails = (led["shortfall_J"][obl] > 1e-6).sum()
                    clean_in_box = 0
                    for h in np.where(obl & (led["shortfall_J"] > 1e-6))[0]:
                        in_box = bx3[h].contains(
                            w_day[h].max(),
                            float(np.maximum(w_day[h], 0).sum() * p.dt_ctrl),
                            dew[h])
                        if h not in run["infeasible_hours"] and in_box:
                            clean_in_box += 1
                    rows.append({
                        "variant": v, "week": week, "date": DATE, "seed": seed,
                        "mv": led["profit_usd"] - led_b1["profit_usd"],
                        "sum_q_kW": float(q.sum() / 1e3),
                        "n_obl": int(obl.sum()), "n_fail": int(fails),
                        "clean_in_box": clean_in_box,
                        "viol_K": float(max(0.0, run["T_j"].max() - p.T_max)),
                        "warm": run["infeasible_starts"]})
                    if v == "nested":
                        for h, err in run["start_err_hourly"]:
                            if obl[h]:
                                premise.append({
                                    "date": DATE, "seed": seed, "hour": h,
                                    "start_err_K": err,
                                    "in_ball": err <= E0_BALL,
                                    "warm": h in run["infeasible_hours"],
                                    "in_box": bool(bx3[h].contains(
                                        w_day[h].max(),
                                        float(np.maximum(w_day[h], 0).sum()
                                              * p.dt_ctrl), dew[h])),
                                    "failed": bool(led["shortfall_J"][h] > 1e-6)})
        print(f"  {week} done", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "revision_ablation.csv", index=False)
    pd.DataFrame(premise).to_csv(OUT / "revision_premise.csv", index=False)


def sensitivity():
    cfg = load_market_config()
    base_p = load_params()
    K0 = lqr_gain(base_p, 3, r_u=1.0 / (p5.R_GAIN_KW * 1e3) ** 2)

    def Ft(p, K, e0=E0_BALL, dew=12.0):
        pool = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=p5.SOURCE)
        feats, recs = pool.features_records()
        b = ConditionalBoxes(feats, recs, eps=p5.EPS, k=80, k_cal=150).box(
            RealRecordPool.hour_features(14))
        bs = ConditionalBoxes(feats, recs, eps=p5.EPS_SAFE, k=80, k_cal=150).box(
            RealRecordPool.hour_features(14))
        spec = EnvelopeSpec(n_states=3, T_dew=dew, d_min=30.0)
        x = ready_state_for(p, dew + bs.w_D, 3)
        tube = build_tube(p, 3, 12, bs.w_Q_sym, bs.w_D, K=K, E_budget=bs.E_hi,
                          e0_K=e0, w_Q_del=b.w_Q_sym, E_del=b.E_hi)
        return max(certified_max_q(p, spec, tube, x), 0) / 1e3

    rows = [{"param": "nominal", "F30_dry_kW": Ft(base_p, K0),
             "F30_humid_kW": Ft(base_p, K0, dew=22.0)}]
    perturbs = {"C_w -20%": {"C_w": 0.8}, "C_w +20%": {"C_w": 1.2},
                "C_f -20%": {"C_f": 0.8}, "C_f +20%": {"C_f": 1.2},
                "h_jw -20%": {"h_jw": 0.8}, "h_jw +20%": {"h_jw": 1.2},
                "delta_c +1K": {"delta_cond": "+1"},
                "e0 x2 (2.5K)": {"e0": 2.5},
                "COP slope -20%": {"cop_c1": 0.8}}
    for name, mod in perturbs.items():
        p = dataclasses.replace(base_p)
        e0 = E0_BALL
        for k, v in mod.items():
            if k == "e0":
                e0 = v
            elif v == "+1":
                p = dataclasses.replace(p, **{k: getattr(base_p, k) + 1.0})
            else:
                p = dataclasses.replace(p, **{k: getattr(base_p, k) * v})
        K = lqr_gain(p, 3, r_u=1.0 / (p5.R_GAIN_KW * 1e3) ** 2)
        rows.append({"param": name, "F30_dry_kW": Ft(p, K, e0=e0),
                     "F30_humid_kW": Ft(p, K, e0=e0, dew=22.0)})
    pd.DataFrame(rows).round(1).to_csv(OUT / "revision_sensitivity.csv", index=False)

    # closed-loop mismatch: nominal certificates, perturbed plant (scarcity week)
    pr = cfg["product"]
    K = K0
    pool_fit = RealRecordPool(base_p.Q_IT_nom, seed=SEED, role="fit", source=p5.SOURCE)
    feats, recs = pool_fit.features_records()
    cb03 = ConditionalBoxes(feats, recs, eps=p5.EPS, k=80, k_cal=150)
    cb005 = ConditionalBoxes(feats, recs, eps=p5.EPS_SAFE, k=80, k_cal=150)
    mism = []
    p_pert = dataclasses.replace(base_p, C_w=base_p.C_w * 0.8,
                                 h_jw=base_p.h_jw * 0.8,
                                 delta_cond=base_p.delta_cond + 1.0)
    for DATE in p5.week_dates(p5.WEEKS["w03-jan-scarcity"]):
        prices = load_day_prices(DATE)
        weather = load_day_weather(DATE)
        pi_rt5 = rtm_to_5min(prices["rtm_15min"])
        base = baseline_day(base_p, p5.T_WB)
        plans = offers_for_variant("nested", base_p, cfg, cb03, cb005, prices,
                                   weather, K)
        for seed in range(5):
            rng = np.random.default_rng(stable_seed(DATE, seed))
            pool = RealRecordPool(base_p.Q_IT_nom, seed=stable_seed("replay", seed),
                                  role="eval", source=p5.SOURCE)
            acts = rng.uniform(size=24) < pr["p_act"]
            w_day = np.array([pool.draw_hour(h)[0] for h in range(24)])
            dew = np.asarray(weather["dew_resid_hourly"], dtype=float)
            run = run_day(p_pert, plans, acts, w_day, dew, K, controller="mpc")
            q = np.array([pl.q_W for pl in plans])
            r = acts.astype(float) * 0.5 * (q > 0)
            led = settle_day(q, r, prices["pi_cap_hourly"], run["P_cool_W"],
                             base["P_base_W"], pi_rt5, run["T_j"],
                             gamma_mult=pr["gamma_mult"])
            obl = (r * q) > 0
            mism.append({"date": DATE, "seed": seed,
                         "viol_K": float(max(0.0, run["T_j"].max() - base_p.T_max)),
                         "n_obl": int(obl.sum()),
                         "n_fail": int((led["shortfall_J"][obl] > 1e-6).sum())})
    pd.DataFrame(mism).to_csv(OUT / "revision_mismatch.csv", index=False)


def product_sensitivity():
    p = load_params()
    cfg = load_market_config()
    K = lqr_gain(p, p5.N_STATES, r_u=1.0 / (p5.R_GAIN_KW * 1e3) ** 2)
    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=p5.SOURCE)
    feats, recs = pool_fit.features_records()
    cb03 = ConditionalBoxes(feats, recs, eps=p5.EPS, k=80, k_cal=150)
    cb005 = ConditionalBoxes(feats, recs, eps=p5.EPS_SAFE, k=80, k_cal=150)
    rows = []
    for DATE in ("2024-01-16", "2024-04-03"):
        prices = load_day_prices(DATE)
        weather = load_day_weather(DATE)
        for p_act in (0.05, 0.15, 0.30):
            for gam in (1.5, 2.0, 3.0):
                cfg2 = json.loads(json.dumps(cfg))
                cfg2["product"]["p_act"] = p_act
                cfg2["product"]["gamma_mult"] = gam
                plans = offers_for_variant("nested", p, cfg2, cb03, cb005, prices,
                                           weather, K)
                rows.append({"date": DATE, "p_act": p_act, "gamma": gam,
                             "sum_q_kW": round(sum(pl.q_W for pl in plans) / 1e3, 1),
                             "exp_value": round(sum(pl.expected_value_usd
                                                    for pl in plans), 1)})
    pd.DataFrame(rows).to_csv(OUT / "revision_product.csv", index=False)


if __name__ == "__main__":
    product_sensitivity()
    print("product sensitivity done", flush=True)
    sensitivity()
    print("model sensitivity + mismatch done", flush=True)
    closed_loop({"nested": 20, "single03": 5, "single005": 5, "ctxfree": 5,
                 "windowonly": 5})
    write_manifest(OUT / "provenance_revision.json", seed=SEED,
                   extra={"experiment": "paper_revision_experiments"})
    print("ablation + premise done", flush=True)
