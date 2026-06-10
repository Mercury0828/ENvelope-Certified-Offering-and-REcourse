"""Phase 2 — envelope cross-validation (the R1 evidence, guide Section 11).

Three layers of validation, >=2,000 points total (acceptance: agreement >= 98%):

A. Projection exactness (the R1 question): membership via exactly-projected fixed-q
   polygons vs the direct open-loop feasibility LP, sampled at on-grid (q, T_dew).
   Mismatches here would mean the geometric route itself is lossy.
B. Tabulated runtime object: continuum samples (x, q, T_dew) against the LP, with the
   guide-6.3 conservative nearest-neighbor snapping. Mismatches are *designed*
   conservatism (snap-up of q and T_dew); must be one-sided (never anti-conservative).
C. Physical (non-circular) check: optimal trajectories extracted at q = F(x) - eps are
   re-simulated at 30 s; constraint violations beyond intra-step tolerance would indicate
   dynamics/discretization inconsistency. Run for both 2- and 3-state models.

Outputs: xval_summary.json, xval_mismatches.csv, provenance, console report.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json
import time

import numpy as np
import pandas as pd

from encore.envelope.geometry import (
    TabulatedEnvelope, extract_trajectory, is_member, max_q, poly_contains,
    poly_halfspaces, project_slice,
)
from encore.envelope.reachability import EnvelopeSpec, build_lifted
from encore.plant.dynamics import steady_state
from encore.plant.params import load_params
from encore.plant.simulate import simulate
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase2"
SEED = 20260610
D_VALUES = [15.0, 30.0, 60.0]
T_DEW_GRID = [10.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0]
N_Q = 50
INTRA_STEP_TOL_K = 0.5     # allowed intra-step excursion beyond T_max at 30 s resolution


def sample_x(rng, n_states):
    """Half broad-uniform over the operating box, half near the operating manifold."""
    if rng.uniform() < 0.5:
        x = [rng.uniform(30, 92), rng.uniform(15, 56)]
    else:
        T_w = rng.uniform(30, 56)
        x = [T_w + rng.uniform(15, 35), T_w]
    if n_states == 3:
        x.append(rng.uniform(12, 38))
    return np.array(x)


def layer_A(p, tab, rng, n_samples=1200):
    """On-grid polygon membership vs LP membership."""
    mism = []
    n_checked = 0
    lifted_cache = {}
    for _ in range(n_samples):
        d = float(rng.choice(D_VALUES))
        T_dew = float(rng.choice(T_DEW_GRID))
        iq = int(rng.integers(0, N_Q))
        q = float(tab.q_grid[iq])
        x = sample_x(rng, 2)
        key = (d, T_dew)
        if key not in lifted_cache:
            lifted_cache[key] = build_lifted(p, EnvelopeSpec(n_states=2, T_dew=T_dew, d_min=d))
        L = lifted_cache[key]
        hs = tab.cells[(d, T_dew, iq)]
        # skip knife-edge points (within 1e-3 K of a polygon facet): tie-breaking noise
        if hs is not None:
            A, b = hs
            if np.abs(A @ x[:2] - b).min() < 1e-3:
                continue
        n_checked += 1
        geo = poly_contains(hs, x[:2])
        lp = is_member(L, x, q)
        if geo != lp:
            mism.append({"layer": "A", "d": d, "T_dew": T_dew, "q_kW": q / 1e3,
                         "T_j": x[0], "T_w": x[1], "geo": geo, "lp": lp})
    return n_checked, mism


def layer_B(p, tab, rng, n_samples=1200):
    """Continuum (q, T_dew) with conservative snapping vs LP."""
    mism = []
    anti = 0
    for _ in range(n_samples):
        d = float(rng.choice(D_VALUES))
        T_dew = float(rng.uniform(10.0, 24.0))
        q = float(rng.uniform(0.0, tab.q_grid[-1]))
        x = sample_x(rng, 2)
        L = build_lifted(p, EnvelopeSpec(n_states=2, T_dew=T_dew, d_min=d))
        geo = tab.member(x[:2], q, T_dew, d)
        lp = is_member(L, x, q)
        if geo != lp:
            mism.append({"layer": "B", "d": d, "T_dew": T_dew, "q_kW": q / 1e3,
                         "T_j": x[0], "T_w": x[1], "geo": geo, "lp": lp})
            if geo and not lp:
                anti += 1
    return n_samples, mism, anti


def layer_C(p, rng, n_states, n_samples=200):
    """Re-simulate optimal trajectories at 30 s; report worst intra-step excursion."""
    worst = -np.inf
    n_ok = 0
    for _ in range(n_samples):
        d = float(rng.choice(D_VALUES))
        T_dew = float(rng.uniform(10.0, 24.0))
        x0s, _ = steady_state(p, n_states, p.Q_IT_nom, p.T_in_nom)
        x = x0s + rng.uniform([-8, -8, -6][: n_states], [5, 5, 5][: n_states])
        x[0] = min(x[0], p.T_max - 0.1)
        L = build_lifted(p, EnvelopeSpec(n_states=n_states, T_dew=T_dew, d_min=d))
        F = max_q(L, x)
        if not np.isfinite(F) or F < 1.0:
            continue
        traj = extract_trajectory(L, x, F - 1.0)
        if traj is None:
            continue
        X, U = traj
        sub = int(p.dt_ctrl / p.dt_sim)
        U_fine = np.repeat(U, sub, axis=0)
        Q_fine = np.full(U_fine.shape[0], p.Q_IT_nom)
        res = simulate(p, n_states, x, U_fine, Q_fine, dt=p.dt_sim)
        assert np.allclose(res.X[::sub], X, atol=1e-6), "5-min marks disagree with LP states"
        worst = max(worst, float(res.X[:, 0].max() - p.T_max))
        if n_states == 3:
            worst = max(worst, float(res.X[:, 2].max() - p.T_f_max))
        n_ok += 1
    return n_ok, worst


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    rng = np.random.default_rng(SEED)

    print("building tabulated envelope "
          f"({len(D_VALUES)} d x {len(T_DEW_GRID)} T_dew x {N_Q} q slices)...")
    t0 = time.perf_counter()
    q_ub = build_lifted(p, EnvelopeSpec(n_states=2)).q_ub
    tab = TabulatedEnvelope(p, D_VALUES, T_DEW_GRID, np.linspace(0.0, q_ub, N_Q))
    tab.build(log=lambda s: print("  " + s))
    n_empty = sum(1 for v in tab.cells.values() if v is None)
    t_build = time.perf_counter() - t0
    print(f"built {len(tab.cells)} cells ({n_empty} empty/degenerate) in {t_build:.0f}s")

    nA, mismA = layer_A(p, tab, rng)
    agreeA = 1.0 - len(mismA) / nA
    print(f"layer A (projection exactness): {nA} pts, agreement {agreeA:.2%}")

    nB, mismB, antiB = layer_B(p, tab, rng)
    agreeB = 1.0 - len(mismB) / nB
    print(f"layer B (tabulated runtime object): {nB} pts, agreement {agreeB:.2%}, "
          f"anti-conservative {antiB}")

    nC2, worst2 = layer_C(p, rng, 2)
    nC3, worst3 = layer_C(p, rng, 3)
    print(f"layer C (re-simulation): 2-state {nC2} trajs, worst excursion {worst2:+.3f} K; "
          f"3-state {nC3} trajs, worst {worst3:+.3f} K")

    n_total = nA + nB
    agree_total = 1.0 - (len(mismA) + len(mismB)) / n_total
    summary = {
        "n_layer_A": nA, "agreement_A": agreeA,
        "n_layer_B": nB, "agreement_B": agreeB, "anti_conservative_B": antiB,
        "n_total_membership_points": n_total, "agreement_total": agree_total,
        "n_resim_2state": nC2, "worst_excursion_2state_K": worst2,
        "n_resim_3state": nC3, "worst_excursion_3state_K": worst3,
        "tab_cells": len(tab.cells), "tab_empty_cells": n_empty,
        "tab_build_seconds": t_build,
    }
    (OUT / "xval_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame(mismA + mismB).to_csv(OUT / "xval_mismatches.csv", index=False)
    write_manifest(OUT / "provenance_xval.json", seed=SEED,
                   extra={"experiment": "phase2_envelope_xval", **summary})

    # ---- acceptance ----
    assert n_total >= 2000
    assert agreeA >= 0.995, f"projection exactness only {agreeA:.2%} — geometric route suspect"
    assert agree_total >= 0.98, f"total agreement {agree_total:.2%} < 98%"
    assert antiB == 0, "tabulated envelope returned an ANTI-conservative member — bug"
    assert not any(m["geo"] and not m["lp"] for m in mismA), "layer-A anti-conservative — bug"
    assert worst2 <= INTRA_STEP_TOL_K and worst3 <= INTRA_STEP_TOL_K
    print("\nall Phase-2 cross-validation assertions passed.")


if __name__ == "__main__":
    main()
