"""Phase 2 — lifted deliverability system (guide 6.3).

An offer (q, d) is deliverable from state x_0 over one market hour iff there exists an
input sequence in U(x) keeping T_j <= T_max (and T_f <= T_f_max) throughout, delivering
cumulative cooling-power reduction >= r q DH along the activation profile, and steering
the terminal state into a readiness set.

This module assembles that as ONE polyhedron in the lifted variable
    z = (x_0 [n], q [1], u_0..u_{N-1} [N*m])        (states eliminated via dynamics)
so that downstream geometry is exact linear algebra: F(x,c) is an LP, fixed-q slices are
polytope projections, and the whole lifted form can later be embedded directly in the
D-1 offering problem (Phase 4) without any projection at all.

Conventions (logged): activation occupies the first round(r*N) steps of the hour with
r = d/60 by default (D-020); delivery is cumulative over the activation window
(guide 6.3 "along the activation profile" — conservative vs. settlement's whole-hour
sum, D-019); the envelope lives inside an explicit operating box and the first input is
ramp-free since x_0 need not be a steady state (D-021). Power enters through the
conservative affine surrogate of D-006. No bilinear terms.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from ..plant import power
from ..plant.dynamics import discrete_matrices
from ..plant.params import PlantParams
from ..plant.virtual_input import T_in_floor


@dataclass(frozen=True)
class EnvelopeSpec:
    """Context + product parameters defining one deliverability polyhedron."""

    n_states: int = 2
    T_dew: float = 15.0          # degC — the contextual variable of Phase 2
    T_wb: float = 22.0           # degC, fixed across cases (D-007)
    d_min: float = 30.0          # product duration [min]
    horizon_steps: int = 12      # one market hour at 5 min
    r: float | None = None       # activation fraction; None -> d/60 (max allowed)
    delivery: str = "cumulative"  # "cumulative" (guide 6.3) | "sustained" (Phase-1 style)
    Q_IT: float | None = None    # constant heat load [W]; None -> nominal
    terminal: tuple | None = None  # (H, h): require H x_N <= h; None -> safety box only
    # operating box (DOE-style domain of definition, D-021): per-state (lo, hi)
    x_box: tuple = ((25.0, 90.0), (12.0, 58.0), (10.0, 40.0))
    u_ext_abs: tuple = (-2.0e6, 3.0e6)   # absolute guards keeping the polytope bounded


@dataclass
class Lifted:
    """G z <= h with bookkeeping. z = (x_0, q, u_0..u_{N-1})."""

    G: np.ndarray
    h: np.ndarray
    n: int
    m: int
    N: int
    p: PlantParams
    spec: EnvelopeSpec
    q_ub: float                  # chiller share [W]
    base: dict                   # baseline_power dict
    # x_t(z) = X_coef[t] @ z + X_const[t]
    X_coef: np.ndarray = field(repr=False, default=None)
    X_const: np.ndarray = field(repr=False, default=None)

    @property
    def nz(self) -> int:
        return self.n + 1 + self.N * self.m

    @property
    def iq(self) -> int:
        return self.n

    def iu(self, t: int) -> int:
        return self.n + 1 + t * self.m


def activation_steps(spec: EnvelopeSpec) -> int:
    r = spec.r if spec.r is not None else spec.d_min / 60.0
    m_act = int(round(r * spec.horizon_steps))
    if not (1 <= m_act <= spec.horizon_steps):
        raise ValueError(f"activation window {m_act} outside horizon")
    return m_act


class _ZeroTube:
    """Margin-free default; see tighten.tube.TubeMargins for the robust version."""

    dew_shift = 0.0

    @staticmethod
    def x_margin(t, j):
        return 0.0

    @staticmethod
    def u_margin(t):
        return 0.0

    @staticmethod
    def ramp_margin(t):
        return 0.0

    @staticmethod
    def terminal_margin(H_row, N):
        return 0.0


def build_lifted(p: PlantParams, spec: EnvelopeSpec, tube=None) -> Lifted:
    """Assemble Gz <= h; with `tube` (tighten.tube.TubeMargins) every row is tightened
    by the worst-case tube-error contribution and the condensation floor is robustified
    by the dew residual bound — feasibility of the result IS the fallback certificate
    (guide 6.5, D-027/D-028)."""
    n = spec.n_states
    m = 1 if n == 2 else 2
    N = spec.horizon_steps
    dt = p.dt_ctrl
    Q = p.Q_IT_nom if spec.Q_IT is None else spec.Q_IT
    m_act = activation_steps(spec)
    tube = tube or _ZeroTube()
    if not isinstance(tube, _ZeroTube) and n != 2:
        raise NotImplementedError("tube-tightened envelope scoped to 2-state (D-027)")

    Ad, Bud, Bwd = discrete_matrices(p, n, dt)
    nz = n + 1 + N * m
    iq = n

    def iu(t):
        return n + 1 + t * m

    # ---- state maps x_t = X_coef[t] @ z + X_const[t] (t = 0..N)
    X_coef = np.zeros((N + 1, n, nz))
    X_const = np.zeros((N + 1, n))
    X_coef[0, :, :n] = np.eye(n)
    w_term = (Bwd @ [Q]).ravel()
    for t in range(N):
        X_coef[t + 1] = Ad @ X_coef[t]
        X_coef[t + 1, :, iu(t): iu(t) + m] += Bud
        X_const[t + 1] = Ad @ X_const[t] + w_term

    P_pump = float(power.pump_power(p, p.m_dot_nom))
    cop_ref = float(power.cop(p, p.T_in_nom, spec.T_wb))
    P_base = P_pump + Q / cop_ref          # frozen exogenous baseline (guide 5.4)
    chiller_share = P_base - P_pump
    floor = T_in_floor(p, spec.T_dew + tube.dew_shift)   # robustified condensation floor
    mc_max, mc_min = p.m_dot_max * p.cp, p.m_dot_min * p.cp
    ramp = p.q_ext_ramp * dt

    rows, rhs = [], []

    def add(coef_z, const_rhs):
        rows.append(coef_z)
        rhs.append(const_rhs)

    def add_state_ub(t, j, ub):     # (x_t)_j <= ub
        add(X_coef[t, j].copy(), ub - X_const[t, j])

    def add_state_lb(t, j, lb):     # (x_t)_j >= lb
        add(-X_coef[t, j].copy(), X_const[t, j] - lb)

    # ---- operating box on x_0 (and initial safety)
    for j in range(n):
        lo, hi = spec.x_box[j]
        add_state_lb(0, j, lo)
        add_state_ub(0, j, hi)
    add_state_ub(0, 0, p.T_max)
    if n == 3:
        add_state_ub(0, 2, p.T_f_max)

    # ---- safety along the hour (tightened by state tube margins)
    for t in range(1, N + 1):
        add_state_ub(t, 0, p.T_max - tube.x_margin(t, 0))
        if n == 3:
            add_state_ub(t, 2, p.T_f_max - tube.x_margin(t, 2))

    # ---- U(x) bounds at both step endpoints (D-010), affine in x via state maps;
    #      tightened by input margin (K e_t) + state margin at the bound's endpoint
    for t in range(N):
        for s in (t, t + 1):
            mg_ub = tube.u_margin(t) + mc_max * tube.x_margin(s, 1)
            mg_lb = tube.u_margin(t) + mc_min * tube.x_margin(s, 1)
            # u_ext,t <= mc_max (T_w,s - floor)
            r_ = np.zeros(nz); r_[iu(t)] = 1.0
            add(r_ - mc_max * X_coef[s, 1], mc_max * (X_const[s, 1] - floor) - mg_ub)
            # u_ext,t >= mc_min (T_w,s - T_in_max)
            r_ = np.zeros(nz); r_[iu(t)] = -1.0
            add(r_ + mc_min * X_coef[s, 1], mc_min * (p.T_in_max - X_const[s, 1]) - mg_lb)
            if n == 3:
                # passive CDU (D-005): u_ext,t <= mc_max (T_w,s - T_f,s - delta_hx)
                r_ = np.zeros(nz); r_[iu(t)] = 1.0
                add(r_ - mc_max * (X_coef[s, 1] - X_coef[s, 2]),
                    mc_max * (X_const[s, 1] - X_const[s, 2] - p.delta_hx))

    # ---- input channel bounds
    for t in range(N):
        r_ = np.zeros(nz); r_[iu(t)] = 1.0
        add(r_, spec.u_ext_abs[1])
        add(-r_, -spec.u_ext_abs[0])
        if n == 3:
            r_ = np.zeros(nz); r_[iu(t) + 1] = 1.0
            add(r_, p.q_rej_max)
            add(-r_, 0.0)

    # ---- ramp on q_ext between consecutive steps (first step free, D-021)
    for t in range(1, N):
        r_ = np.zeros(nz); r_[iu(t)] = 1.0; r_[iu(t - 1)] = -1.0
        add(r_, ramp - tube.ramp_margin(t))
        add(-r_, ramp - tube.ramp_margin(t))

    # ---- power-cut / delivery on the rejection channel (D-006 surrogate)
    # rejection variable: u_ext for n=2 (q_rej == q_ext), u_rej for n=3
    def rej_col(t):
        return iu(t) if n == 2 else iu(t) + 1

    if spec.delivery == "sustained":
        # q_rej,t + cop_ref * q <= cop_ref * chiller_share for activated steps
        for t in range(m_act):
            r_ = np.zeros(nz); r_[rej_col(t)] = 1.0; r_[iq] = cop_ref
            add(r_, cop_ref * chiller_share - tube.u_margin(t))
    elif spec.delivery == "cumulative":
        # sum_{t<m_act} (P_base - P_t) dt >= r q DH, P_t = P_pump + q_rej,t/cop_ref
        r_ = np.zeros(nz)
        delivery_margin = 0.0
        for t in range(m_act):
            r_[rej_col(t)] = dt / cop_ref
            delivery_margin += (dt / cop_ref) * tube.u_margin(t)
        r_[iq] = m_act * dt          # r*DH = m_act*dt by construction of m_act
        add(r_, m_act * dt * chiller_share - delivery_margin)
    else:
        raise ValueError(spec.delivery)

    # ---- offer bounds
    r_ = np.zeros(nz); r_[iq] = -1.0
    add(r_, 0.0)                                  # q >= 0
    r_ = np.zeros(nz); r_[iq] = 1.0
    add(r_, chiller_share)                        # q <= chiller share

    # ---- terminal readiness constraint H x_N <= h_term
    if spec.terminal is not None:
        H, h_term = spec.terminal
        H = np.atleast_2d(np.asarray(H, dtype=float))
        for row, b in zip(H, np.atleast_1d(h_term)):
            add(row @ X_coef[N],
                float(b) - row @ X_const[N] - tube.terminal_margin(row, N))

    base = {"P_base_W": P_base, "P_pump_W": P_pump, "cop_ref": cop_ref,
            "chiller_share_W": chiller_share}
    return Lifted(G=np.array(rows), h=np.array(rhs), n=n, m=m, N=N, p=p, spec=spec,
                  q_ub=chiller_share, base=base, X_coef=X_coef, X_const=X_const)


def with_terminal(p: PlantParams, spec: EnvelopeSpec, H: np.ndarray, h: np.ndarray) -> Lifted:
    return build_lifted(p, replace(spec, terminal=(H, h)))
