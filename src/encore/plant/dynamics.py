"""LTI thermal dynamics (guide 6.1), virtual-input form and closed-loop physical form.

Virtual-input (optimization-facing) form — all SI:

2-state, x = (T_j, T_w), u = (q_ext,), w = (Q_IT,):
    C_j dT_j/dt = Q_IT - h_jw (T_j - T_w)
    C_w dT_w/dt = h_jw (T_j - T_w) - q_ext            [q_rej == q_ext, no buffering]

3-state, x = (T_j, T_w, T_f), u = (q_ext, q_rej), w = (Q_IT,):
    C_j dT_j/dt = Q_IT - h_jw (T_j - T_w)
    C_w dT_w/dt = h_jw (T_j - T_w) - q_ext            [q_ext: coolant loop -> facility loop]
    C_f dT_f/dt = q_ext - q_rej                       [q_rej: facility loop -> ambient]

Energy-consistent series topology per DESIGN_DECISIONS D-004. No bilinear terms anywhere:
the (m_dot, T_in) physics lives in the state-dependent input set U(x) (virtual_input.py).

The closed-loop *physical* form (fixed m_dot/T_in plus a proportional chiller rejection
law) is used only for step-response characterization; substituting
q_ext = m_dot cp (T_w - T_f - delta_hx) recovers the guide's h_wf (T_w - T_f) coupling
with h_wf = m_dot cp.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm

from .params import PlantParams


# ---------------------------------------------------------------- CT matrices

def ct_matrices(p: PlantParams, n_states: int):
    """Continuous-time (A, Bu, Bw) of the virtual-input form."""
    if n_states == 2:
        A = np.array([
            [-p.h_jw / p.C_j, p.h_jw / p.C_j],
            [p.h_jw / p.C_w, -p.h_jw / p.C_w],
        ])
        Bu = np.array([[0.0], [-1.0 / p.C_w]])
        Bw = np.array([[1.0 / p.C_j], [0.0]])
    elif n_states == 3:
        A = np.array([
            [-p.h_jw / p.C_j, p.h_jw / p.C_j, 0.0],
            [p.h_jw / p.C_w, -p.h_jw / p.C_w, 0.0],
            [0.0, 0.0, 0.0],
        ])
        Bu = np.array([
            [0.0, 0.0],
            [-1.0 / p.C_w, 0.0],
            [1.0 / p.C_f, -1.0 / p.C_f],
        ])
        Bw = np.array([[1.0 / p.C_j], [0.0], [0.0]])
    else:
        raise ValueError(f"n_states must be 2 or 3, got {n_states}")
    return A, Bu, Bw


def capacitances(p: PlantParams, n_states: int) -> np.ndarray:
    """Heat capacities aligned with the state vector [J/K]."""
    if n_states == 2:
        return np.array([p.C_j, p.C_w])
    return np.array([p.C_j, p.C_w, p.C_f])


# ------------------------------------------------------------- discretization

def discretize(A: np.ndarray, B: np.ndarray, dt: float):
    """Exact zero-order-hold discretization via block matrix exponential."""
    n, m = A.shape[0], B.shape[1]
    M = np.zeros((n + m, n + m))
    M[:n, :n] = A
    M[:n, n:] = B
    Md = expm(M * dt)
    return Md[:n, :n], Md[:n, n:]


def discrete_matrices(p: PlantParams, n_states: int, dt: float):
    """Exact ZOH (Ad, Bud, Bwd) of the virtual-input form at step dt [s]."""
    A, Bu, Bw = ct_matrices(p, n_states)
    B = np.hstack([Bu, Bw])
    Ad, Bd = discretize(A, B, dt)
    return Ad, Bd[:, : Bu.shape[1]], Bd[:, Bu.shape[1]:]


# ---------------------------------------------------------------- steady state

def steady_state(p: PlantParams, n_states: int, Q_IT: float, T_in: float):
    """Steady state for heat load Q_IT [W] at supply temperature T_in [degC],
    pump at nominal flow. Returns (x_ss, u_ss).

    At steady state the full load passes through every interface:
    q_ext = q_rej = Q_IT;  T_w = T_in + Q/(m cp);  T_j = T_w + Q/h_jw;
    (3-state) T_f = T_in - delta_hx (passive CDU approach).
    """
    T_w = T_in + Q_IT / (p.m_dot_nom * p.cp)
    T_j = T_w + Q_IT / p.h_jw
    if n_states == 2:
        return np.array([T_j, T_w]), np.array([Q_IT])
    T_f = T_in - p.delta_hx
    return np.array([T_j, T_w, T_f]), np.array([Q_IT, Q_IT])


# ------------------------------------------- closed-loop physical (step tests)

def closed_loop_affine(
    p: PlantParams,
    n_states: int,
    Q_IT: float,
    m_dot: float,
    T_in: float | None = None,
    q_rej0: float = 0.0,
    T_f_ref: float = 0.0,
):
    """Closed-loop affine system dx/dt = A_cl x + b for fixed *physical* laws.

    2-state: q_ext = m_dot cp (T_w - T_in)              (T_in required)
    3-state: q_ext = m_dot cp (T_w - T_f - delta_hx)    (passive CDU)
             q_rej = q_rej0 + k_rej (T_f - T_f_ref)     (proportional chiller law)
    """
    A, Bu, Bw = ct_matrices(p, n_states)
    mc = m_dot * p.cp
    if n_states == 2:
        if T_in is None:
            raise ValueError("2-state closed loop needs T_in")
        K = np.array([[0.0, mc]])
        k0 = np.array([-mc * T_in])
    else:
        K = np.array([
            [0.0, mc, -mc],
            [0.0, 0.0, p.k_rej],
        ])
        k0 = np.array([-mc * p.delta_hx, q_rej0 - p.k_rej * T_f_ref])
    A_cl = A + Bu @ K
    b = Bu @ k0 + (Bw @ np.array([Q_IT])).ravel()
    return A_cl, b


def time_constants(A_cl: np.ndarray) -> np.ndarray:
    """Sorted time constants -1/Re(lambda) [s] of a Hurwitz matrix (fast to slow)."""
    eig = np.linalg.eigvals(A_cl)
    if np.any(eig.real >= 0):
        raise ValueError(f"closed-loop matrix not Hurwitz: eigenvalues {eig}")
    return np.sort(-1.0 / eig.real)


def simulate_affine(A: np.ndarray, b: np.ndarray, x0: np.ndarray, dt: float, n_steps: int):
    """Exact integration of dx/dt = A x + b on a fixed grid.

    Returns (X, IX): X[k] = x(k dt), shape (n_steps+1, n); IX[k] = integral of x(t) dt
    over step k, shape (n_steps, n) — exact via augmented matrix exponential, so energy
    bookkeeping of affine output laws closes to machine precision.
    """
    n = A.shape[0]
    # augmented state z = (x, 1, ix); d/dt: x' = A x + b*1 ; 1' = 0 ; ix' = x
    M = np.zeros((2 * n + 1, 2 * n + 1))
    M[:n, :n] = A
    M[:n, n] = b
    M[n + 1:, :n] = np.eye(n)
    Md = expm(M * dt)
    X = np.empty((n_steps + 1, n))
    IX = np.empty((n_steps, n))
    X[0] = x0
    for k in range(n_steps):
        z = np.concatenate([X[k], [1.0], np.zeros(n)])
        z = Md @ z
        X[k + 1] = z[:n]
        IX[k] = z[n + 1:]
    return X, IX
