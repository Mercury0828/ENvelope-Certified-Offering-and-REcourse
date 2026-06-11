"""Phase 4 — one simulated day end-to-end, B1..B4 (guide §11 acceptance).

Real inputs: ERCOT HB_HOUSTON DAM/RTM prices + ECRS MCPC (pi^cap) and KIAH hourly dew
point for one day. Disturbances/activations: seeded synthetic conditional process
(trace-residual refit is Phase-5 work). Controllers:

  B1  no-market MPC (idle; defines the frozen baseline P-bar, D-035)
  B2  DA offering on the DETERMINISTIC envelope + margin-free MPC (no certificate)
  B3  DA offering on a 20-scenario empirical (SAA) box + its MPC (no guarantee)
  B4  ENCORE: conformal W(c) -> tube-tightened F-tilde + certified fallback/MPC

Acceptance (asserted): all four run the full day; profit decomposition reconciles to
the settlement formulas exactly; offers respect their envelope by construction.
Outputs: results/phase4/ ledger CSV, offers+prices figure, day-trajectory figure,
key_numbers.json, provenance.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from encore.data.loaders import load_day_prices, load_day_weather, rtm_to_5min
from encore.data.synthetic import Context, draw_dew_residual, draw_step_heat_devs, generate_history
from encore.market.baseline import baseline_day
from encore.market.dayrun import run_day
from encore.market.offering import make_offers
from encore.market.settlement import settle_day
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import Box, ConditionalBoxes
from encore.tighten.tube import lqr_gain
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase4"
SEED = 20260610
DATES = ["2023-08-17",     # humid Houston summer day (B4 expected to sit out — Phase-3 finding)
         "2024-01-16"]     # very dry winter day, dew -6.7 C (B4 expected to offer)
T_WB = 22.0                # carried from D-007; weather-coupled COP parked
DAY_BURST_SHARE = 0.5      # [est] day-type scenario parameter
P_ACT = 0.15               # [est] activation probability per hour (D-038)
N_SAA = 20                 # B3 scenario count (guide 6.6: 20-50)


def hour_context(h, T_dew_fc):
    return Context(hour=h, burst_share=DAY_BURST_SHARE, T_dew_fc=float(T_dew_fc),
                   sigma_regime=1)


def saa_box(rng, c, p) -> Box:
    """B3's empirical box: elementwise max over N_SAA sampled scenarios (no guarantee)."""
    wq, en, dw = 0.0, 0.0, 0.0
    for _ in range(N_SAA):
        devs = draw_step_heat_devs(rng, c, p.Q_IT_nom)
        wq = max(wq, float(devs.max()))
        en = max(en, float(np.maximum(devs, 0).sum() * p.dt_ctrl))
        dw = max(dw, draw_dew_residual(rng, c))
    return Box(w_Q_hi=wq, E_hi=en, w_D_hi=dw)


def run_date(DATE: str, p, rng):
    prices = load_day_prices(DATE)
    weather = load_day_weather(DATE)
    pi_rt5 = rtm_to_5min(prices["rtm_15min"])
    base = baseline_day(p, T_WB)

    feats, recs = generate_history(rng, p.Q_IT_nom, n=6000)
    cb = ConditionalBoxes(feats, recs, eps=0.1)
    K = lqr_gain(p, r_u=1.0 / (10e3) ** 2)        # authority from Phase-3 sweep

    contexts, boxes_cert, boxes_saa = [], [], []
    rtm_h = prices["rtm_15min"].reshape(24, 4).mean(axis=1)
    for h in range(24):
        c = hour_context(h, weather["T_dew_hourly"][h])
        contexts.append({
            "T_dew_fc": c.T_dew_fc, "T_wb": T_WB,
            "pi_cap": float(prices["pi_cap_hourly"][h]),
            "pi_rt_event": float(rtm_h[h]),
            "pi_rt_recovery": float(rtm_h[(h + 1) % 24]),
        })
        boxes_cert.append(cb.box(c.features()))
        boxes_saa.append(saa_box(rng, c, p))

    offers = {
        "B2": make_offers(p, contexts, "deterministic", K=K, p_act=P_ACT),
        "B3": make_offers(p, contexts, "saa", boxes=boxes_saa, K=K, p_act=P_ACT),
        "B4": make_offers(p, contexts, "certified", boxes=boxes_cert, K=K, p_act=P_ACT),
    }
    for name, plans in offers.items():
        for pl in plans:
            assert pl.q_W <= pl.F_W + 1e-6, f"{name} h{pl.hour}: offer above envelope"

    # ---- realized day (common random numbers across controllers) ----
    activations = rng.uniform(size=24) < P_ACT
    w_day = np.array([draw_step_heat_devs(rng, hour_context(h, weather["T_dew_hourly"][h]),
                                          p.Q_IT_nom) for h in range(24)])
    dew_res = np.array([draw_dew_residual(rng, hour_context(h, weather["T_dew_hourly"][h]))
                        for h in range(24)])

    ledgers, runs = {}, {}
    for name, plans, ctl in (("B1", offers["B4"], "idle"), ("B2", offers["B2"], "mpc"),
                             ("B3", offers["B3"], "mpc"), ("B4", offers["B4"], "mpc")):
        run = run_day(p, plans, activations, w_day, dew_res, K, controller=ctl)
        q = np.zeros(24) if name == "B1" else np.array([pl.q_W for pl in plans])
        r = activations.astype(float) * 0.5 * (q > 0)
        led = settle_day(q, r, prices["pi_cap_hourly"], run["P_cool_W"],
                         base["P_base_W"], pi_rt5, run["T_j"])
        ledgers[name] = led
        runs[name] = run
        assert run["P_cool_W"].size == 288, f"{name}: incomplete day"
        # exact reconciliation (acceptance): profit identity re-derived
        recon = (led["revenue_usd"] - led["rt_cost_usd"] - led["penalty_usd"]
                 - led["degradation_usd"])
        assert abs(recon - led["profit_usd"]) < 1e-9, f"{name}: ledger does not reconcile"

    # ---- report ----
    rows = []
    for name, led in ledgers.items():
        rows.append({
            "controller": name,
            "sum_q_kW": float(sum(pl.q_W for pl in offers.get(name, [])) / 1e3)
                        if name != "B1" else 0.0,
            "revenue_usd": led["revenue_usd"], "rt_cost_usd": led["rt_cost_usd"],
            "penalty_usd": led["penalty_usd"], "degradation_usd": led["degradation_usd"],
            "profit_usd": led["profit_usd"],
            "shortfall_kWh": led["shortfall_kWh_total"],
            "max_T_j": float(runs[name]["T_j"].max()),
            "mpc_switches": runs[name]["switches"],
            "infeasible_starts": runs[name]["infeasible_starts"],
        })
    df = pd.DataFrame(rows)
    df.insert(0, "date", DATE)
    df["market_value_vs_B1_usd"] = df["profit_usd"] - df.loc[df.controller == "B1",
                                                             "profit_usd"].iloc[0]
    df.to_csv(OUT / f"day_ledger_{DATE}.csv", index=False)
    print(f"\n=== {DATE} ===")
    print(df.round(2).to_string(index=False))

    # offers + prices figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 5.6), sharex=True)
    hours = np.arange(24)
    for name, color in (("B2", "C3"), ("B3", "C1"), ("B4", "C0")):
        ax1.step(hours, [pl.q_W / 1e3 for pl in offers[name]], where="post",
                 color=color, label=f"{name} offers")
    ax1.step(hours, [pl.F_W / 1e3 for pl in offers["B4"]], where="post", color="C0",
             ls=":", lw=1, label="B4 envelope F̃")
    for h in np.where(activations)[0]:
        ax1.axvspan(h, h + 1, color="gray", alpha=0.15)
    ax1.set_ylabel("offer q [kW]")
    ax1.legend(fontsize=7, ncol=2)
    ax1.set_title(f"{DATE} (KIAH dew {weather['T_dew_hourly'].min():.0f}–"
                  f"{weather['T_dew_hourly'].max():.0f} °C; shaded = activated)")
    ax2.step(hours, prices["pi_cap_hourly"], where="post", color="C2", label="π_cap (ECRS)")
    ax2.step(hours, rtm_h, where="post", color="C4", label="RTM (hourly mean)")
    ax2.set_ylabel("price [$/MWh]")
    ax2.set_xlabel("hour (US/Central)")
    ax2.legend(fontsize=7)
    fig.tight_layout()
    savefig(fig, OUT / f"day_offers_prices_{DATE}")
    plt.close(fig)

    # day trajectory figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 5.2), sharex=True)
    t = np.arange(288) * 5 / 60
    for name, color in (("B1", "0.6"), ("B2", "C3"), ("B4", "C0")):
        ax1.plot(t, runs[name]["P_cool_W"] / 1e3, color=color, lw=1, label=name)
        ax2.plot(t, runs[name]["T_j"], color=color, lw=1, label=name)
    ax1.axhline(base["P_base_scalar_W"] / 1e3, ls=":", color="k", lw=0.8)
    ax1.set_ylabel("P_cool [kW]")
    ax1.legend(fontsize=7)
    ax2.axhline(p.T_max, ls="--", color="r", lw=0.8)
    ax2.set_ylabel("T_j [°C]")
    ax2.set_xlabel("hour of day")
    fig.tight_layout()
    savefig(fig, OUT / f"day_trajectories_{DATE}")
    plt.close(fig)

    return {"date": DATE, "activated_hours": [int(h) for h in np.where(activations)[0]],
            "ledger": {k: {kk: float(vv) for kk, vv in v.items() if np.isscalar(vv)}
                       for k, v in ledgers.items()}}


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    rng = np.random.default_rng(SEED)
    keys = [run_date(d, p, rng) for d in DATES]
    (OUT / "key_numbers.json").write_text(json.dumps(keys, indent=2), encoding="utf-8")
    write_manifest(OUT / "provenance_one_day.json", seed=SEED,
                   extra={"experiment": "phase4_one_day", "dates": DATES,
                          "p_act": P_ACT, "n_saa": N_SAA})
    print("\nall Phase-4 assertions passed (B1–B4 end-to-end, exact reconciliation, "
          "offers within envelopes).")


if __name__ == "__main__":
    main()
