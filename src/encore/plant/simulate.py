"""Simulation harness with energy-balance bookkeeping (guide 6.1, Phase 0).

simulate() integrates the virtual-input LTI form exactly (ZOH) for piecewise-constant
input/disturbance trajectories and reports an energy balance:

    E_in (IT heat)  -  E_export (q_ext for 2-state / q_rej for 3-state)  =  dE_stored

Closure is exact up to floating point for the LTI model; the <1% Phase-0 acceptance
threshold guards against discretization or unit bugs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dynamics import capacitances, discrete_matrices
from .params import PlantParams


@dataclass
class SimResult:
    t: np.ndarray        # (N+1,) s
    X: np.ndarray        # (N+1, n) degC
    U: np.ndarray        # (N, m) W
    W: np.ndarray        # (N,) W
    energy: dict         # bookkeeping summary


def simulate(p: PlantParams, n_states: int, x0: np.ndarray, u_traj: np.ndarray,
             dist_traj: np.ndarray, dt: float | None = None) -> SimResult:
    """Simulate the virtual-input form under piecewise-constant (u, w).

    u_traj: (N, m) [W] with m=1 (2-state: q_ext) or m=2 (3-state: q_ext, q_rej).
    dist_traj: (N,) IT heat [W]. dt defaults to the configured simulation step.
    """
    dt = p.dt_sim if dt is None else dt
    u_traj = np.asarray(u_traj, dtype=float)
    if u_traj.ndim == 1:
        u_traj = u_traj.reshape(-1, 1)
    dist_traj = np.asarray(dist_traj, dtype=float)
    N = u_traj.shape[0]
    if dist_traj.shape != (N,):
        raise ValueError("dist_traj length must match u_traj")

    Ad, Bud, Bwd = discrete_matrices(p, n_states, dt)
    X = np.empty((N + 1, n_states))
    X[0] = x0
    for k in range(N):
        X[k + 1] = Ad @ X[k] + Bud @ u_traj[k] + Bwd @ np.array([dist_traj[k]])

    C = capacitances(p, n_states)
    E_in = float(np.sum(dist_traj) * dt)
    # exports leave the modeled system: 2-state rejects q_ext directly, 3-state rejects q_rej
    exports = u_traj[:, 0] if n_states == 2 else u_traj[:, 1]
    E_out = float(np.sum(exports) * dt)
    dE = float(C @ (X[-1] - X[0]))
    residual = E_in - E_out - dE
    scale = max(abs(E_in), abs(E_out), abs(dE), 1.0)
    energy = {
        "E_in_J": E_in,
        "E_export_J": E_out,
        "dE_stored_J": dE,
        "residual_J": residual,
        "closure_frac": abs(residual) / scale,
    }
    t = np.arange(N + 1) * dt
    return SimResult(t=t, X=X, U=u_traj, W=dist_traj, energy=energy)
