"""Phase 0 — supply-temperature sweep ([Gheni26] calibration experiment).

Steady state at nominal IT load, pump at nominal flow, q_rej = Q_IT; sweep the supply
temperature 17 -> 25 degC and record total cooling power from the fitted power map.
Acceptance (trend-based): the 17->25 sweep reduces cooling power by tens of percent —
40-75% band around the ~63.3% [Gheni26] anchor. The fitted COP coefficients are
reported and must match config/plant.yaml (test-guarded).

Writes the sweep plot (PDF+PNG), a CSV table, and a provenance manifest to results/phase0/.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from encore.plant import power
from encore.plant.params import load_params
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase0"
SEED = 20260610  # deterministic experiment; recorded by convention


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    g = p.gheni
    T_wb = float(g["T_wb_calib_C"])

    fit = power.fit_cop_coefficients(p)
    assert abs(fit["cop_c0"] - p.cop_c0) / p.cop_c0 < 1e-4, "config cop_c0 stale vs fit"
    assert abs(fit["cop_c1_per_K"] - p.cop_c1) / p.cop_c1 < 1e-4, "config cop_c1 stale vs fit"

    T_in = np.linspace(g["T_supply_lo_C"], g["T_supply_hi_C"], 33)
    P_pump = float(power.pump_power(p, p.m_dot_nom))
    P_chiller = np.asarray(power.chiller_power(p, p.Q_IT_nom, T_in, T_wb))
    P_cool = P_pump + P_chiller
    cop_vals = np.asarray(power.cop(p, T_in, T_wb))

    df = pd.DataFrame({
        "T_supply_C": T_in,
        "COP_eff": cop_vals,
        "P_pump_kW": P_pump / 1e3,
        "P_chiller_kW": P_chiller / 1e3,
        "P_cool_kW": P_cool / 1e3,
        "P_cool_rel_to_17C": P_cool / P_cool[0],
    })
    df.to_csv(OUT / "supply_sweep.csv", index=False)

    reduction = (P_cool[0] - P_cool[-1]) / P_cool[0]
    assert 0.40 <= reduction <= 0.75, f"sweep reduction {reduction:.1%} outside 40-75% band"

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.8))
    ax1.plot(T_in, P_cool / 1e3, label="$P_{cool}$ total")
    ax1.plot(T_in, P_chiller / 1e3, "--", label="chiller")
    ax1.axhline(P_pump / 1e3, ls=":", color="gray", label="pump (nominal)")
    ax1.set_xlabel("supply temperature $T_{in}$ [°C]")
    ax1.set_ylabel("cooling power [kW]")
    ax1.set_title(f"17→25 °C sweep: −{reduction:.1%}\n"
                  f"(anchor [Gheni26] ≈ −{g['power_reduction_target']:.1%})")
    ax1.legend()
    ax2.plot(T_in, cop_vals, color="C2")
    ax2.set_xlabel("supply temperature $T_{in}$ [°C]")
    ax2.set_ylabel("effective COP [-]")
    ax2.set_title(f"COP = {p.cop_c0:.3f} + {p.cop_c1:.3f}·($T_{{supply}}$ − $T_{{wb}}$)\n"
                  f"$T_{{wb}}$ = {T_wb:.0f} °C")
    fig.tight_layout()
    savefig(fig, OUT / "supply_sweep")
    plt.close(fig)

    write_manifest(OUT / "provenance_supply_sweep.json", seed=SEED,
                   extra={"experiment": "phase0_supply_sweep",
                          "fitted": fit, "achieved_reduction": float(reduction)})
    print(f"fitted COP coefficients: c0 = {fit['cop_c0']:.7f}, c1 = {fit['cop_c1_per_K']:.7f} /K")
    print(f"P_cool(17 °C) = {P_cool[0]/1e3:.1f} kW -> P_cool(25 °C) = {P_cool[-1]/1e3:.1f} kW")
    print(f"achieved reduction = {reduction:.1%}  (acceptance band 40-75%)")
    print("all Phase-0 supply-sweep assertions passed.")


if __name__ == "__main__":
    main()
