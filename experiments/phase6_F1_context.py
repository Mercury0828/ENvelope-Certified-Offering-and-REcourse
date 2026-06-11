"""Phase 6 — F1, the headline figure: when is certification possible, and what is
context worth (guide 6.4, §8; reworked after the pre-paper audit, D-047).

Panel (a) — the certification wall: max certifiable offer vs workload-volatility scale
kappa (fraction of the Borg-2019 cell-a hall residual magnitude), dry day. The Borg
cell (kappa = 1, a deliberately hard mixed-batch workload at full-hall scale, ~±25%/h)
sits at/beyond the wall for d = 30; steadier halls certify deep offers. All curves use
the FULLY honest chain: held-out day-block fit, causal forecast, conformal W(c) with
a-priori face allocation, tube margins incl. the e0 warm-start ball.

Panel (b) — the weather coupling: certifiable offer vs day-ahead dew point at
kappa = 0.5 (the "steadier hall" reference scenario used in the closed-loop F2 run),
showing conditional vs context-free certification and the deterministic ceiling.

Outputs: F1_context.{pdf,png}, F1_kappa.csv, F1_dew.csv, provenance.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from encore.control.fallback import certified_max_q
from encore.data.residuals import RealRecordPool
from encore.envelope.geometry import max_q
from encore.envelope.reachability import EnvelopeSpec, build_lifted
from encore.market.offering import ready_state_for
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import Box, ConditionalBoxes
from encore.tighten.tube import build_tube, lqr_gain
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase6"
SEED = 20260610
HOD = 14
KAPPA_GRID = [0.1, 0.25, 0.4, 0.5, 0.65, 0.8, 1.0]
T_DEW_GRID = np.arange(8.0, 27.0, 2.0)
KAPPA_REF = 0.5


def boxes_for(p, kappa, eps=0.1):
    pool = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", scale=kappa)
    feats, recs = pool.features_records()
    return ConditionalBoxes(feats, recs, eps=eps, k=80, k_cal=150)


def F_of(p, T_dew, box: Box | None, K, d_min=30.0) -> float:
    spec = EnvelopeSpec(n_states=2, T_dew=float(T_dew), d_min=d_min)
    if box is None:
        return max(max_q(build_lifted(p, spec), ready_state_for(p, float(T_dew))), 0.0)
    x = ready_state_for(p, float(T_dew) + box.w_D)
    tube = build_tube(p, 2, 12, box.w_Q_sym, box.w_D, K=K, E_budget=box.E_hi)
    return max(certified_max_q(p, spec, tube, x), 0.0)


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    K = lqr_gain(p, r_u=1.0 / (10e3) ** 2)
    T_DEW_A = 12.0

    # ---- panel (a): certification wall vs kappa ----
    rows_a = []
    for kp in KAPPA_GRID:
        cb = boxes_for(p, kp, eps=0.1)
        cb05 = boxes_for(p, kp, eps=0.05)
        b = cb.box(RealRecordPool.hour_features(HOD))
        b05 = cb05.box(RealRecordPool.hour_features(HOD))
        rows_a.append({
            "kappa": kp,
            "F_kW": F_of(p, T_DEW_A, None, K) / 1e3,
            "Ft30_kW": F_of(p, T_DEW_A, b, K, 30.0) / 1e3,
            "Ft15_kW": F_of(p, T_DEW_A, b, K, 15.0) / 1e3,
            "Ft30_eps05_kW": F_of(p, T_DEW_A, b05, K, 30.0) / 1e3,
        })
        print(f"kappa {kp}: F̃30 {rows_a[-1]['Ft30_kW']:.1f}  F̃15 {rows_a[-1]['Ft15_kW']:.1f} kW")
    dfa = pd.DataFrame(rows_a)
    dfa.to_csv(OUT / "F1_kappa.csv", index=False)
    for col in ("Ft30_kW", "Ft15_kW", "Ft30_eps05_kW"):
        assert (np.diff(dfa[col]) <= 1e-6).all(), f"{col} not non-increasing in kappa"

    # ---- panel (b): dew coupling at kappa_ref ----
    cb = boxes_for(p, KAPPA_REF, eps=0.1)
    box_h = cb.box(RealRecordPool.hour_features(HOD))
    sample = [cb.box(RealRecordPool.hour_features(h)) for h in range(24)]
    uni = Box(w_Q_hi=max(b.w_Q_hi for b in sample), E_hi=max(b.E_hi for b in sample),
              w_D_hi=max(b.w_D_hi for b in sample))
    rows_b = []
    for td in T_DEW_GRID:
        rows_b.append({
            "T_dew": td,
            "F_kW": F_of(p, td, None, K) / 1e3,
            "Ft30_kW": F_of(p, td, box_h, K, 30.0) / 1e3,
            "Ft15_kW": F_of(p, td, box_h, K, 15.0) / 1e3,
            "Ft30_uniform_kW": F_of(p, td, uni, K, 30.0) / 1e3,
        })
    dfb = pd.DataFrame(rows_b)
    dfb.to_csv(OUT / "F1_dew.csv", index=False)
    for col in dfb.columns[1:]:
        assert (np.diff(dfb[col]) <= 1e-6).all(), f"{col} not monotone in T_dew"
    assert (dfb["F_kW"] >= dfb["Ft30_kW"] - 1e-9).all()
    assert (dfb["Ft30_kW"] >= dfb["Ft30_uniform_kW"] - 1e-9).all()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 4.1))
    ax1.plot(dfa.kappa, dfa.F_kW, color="0.55", lw=2.0, label="F — no uncertainty")
    ax1.plot(dfa.kappa, dfa.Ft15_kW, color="C2", lw=2.0, marker="v", ms=4,
             label="F̃ certified, d = 15 min (ε = 0.1)")
    ax1.plot(dfa.kappa, dfa.Ft30_kW, color="C0", lw=2.2, marker="o", ms=4,
             label="F̃ certified, d = 30 min (ε = 0.1)")
    ax1.plot(dfa.kappa, dfa.Ft30_eps05_kW, color="C0", lw=1.3, ls="--",
             label="F̃ certified, d = 30 min (ε = 0.05)")
    ax1.axvline(1.0, color="C3", lw=1, ls=":")
    ax1.annotate("Borg-2019 cell-a\n(mixed batch, full hall)", xy=(0.97, 60),
                 fontsize=7.5, ha="right", color="C3")
    ax1.axvline(KAPPA_REF, color="0.4", lw=1, ls=":")
    ax1.annotate("F2 reference\nscenario", xy=(KAPPA_REF + 0.02, 75), fontsize=7.5,
                 color="0.4")
    ax1.set_xlabel("workload volatility scale κ (× Borg-2019 cell-a)")
    ax1.set_ylabel("max certifiable offer [kW per MW IT]")
    ax1.set_title(f"(a) the certification wall (dry day, T_dew = {T_DEW_A:.0f} °C)")
    ax1.legend(fontsize=7.5)

    ax2.plot(dfb.T_dew, dfb.F_kW, color="0.55", lw=2.0, label="F — no uncertainty")
    ax2.plot(dfb.T_dew, dfb.Ft15_kW, color="C2", lw=2.0, marker="v", ms=4,
             label="F̃ conditional, d = 15")
    ax2.plot(dfb.T_dew, dfb.Ft30_kW, color="C0", lw=2.2, marker="o", ms=4,
             label="F̃ conditional, d = 30")
    ax2.plot(dfb.T_dew, dfb.Ft30_uniform_kW, color="C3", lw=2.0,
             label="F̃ context-free, d = 30")
    ax2.set_xlabel("day-ahead dew-point forecast $T_{dew}$ [°C]")
    ax2.set_title(f"(b) weather coupling (κ = {KAPPA_REF})")
    ax2.legend(fontsize=7.5)
    fig.suptitle("F1 — certified envelope vs workload volatility, duration, weather and "
                 "information (held-out fit, causal forecast, e₀-covered tube)", y=1.02)
    fig.tight_layout()
    savefig(fig, OUT / "F1_context")
    plt.close(fig)

    write_manifest(OUT / "provenance_F1.json", seed=SEED,
                   extra={"experiment": "phase6_F1_context", "hod": HOD,
                          "kappa_grid": KAPPA_GRID, "kappa_ref": KAPPA_REF,
                          "regime_feature_finding": "non-informative on Borg-2019 (D-043)"})
    print("\nF1 complete; monotonicity + ordering assertions passed.")


if __name__ == "__main__":
    main()
