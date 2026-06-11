"""Cheap deterministic online MPC with certified fallback switch (guide 6.5, D-029).

Every 5 minutes: solve a small LP from the measured state over the remaining horizon,
tracking the certified fallback plan with an L1 objective. Constraints carry the SAME
tube margins as the certificate, indexed by prediction depth k (the error tube restarts
from the measured state at every re-solve, and M_k is nondecreasing, so the suffix
margins are no tighter than the certificate's at the same absolute time — the certified
fallback plan therefore remains suffix-feasible: recursive feasibility, Thm-3). There
is still no online min-sup (guide 6.4); margins are fixed offline numbers. If the LP is
infeasible at any step, switch permanently to the certified fallback policy.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

from ..envelope.reachability import EnvelopeSpec, activation_steps
from ..plant.dynamics import discrete_matrices
from ..plant.params import PlantParams
from ..plant.virtual_input import T_in_floor
from .fallback import fallback_controller


def _suffix_lp(p: PlantParams, spec: EnvelopeSpec, base: dict, x_t: np.ndarray, t0: int,
               remaining_J: float, u_ref: np.ndarray, terminal_hs,
               tube=None) -> np.ndarray | None:
    """Solve the remaining-horizon LP; return planned inputs u_{t0..N-1} or None."""
    N = spec.horizon_steps
    H = N - t0
    m_act = activation_steps(spec)
    dt = p.dt_ctrl

    class _Zero:
        w_D = 0.0
        M = np.zeros((N + 1, 2))
        mu = np.zeros(N + 1)

    tb = tube or _Zero()
    Ad, Bud, Bwd = discrete_matrices(p, 2, dt)
    floor = T_in_floor(p, spec.T_dew + tb.w_D)
    mc_max, mc_min = p.m_dot_max * p.cp, p.m_dot_min * p.cp
    cop = base["cop_ref"]
    cap = cop * (base["chiller_share_W"])

    # z = (u_0..u_{H-1}, s_0..s_{H-1}) with s = |u - u_ref| slack
    nz = 2 * H
    # state maps over the suffix
    Phi = [np.eye(2)]
    for _ in range(H):
        Phi.append(Ad @ Phi[-1])
    w_term = (Bwd @ [p.Q_IT_nom]).ravel()

    def x_maps(k):       # x_{t0+k} as (coef over u-block, const)
        coef = np.zeros((2, nz))
        for i in range(k):
            coef[:, i: i + 1] = Phi[k - 1 - i] @ Bud
        const = Phi[k] @ x_t + sum((Phi[k - 1 - i] @ w_term for i in range(k)),
                                   np.zeros(2))
        return coef, const

    rows, rhs = [], []

    def add(r, b):
        rows.append(r); rhs.append(b)

    for k in range(1, H + 1):
        coef, const = x_maps(k)
        # T_j <= T_max, tightened by the depth-k tube margin
        add(coef[0], p.T_max - const[0] - tb.M[k, 0])
    for k in range(H):
        # input bounds vs both endpoints
        for s in (k, k + 1):
            coef, const = x_maps(s)
            r = np.zeros(nz); r[k] = 1.0
            add(r - mc_max * coef[1],
                mc_max * (const[1] - floor) - (tb.mu[k] + mc_max * tb.M[s, 1]))
            r = np.zeros(nz); r[k] = -1.0
            add(r + mc_min * coef[1],
                mc_min * (p.T_in_max - const[1]) - (tb.mu[k] + mc_min * tb.M[s, 1]))
        # power cap during remaining activated steps
        if t0 + k < m_act:
            r = np.zeros(nz); r[k] = 1.0
            add(r, cap - tb.mu[k])
    # remaining delivery: settlement sums the WHOLE hour (D-048), so every remaining
    # step contributes (share - u/cop) dt toward the obligation
    if H > 0:
        r = np.zeros(nz)
        dmargin = 0.0
        for k in range(H):
            r[k] = dt / cop
            dmargin += (dt / cop) * tb.mu[k]
        add(r, H * dt * base["chiller_share_W"] - remaining_J - dmargin)
    elif remaining_J > 1e-6:
        return None                      # obligation unmet and hour closed
    # terminal readiness
    if terminal_hs is not None:
        A_T, b_T = terminal_hs
        coef, const = x_maps(H)
        for a_row, b in zip(A_T, b_T):
            add(a_row @ coef, b - a_row @ const - float(np.abs(a_row) @ tb.M[H]))
    # L1 tracking slacks: |u_k - u_ref_k| <= s_k
    for k in range(H):
        r = np.zeros(nz); r[k] = 1.0; r[H + k] = -1.0
        add(r, u_ref[k])
        r = np.zeros(nz); r[k] = -1.0; r[H + k] = -1.0
        add(r, -u_ref[k])

    c = np.zeros(nz)
    c[H:] = 1.0
    res = linprog(c, A_ub=np.array(rows), b_ub=np.array(rhs),
                  bounds=[(None, None)] * H + [(0, None)] * H, method="highs")
    return res.x[:H] if res.status == 0 else None


def mpc_controller(p: PlantParams, cert: dict, terminal_hs=None, tube=None):
    """Returns (controller(t, x), state dict). Tracks delivery internally; switches to
    the certified fallback on infeasibility and stays there."""
    spec: EnvelopeSpec = cert["spec"]
    base = cert["base"]
    m_act = activation_steps(spec)
    dt = p.dt_ctrl
    fb = fallback_controller(cert)
    state = {"switched": False, "switch_step": None, "delivered_J": 0.0}
    required = cert["q"] * m_act * dt

    def ctl(t, x):
        # NOTE (audit A5, accepted approximation): delivered_J accumulates the PLANNED
        # input; the simulator may clip u into the realized U(x) afterwards, so the
        # internal delivery ledger can drift from the physical one when clipping binds.
        # Settlement always uses the realized power series, so reported metrics are
        # unaffected; only the MPC's remaining-obligation steering is approximate.
        if state["switched"]:
            return fb(t, x)
        remaining = max(0.0, required - state["delivered_J"])
        u_ref = cert["u_nom"][t:, 0]
        plan = _suffix_lp(p, spec, base, np.asarray(x), t, remaining, u_ref, terminal_hs,
                          tube=tube)
        if plan is None:
            state["switched"] = True
            state["switch_step"] = t
            u = fb(t, x)
        else:
            u = float(plan[0])
        # delivery accrues over the whole hour (D-048), planned-u approximation (A5)
        P = base["P_pump_W"] + u / base["cop_ref"]
        state["delivered_J"] += (base["P_base_W"] - P) * dt
        return u

    return ctl, state
