"""Tube margins with a fixed feedback gain (guide 6.3/6.5, D-027).

Error dynamics under the fallback policy u = u_nom + K (x - x_nom):

    e_{t+1} = (A_d + B_d K) e_t + E_d w_t,   |w_t| <= w_Q  (heat-load deviation, W)

With e_0 = 0 (the hour starts from a measured state), the reachable error set under the
polytopic disturbance set W = {0 <= w_t <= w_Q, sum_t w_t dt <= E_budget} (D-031) is
bounded componentwise by the support function

    M_t[j] = max_w sum_{i<t} |A_K^i E_d|_j w_i   over W
           = greedy fill of the largest coefficients at w_Q until the budget runs out
    mu_t = |K| M_t                               (input margin, W)

(E_budget = None recovers the persistent-box margins sum |A_K^i E_d| w_Q — which are so
conservative they empty the envelope; kept for the documentation experiment.)

Every constraint row of the lifted deliverability polyhedron is tightened by the
worst-case contribution of (e_t, K e_t); the condensation floor is robustified by the
dew-point residual bound (T_dew -> T_dew + w_D). Feasibility of the *tightened* LP is
therefore exactly the certificate that the fallback policy satisfies safety and
delivery for ALL disturbances in W(c) — the Thm-2 mechanism.

Scope: certification on the 2-state envelope (the guide's default geometry, D-013);
margins are computed generically but n=3 certification is deferred (D-027).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import solve_discrete_are

from ..plant.dynamics import discrete_matrices
from ..plant.params import PlantParams


@dataclass
class TubeMargins:
    """Worst-case error margins consumed by reachability.build_lifted."""

    K: np.ndarray            # (m, n): u = u_nom + K e
    A_K: np.ndarray
    M: np.ndarray            # (N+1, n) state margins [K]
    mu: np.ndarray           # (N+1,) input margin [W] (first input channel)
    w_Q: float               # heat-deviation bound [W]
    w_D: float               # dew-point residual bound [K]

    @property
    def dew_shift(self) -> float:
        return self.w_D

    def x_margin(self, t: int, j: int) -> float:
        return float(self.M[t, j])

    def u_margin(self, t: int) -> float:
        return float(self.mu[t])

    def ramp_margin(self, t: int) -> float:
        return float(self.mu[t] + self.mu[t - 1]) if t >= 1 else float(self.mu[t])

    def terminal_margin(self, H_row: np.ndarray, N: int) -> float:
        return float(np.abs(np.asarray(H_row)) @ self.M[N])


def lqr_gain(p: PlantParams, n_states: int = 2, q_T: float = 1.0,
             r_u: float = 1.0 / (5e4) ** 2) -> np.ndarray:
    """Fixed fallback gain via discrete LQR on the virtual-input model.

    r_u penalizes input use (per W^2); the default corresponds to ~50 kW of feedback
    authority per K of error — chosen offline once (sweepable, logged in experiment).
    Returns K with the convention u = u_nom + K e (stabilizing: A + B K Hurwitz-d).
    """
    Ad, Bud, _ = discrete_matrices(p, n_states, p.dt_ctrl)
    Q = q_T * np.eye(n_states)
    R = r_u * np.eye(Bud.shape[1])
    P = solve_discrete_are(Ad, Bud, Q, R)
    K_lqr = np.linalg.solve(R + Bud.T @ P @ Bud, Bud.T @ P @ Ad)
    return -K_lqr


def build_tube(p: PlantParams, n_states: int, N: int, w_Q: float, w_D: float,
               K: np.ndarray | None = None, E_budget: float | None = None) -> TubeMargins:
    if n_states != 2:
        raise NotImplementedError("tube certification scoped to the 2-state model (D-027)")
    Ad, Bud, Ed = discrete_matrices(p, n_states, p.dt_ctrl)
    K = lqr_gain(p, n_states) if K is None else np.asarray(K, dtype=float)
    A_K = Ad + Bud @ K

    # coefficient sequence |A_K^i E_d| for i = 0..N-1
    coefs = np.zeros((N, n_states))
    Ai_Ed = Ed[:, 0].copy()
    for i in range(N):
        coefs[i] = np.abs(Ai_Ed)
        Ai_Ed = A_K @ Ai_Ed

    n_budget = np.inf if E_budget is None else E_budget / (w_Q * p.dt_ctrl) if w_Q > 0 else 0.0

    M = np.zeros((N + 1, n_states))
    mu = np.zeros(N + 1)
    for t in range(1, N + 1):
        for j in range(n_states):
            c = np.sort(coefs[:t, j])[::-1]
            if n_budget >= t:
                M[t, j] = w_Q * c.sum()
            else:
                full = int(n_budget)
                M[t, j] = w_Q * (c[:full].sum()
                                 + (n_budget - full) * (c[full] if full < t else 0.0))
        mu[t] = float((np.abs(K) @ M[t])[0])
    return TubeMargins(K=K, A_K=A_K, M=M, mu=mu, w_Q=w_Q, w_D=w_D)


def corner_disturbance(box, N: int, dt_s: float) -> np.ndarray:
    """A harsh in-W trajectory: the per-step bound applied from t=0 until the energy
    budget is exhausted (the front-loaded extreme point of the polytope)."""
    w = np.zeros(N)
    if box.w_Q_sym <= 0:
        return w
    n_budget = box.E_hi / (box.w_Q_sym * dt_s)
    for t in range(N):
        if t + 1 <= n_budget:
            w[t] = box.w_Q_sym
        elif t < n_budget:
            w[t] = (n_budget - t) * box.w_Q_sym
    return w
