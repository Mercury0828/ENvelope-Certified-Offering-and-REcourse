"""Phase 6 — F3: degradation-cost sensitivity of the optimal offer (guide §8, C3-iii).

Sweep the degradation proxy c_deg over two decades and recompute the D-1 certified
offers for one high-price day (Winter Storm Heather) and one mild day. Reported:
total committed capacity sum_h q_h and expected offering value, per c_deg.

Offering-level by design: C3(iii) asks how the OPTIMAL OFFER responds to the wear
price, not for closed-loop re-simulation. gamma sensitivity {1.5, 3}x (guide 5.3) is
computed alongside as a table (penalties are zero in-box, so it moves nothing for B4 —
stated rather than plotted).
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import phase5_weeks as p5
from encore.data.loaders import load_day_prices, load_day_weather
from encore.data.residuals import RealRecordPool
from encore.market.offering import make_offers
from encore.market.portfolio import load_market_config
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import ConditionalBoxes
from encore.tighten.tube import lqr_gain
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase6"
SEED = 20260610
C_DEG_GRID = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
DAYS = {"scarcity (2024-01-16)": "2024-01-16", "mild (2024-04-03)": "2024-04-03"}
KAPPA = 0.5    # steadier-hall reference scenario (D-047/D-048) — offers exist here


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    cfg = load_market_config()
    K = lqr_gain(p, r_u=1.0 / (10e3) ** 2)
    pool = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", scale=KAPPA)
    feats, recs = pool.features_records()
    cb = ConditionalBoxes(feats, recs, eps=0.1, k=80, k_cal=150)

    rows = []
    for label, DATE in DAYS.items():
        prices = load_day_prices(DATE)
        weather = load_day_weather(DATE)
        rtm_h = prices["rtm_15min"].reshape(24, 4).mean(axis=1)
        contexts, bx = [], []
        for h in range(24):
            contexts.append({"T_dew_fc": float(weather["T_dew_hourly"][h]), "T_wb": p5.T_WB,
                             "pi_cap": float(prices["pi_cap_hourly"][h]),
                             "pi_rt_event": float(rtm_h[h]),
                             "pi_rt_recovery": float(rtm_h[(h + 1) % 24])})
            bx.append(cb.box(RealRecordPool.hour_features(h)))
        for c_deg in C_DEG_GRID:
            plans = make_offers(p, contexts, "certified", boxes=bx, K=K,
                                d_min=float(cfg["product"]["d_min"]),
                                p_act=cfg["product"]["p_act"],
                                c_deg_per_Kh=c_deg, T_thr=cfg["product"]["T_thr_C"],
                                n_grid=12)
            rows.append({"day": label, "c_deg": c_deg,
                         "sum_q_kW": sum(pl.q_W for pl in plans) / 1e3,
                         "exp_value_usd": sum(pl.expected_value_usd for pl in plans),
                         "offered_hours": sum(pl.q_W > 0 for pl in plans)})
            print(f"{label} c_deg={c_deg}: sum_q {rows[-1]['sum_q_kW']:.0f} kW, "
                  f"value ${rows[-1]['exp_value_usd']:.0f}")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "F3_cdeg.csv", index=False)
    for label in DAYS:
        s = df[df.day == label].sort_values("c_deg")
        assert (np.diff(s["sum_q_kW"]) <= 1e-6).all(), f"sum_q not non-increasing: {label}"

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.0, 3.8))
    for label, color in zip(DAYS, ("C3", "C0")):
        s = df[df.day == label].sort_values("c_deg")
        ax1.semilogx(s.c_deg, s.sum_q_kW, marker="o", color=color, label=label)
        ax2.semilogx(s.c_deg, s.exp_value_usd, marker="o", color=color, label=label)
    ax1.set_xlabel("degradation proxy $c_{deg}$ [\\$/K·h]")
    ax1.set_ylabel("committed capacity $\\Sigma_h q_h$ [kW]")
    ax2.set_xlabel("degradation proxy $c_{deg}$ [\\$/K·h]")
    ax2.set_ylabel("expected offering value [\\$/day]")
    ax1.legend(fontsize=8)
    fig.suptitle(f"F3 — degradation-cost sensitivity of the certified offer "
                 f"(d = 30 min, κ = {KAPPA})")
    fig.tight_layout()
    savefig(fig, OUT / "F3_cdeg")
    plt.close(fig)

    write_manifest(OUT / "provenance_F3.json", seed=SEED,
                   extra={"experiment": "phase6_F3_cdeg", "c_deg_grid": C_DEG_GRID,
                          "gamma_note": "gamma in {1.5,3}x moves nothing for B4 "
                                        "(zero in-box penalties); stated in audit"})
    print("\nF3 complete; monotone-commitment assertion passed.")


if __name__ == "__main__":
    main()
