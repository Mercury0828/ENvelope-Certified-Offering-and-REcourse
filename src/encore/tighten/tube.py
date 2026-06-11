"""Tube margins with a fixed feedback gain (guide 6.3/6.5, D-027/D-046/D-047/D-049).

Error dynamics under the fallback policy u = u_nom + K (x - x_nom):

    e_{t+1} = (A_d + B_d K) e_t + E_d w_t,   0 <= w_t <= w_Q,  sum_t w_t dt <= E_budget

with e_0 in the +-e0_K componentwise ball (the pre-positioning accuracy, D-047).
Margins are the exact support function of this disturbance polytope (greedy
largest-coefficients-first fill, D-031) plus the decaying initial-error term:

    M_t[j]  = max_w sum_{i<t} |A_K^i E_d|_j w_i  +  (|A_K^t| e0)_j      [K]
    mu_t[c] = |K_c| M_t                                                  [W], per channel

Feasibility of the margin-tightened lifted LP is the fallback certificate (D-028).

Supports BOTH plant models (D-049 extends D-027's 2-state scoping):
  n=2: u = (q_ext,), K is 1x2
  n=3: u = (q_ext, q_rej), K is 2x3 — certifies the S2 facility-loop product
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
    mu: np.ndarray           # (N+1, m) input margins [W] per channel
    w_Q: float               # heat-deviation bound [W]
    w_D: float               # dew-point residual bound [K]

    @property
    def dew_shift(self) -> float:
        return self.w_D

    def x_margin(self, t: int, j: int) -> float:
        return float(self.M[t, j])

    def u_margin(self, t: int, ch: int = 0) -> float:
        return float(self.mu[t, ch])

    def ramp_margin(self, t: int) -> float:
        return float(self.mu[t, 0] + self.mu[t - 1, 0]) if t >= 1 else float(self.mu[t, 0])

    def terminal_margin(self, H_row: np.ndarray, N: int) -> float:
        return float(np.abs(np.asarray(H_row)) @ self.M[N])


def lqr_gain(p: PlantParams, n_states: int = 2, q_T: float = 1.0,
             r_u: float = 1.0 / (5e4) ** 2) -> np.ndarray:
    """Fixed fallback gain via discrete LQR on the virtual-input model.

    r_u penalizes input use (per W^2) on every channel; chosen offline once.
    Returns K with the convention u = u_nom + K e (stabilizing).
    """
    Ad, Bud, _ = discrete_matrices(p, n_states, p.dt_ctrl)
    Q = q_T * np.eye(n_states)
    R = r_u * np.eye(Bud.shape[1])
    P = solve_discrete_are(Ad, Bud, Q, R)
    K_lqr = np.linalg.solve(R + Bud.T @ P @ Bud, Bud.T @ P @ Ad)
    return -K_lqr


def build_tube(p: PlantParams, n_states: int, N: int, w_Q: float, w_D: float,
               K: np.ndarray | None = None, E_budget: float | None = None,
               e0_K: float = 1.5) -> TubeMargins:
    """e0_K: componentwise bound [K] on the INITIAL state error e_0 — covers any event
    start within e0_K of the committed ready state (D-047). Default derived from the
    sprint idle law's one-hour convergence (D-048)."""
    Ad, Bud, Ed = discrete_matrices(p, n_states, p.dt_ctrl)
    K = lqr_gain(p, n_states) if K is None else np.asarray(K, dtype=float)
    A_K = Ad + Bud @ K
    m = Bud.shape[1]

    coefs = np.zeros((N, n_states))
    Ai_Ed = Ed[:, 0].copy()
    A_pow = np.eye(n_states)
    e0_vec = np.full(n_states, float(e0_K))
    e0_term = np.zeros((N + 1, n_states))
    e0_term[0] = np.abs(A_pow) @ e0_vec
    for i in range(N):
        coefs[i] = np.abs(Ai_Ed)
        Ai_Ed = A_K @ Ai_Ed
        A_pow = A_K @ A_pow
        e0_term[i + 1] = np.abs(A_pow) @ e0_vec

    n_budget = np.inf if E_budget is None else E_budget / (w_Q * p.dt_ctrl) if w_Q > 0 else 0.0

    M = np.zeros((N + 1, n_states))
    mu = np.zeros((N + 1, m))
    M[0] = e0_term[0]
    mu[0] = np.abs(K) @ M[0]
    for t in range(1, N + 1):
        for j in range(n_states):
            c = np.sort(coefs[:t, j])[::-1]
            if n_budget >= t:
                M[t, j] = w_Q * c.sum()
            else:
                full = int(n_budget)
                M[t, j] = w_Q * (c[:full].sum()
                                 + (n_budget - full) * (c[full] if full < t else 0.0))
            M[t, j] += e0_term[t, j]
        mu[t] = np.abs(K) @ M[t]
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
