"""Phase 6 — F1, the headline figure: value of context (guide 6.4, §8).

Max certifiable offer at d = 30 min across the dew-point range, from each
certification level's own ready state (pre-cooled to its ROBUST condensation floor,
D-044), under increasingly informed certification:

  F      deterministic envelope (no uncertainty — the physical ceiling)
  F̃_hod  conditional on hour-of-day (ε = 0.1 and 0.05)
  F̃_u    context-free certificate (uniform box over all contexts — the only VALID
         certificate without context; the pooled box under-covers, D-030)

Context note (D-043): a recent-residual volatility-regime feature was tested and found
non-informative on the Borg-2019 trace (corr with next-hour records ≈ 0.0–0.08) — on
this workload, context value comes from hour-of-day and dominantly from the dew-point
forecast itself. Logged as a finding, not plotted.

Outputs: F1_context.{pdf,png}, F1_context.csv, provenance. Asserts monotonicity in
T_dew and the certification ordering F >= F̃_hod >= F̃_uniform.
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
D_MIN = 30.0
HOD = 14
T_DEW_GRID = np.arange(8.0, 27.0, 2.0)


def F_of(p, T_dew, box: Box | None, K, d_min: float = D_MIN) -> float:
    """Envelope value from the certification level's own robust-floor ready state."""
    spec = EnvelopeSpec(n_states=2, T_dew=float(T_dew), d_min=d_min)
    if box is None:
        return max(max_q(build_lifted(p, spec), ready_state_for(p, float(T_dew))), 0.0)
    x = ready_state_for(p, float(T_dew) + box.w_D)        # robust floor (D-044)
    tube = build_tube(p, 2, 12, box.w_Q_sym, box.w_D, K=K, E_budget=box.E_hi)
    return max(certified_max_q(p, spec, tube, x), 0.0)


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    K = lqr_gain(p, r_u=1.0 / (10e3) ** 2)
    pool = RealRecordPool(p.Q_IT_nom, seed=SEED)

    feats, recs = pool.features_records()
    cb10 = ConditionalBoxes(feats, recs, eps=0.1, k=80, k_cal=150)
    cb05 = ConditionalBoxes(feats, recs, eps=0.05, k=80, k_cal=150)

    sample = [cb10.box(RealRecordPool.hour_features(h)) for h in range(24)]
    uni = Box(w_Q_hi=max(b.w_Q_hi for b in sample), E_hi=max(b.E_hi for b in sample),
              w_D_hi=max(b.w_D_hi for b in sample))
    box10 = cb10.box(RealRecordPool.hour_features(HOD))
    box05 = cb05.box(RealRecordPool.hour_features(HOD))

    rows = []
    for td in T_DEW_GRID:
        rows.append({
            "T_dew": td,
            "F_kW": F_of(p, td, None, K) / 1e3,
            "Ft_hod10_kW": F_of(p, td, box10, K) / 1e3,
            "Ft_hod05_kW": F_of(p, td, box05, K) / 1e3,
            "Ft_hod10_d15_kW": F_of(p, td, box10, K, d_min=15.0) / 1e3,
            "Ft_uniform_kW": F_of(p, td, uni, K) / 1e3,
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "F1_context.csv", index=False)
    print(df.round(1).to_string(index=False))

    for col in df.columns[1:]:
        assert (np.diff(df[col]) <= 1e-6).all(), f"{col} not monotone in T_dew"
    assert (df["Ft_hod10_kW"] >= df["Ft_uniform_kW"] - 1e-9).all()
    assert (df["F_kW"] >= df["Ft_hod10_kW"] - 1e-9).all()

    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    ax.plot(df.T_dew, df.F_kW, color="0.55", lw=2.2, label="F — no uncertainty (ceiling)")
    ax.plot(df.T_dew, df.Ft_hod10_kW, color="C0", lw=2.2, marker="o", ms=4,
            label="F̃ conditional, hour-of-day (ε = 0.1)")
    ax.plot(df.T_dew, df.Ft_hod05_kW, color="C0", lw=1.4, ls="--", marker="o", ms=3,
            label="F̃ conditional, hour-of-day (ε = 0.05)")
    ax.plot(df.T_dew, df.Ft_hod10_d15_kW, color="C2", lw=1.6, marker="v", ms=4,
            label="F̃ conditional, shorter product d = 15 min (ε = 0.1)")
    ax.plot(df.T_dew, df.Ft_uniform_kW, color="C3", lw=2.0,
            label="F̃ context-free (uniform box)")
    ax.fill_between(df.T_dew, 0, df.F_kW,
                    where=(df.Ft_uniform_kW <= 0) & (df.Ft_hod10_kW > 0),
                    color="C0", alpha=0.06)
    ax.annotate("certifiable only WITH context", xy=(11, 8), fontsize=8, color="C0")
    ax.set_xlabel("day-ahead dew-point forecast $T_{dew}$ [°C]")
    ax.set_ylabel("max certifiable offer [kW per MW IT]")
    ax.set_title("F1 — value of context: certified envelope vs information level\n"
                 f"(d = 30 min, hour {HOD}:00, ready state at the robust floor; "
                 "real Borg-2019 heat residuals + NWP-skill dew model)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    savefig(fig, OUT / "F1_context")
    plt.close(fig)

    write_manifest(OUT / "provenance_F1.json", seed=SEED,
                   extra={"experiment": "phase6_F1_context", "hod": HOD,
                          "uniform_box": [uni.w_Q_sym / 1e3, uni.E_hi / 1e6, uni.w_D],
                          "hod_box_eps10": [box10.w_Q_sym / 1e3, box10.E_hi / 1e6,
                                            box10.w_D],
                          "regime_feature_finding":
                              "non-informative on Borg-2019 (corr ~0.0-0.08), D-043"})
    print("\nF1 complete; monotonicity + ordering assertions passed.")


if __name__ == "__main__":
    main()
