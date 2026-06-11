"""Phase 6 — F1, the headline figure (final form, D-049/D-050).

Panel (a) — the certification wall: certified S2 offer vs workload-volatility scale
(Borg cell-a residuals scaled by kappa — the volatile mixed-batch reference), with the
REAL dedicated-ML-hall trace (Alibaba PAI 2020) marked at its empirical volatility.
All curves use the honest chain: held-out fit, causal forecast, conformal W(c) with
face allocation, real-NWP dew residuals, tube margins incl. the e0 ball — and the
3-state S2 product the gate approved.

Panel (b) — the weather coupling: certified offer vs the REAL day-ahead dew forecast
on the Alibaba trace, conditional vs context-free, with the deterministic ceiling.

Outputs: F1_context.{pdf,png}, F1_kappa.csv, F1_dew.csv, provenance.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json

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
N_STATES = 3
KAPPA_GRID = [0.1, 0.25, 0.4, 0.5, 0.65, 0.8, 1.0]
T_DEW_GRID = np.arange(8.0, 27.0, 2.0)


def boxes_for(p, source, kappa=1.0, eps=0.1):
    pool = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", scale=kappa, source=source)
    feats, recs = pool.features_records()
    return ConditionalBoxes(feats, recs, eps=eps, k=80, k_cal=150)


def F_of(p, T_dew, box: Box | None, K, d_min=30.0) -> float:
    spec = EnvelopeSpec(n_states=N_STATES, T_dew=float(T_dew), d_min=d_min)
    if box is None:
        return max(max_q(build_lifted(p, spec),
                         ready_state_for(p, float(T_dew), N_STATES)), 0.0)
    x = ready_state_for(p, float(T_dew) + box.w_D, N_STATES)
    tube = build_tube(p, N_STATES, 12, box.w_Q_sym, box.w_D, K=K, E_budget=box.E_hi)
    return max(certified_max_q(p, spec, tube, x), 0.0)


def trace_volatility_kappa(p) -> float:
    """Alibaba hall volatility as a fraction of Borg cell-a, measured on the
    certification-binding statistic (q95 of the hourly-max residual): the PAI hall has
    comparable step noise but thinner burst tails than the mixed-batch Borg cell."""
    q = {}
    for src in ("borg", "alibaba"):
        pool = RealRecordPool(p.Q_IT_nom, seed=0, role="all", source=src)
        hmax = pool.heat["vectors"].max(axis=1)
        q[src] = float(np.quantile(hmax, 0.95))
    return q["alibaba"] / q["borg"]


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    K = lqr_gain(p, N_STATES, r_u=1.0 / (10e3) ** 2)
    T_DEW_A = 12.0

    # ---- panel (a): wall vs kappa on Borg residuals; Alibaba marked empirically ----
    rows_a = []
    for kp in KAPPA_GRID:
        cb = boxes_for(p, "borg", kappa=kp, eps=0.1)
        b = cb.box(RealRecordPool.hour_features(HOD))
        rows_a.append({"kappa": kp,
                       "F_kW": F_of(p, T_DEW_A, None, K) / 1e3,
                       "Ft30_kW": F_of(p, T_DEW_A, b, K, 30.0) / 1e3,
                       "Ft15_kW": F_of(p, T_DEW_A, b, K, 15.0) / 1e3})
        print(f"kappa {kp}: Ft30 {rows_a[-1]['Ft30_kW']:.1f} kW")
    dfa = pd.DataFrame(rows_a)
    dfa.to_csv(OUT / "F1_kappa.csv", index=False)
    for col in ("Ft30_kW", "Ft15_kW"):
        assert (np.diff(dfa[col]) <= 1e-6).all(), f"{col} not non-increasing in kappa"

    kp_ali = trace_volatility_kappa(p)
    cb_ali = boxes_for(p, "alibaba", eps=0.1)
    b_ali = cb_ali.box(RealRecordPool.hour_features(HOD))
    F30_ali = F_of(p, T_DEW_A, b_ali, K, 30.0) / 1e3
    print(f"alibaba empirical kappa = {kp_ali:.2f}, Ft30 = {F30_ali:.1f} kW")

    # ---- panel (b): dew coupling on the Alibaba trace ----
    sample = [cb_ali.box(RealRecordPool.hour_features(h)) for h in range(24)]
    uni = Box(w_Q_hi=max(b.w_Q_hi for b in sample), E_hi=max(b.E_hi for b in sample),
              w_D_hi=max(b.w_D_hi for b in sample))
    rows_b = []
    for td in T_DEW_GRID:
        rows_b.append({"T_dew": td,
                       "F_kW": F_of(p, td, None, K) / 1e3,
                       "Ft30_kW": F_of(p, td, b_ali, K, 30.0) / 1e3,
                       "Ft15_kW": F_of(p, td, b_ali, K, 15.0) / 1e3,
                       "Ft30_uniform_kW": F_of(p, td, uni, K, 30.0) / 1e3})
    dfb = pd.DataFrame(rows_b)
    dfb.to_csv(OUT / "F1_dew.csv", index=False)
    for col in dfb.columns[1:]:
        assert (np.diff(dfb[col]) <= 1e-6).all(), f"{col} not monotone in T_dew"
    assert (dfb["F_kW"] >= dfb["Ft30_kW"] - 1e-9).all()
    assert (dfb["Ft30_kW"] >= dfb["Ft30_uniform_kW"] - 1e-9).all()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 4.1))
    ax1.plot(dfa.kappa, dfa.F_kW, color="0.55", lw=2.0, label="F — no uncertainty")
    ax1.plot(dfa.kappa, dfa.Ft15_kW, color="C2", lw=2.0, marker="v", ms=4,
             label="F̃ certified, d = 15 min")
    ax1.plot(dfa.kappa, dfa.Ft30_kW, color="C0", lw=2.2, marker="o", ms=4,
             label="F̃ certified, d = 30 min")
    ax1.plot([kp_ali], [F30_ali], marker="*", ms=14, color="C1", ls="none",
             label=f"Alibaba PAI hall (κ ≈ {kp_ali:.2f}), d = 30")
    ax1.axvline(1.0, color="C3", lw=1, ls=":")
    ax1.annotate("Borg-2019 cell-a\n(mixed batch)", xy=(0.97, 0.65), fontsize=7.5,
                 ha="right", color="C3", xycoords=("data", "axes fraction"))
    ax1.set_xlabel("workload volatility (× Borg-2019 cell-a)")
    ax1.set_ylabel("max certifiable S2 offer [kW per MW IT]")
    ax1.set_title(f"(a) the certification wall (dry day, T_dew = {T_DEW_A:.0f} °C)")
    ax1.legend(fontsize=7.5)

    ax2.plot(dfb.T_dew, dfb.F_kW, color="0.55", lw=2.0, label="F — no uncertainty")
    ax2.plot(dfb.T_dew, dfb.Ft15_kW, color="C2", lw=2.0, marker="v", ms=4,
             label="F̃ conditional, d = 15")
    ax2.plot(dfb.T_dew, dfb.Ft30_kW, color="C0", lw=2.2, marker="o", ms=4,
             label="F̃ conditional, d = 30")
    ax2.plot(dfb.T_dew, dfb.Ft30_uniform_kW, color="C3", lw=2.0,
             label="F̃ context-free, d = 30")
    ax2.set_xlabel("day-ahead NWP dew-point forecast $T_{dew}$ [°C]")
    ax2.set_title("(b) weather coupling (Alibaba PAI hall)")
    ax2.legend(fontsize=7.5)
    fig.suptitle("F1 — certified S2 envelope vs workload volatility, duration, weather "
                 "and information (held-out fit, causal forecast, real NWP dew, "
                 "e₀-covered tube)", y=1.02)
    fig.tight_layout()
    savefig(fig, OUT / "F1_context")
    plt.close(fig)

    write_manifest(OUT / "provenance_F1.json", seed=SEED,
                   extra={"experiment": "phase6_F1_context", "hod": HOD,
                          "n_states": N_STATES, "alibaba_kappa": kp_ali,
                          "alibaba_Ft30_kW": F30_ali})
    print("\nF1 complete; monotonicity + ordering assertions passed.")


if __name__ == "__main__":
    main()
