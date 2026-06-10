"""Phase 1 — duration accounting (guide Section 11, GO/NO-GO gate #1).

For a candidate sustained cooling-power cut q [W] and duration d, a small feasibility LP
over the 5-min control model decides whether an open-loop input trajectory exists that
keeps T_j <= T_max and T_in >= T_dew + delta_cond (encoded in U(x)) throughout, while
realized cooling power stays <= P_base - q. Bisection on q gives the frontier q*(d).

Conservative affine power surrogate (D-006): P_cool,t = P_pump(m_nom) + q_rej,t/COP_ref
with COP_ref at baseline supply temperature — so the power-cut requirement becomes the
affine cap  q_rej,t <= COP_ref (P_base - P_pump_nom - q).

LP variables: z = [x_1..x_N, u_0..u_{N-1}]; all constraints affine (no bilinear terms).
Solver: scipy HiGHS (D-009).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from ..plant import power
from ..plant.dynamics import discrete_matrices, steady_state
from ..plant.params import PlantParams, with_extra_facility_mass
from ..plant.virtual_input import T_in_floor


@dataclass(frozen=True)
class DurationCase:
    """One cell of the Phase-1 grid."""
    scenario: str           # "S1" (2-state) | "S2" (3-state) | "S3" (3-state + tank, SENSITIVITY ONLY)
    workload: str           # "nominal" | "burst"
    init: str               # "nominal" | "precooled"
    weather: str            # "dry" | "humid"
    T_dew: float            # degC
    T_wb: float             # degC

    @property
    def n_states(self) -> int:
        return 2 if self.scenario == "S1" else 3

    @property
    def label(self) -> str:
        return f"{self.scenario}/{self.workload}/{self.init}/{self.weather}"


def case_params(p: PlantParams, case: DurationCase) -> PlantParams:
    if case.scenario == "S3":
        return with_extra_facility_mass(p, p.C_tank)
    return p


def baseline_power(p: PlantParams, T_wb: float) -> dict:
    """Frozen no-event baseline (guide 5.4): nominal load, nominal supply temp, pump nominal."""
    P_pump = float(power.pump_power(p, p.m_dot_nom))
    cop_ref = float(power.cop(p, p.T_in_nom, T_wb))
    P_base = P_pump + p.Q_IT_nom / cop_ref
    return {"P_base_W": P_base, "P_pump_W": P_pump, "cop_ref": cop_ref}


def build_Q_trace(p: PlantParams, workload: str, n_steps: int) -> np.ndarray:
    """Per-5-min peak IT heat trace [W] over the event window (D-008).

    Defined on absolute event time and truncated to n_steps, so the frontier's
    monotonicity in d is structural (prefix property).
    """
    trace = np.full(12, p.Q_IT_nom)
    if workload == "burst":
        trace[[1, 4]] = 1.2 * p.Q_IT_nom   # +20% squares, minutes 5-10 and 20-25 [est]
    elif workload != "nominal":
        raise ValueError(f"unknown workload {workload}")
    if n_steps > trace.size:
        raise ValueError("event longer than defined trace window")
    return trace[:n_steps].copy()


def initial_state(p: PlantParams, case: DurationCase) -> np.ndarray:
    """Pre-event steady state: nominal supply temp, or pre-cooled to the condensation
    floor (ready state, D-012)."""
    T_in0 = p.T_in_nom if case.init == "nominal" else T_in_floor(p, case.T_dew)
    x0, _ = steady_state(p, case.n_states, p.Q_IT_nom, T_in0)
    return x0


def feasibility_lp(p: PlantParams, case: DurationCase, x0: np.ndarray, q_cut: float,
                   n_steps: int, return_traj: bool = False):
    """Is a sustained cut of q_cut [W] below baseline feasible for n_steps 5-min steps?

    Returns bool (and optionally the state/input trajectory found).
    """
    n = case.n_states
    m = 1 if n == 2 else 2
    N = n_steps
    dt = p.dt_ctrl

    base = baseline_power(p, case.T_wb)
    q_rej_cap = base["cop_ref"] * (base["P_base_W"] - base["P_pump_W"] - q_cut)
    if q_rej_cap < -1e-9:
        return (False, None) if return_traj else False
    q_rej_cap = max(q_rej_cap, 0.0)

    Ad, Bud, Bwd = discrete_matrices(p, n, dt)
    Q_trace = build_Q_trace(p, case.workload, N)
    floor = T_in_floor(p, case.T_dew)
    mc_max = p.m_dot_max * p.cp
    mc_min = p.m_dot_min * p.cp
    ramp = p.q_ext_ramp * dt
    u_ext_pre = p.Q_IT_nom        # pre-event extraction equals the load (steady state)

    nz = N * n + N * m

    def xi(t):           # x_t slice start (t = 1..N)
        return (t - 1) * n

    def ui(t):           # u_t slice start (t = 0..N-1)
        return N * n + t * m

    # ----- equalities: x_{t+1} = Ad x_t + Bud u_t + Bwd Q_t
    A_eq = np.zeros((N * n, nz))
    b_eq = np.zeros(N * n)
    for t in range(N):
        r = slice(t * n, (t + 1) * n)
        A_eq[r, xi(t + 1): xi(t + 1) + n] = np.eye(n)
        if t > 0:
            A_eq[r, xi(t): xi(t) + n] = -Ad
        A_eq[r, ui(t): ui(t) + m] = -Bud
        b_eq[r] = (Bwd @ [Q_trace[t]]).ravel()
        if t == 0:
            b_eq[r] += Ad @ x0

    # ----- inequalities A_ub z <= b_ub
    rows, rhs = [], []

    def add(row, b):
        rows.append(row)
        rhs.append(b)

    for t in range(1, N + 1):
        # T_j,t <= T_max
        r = np.zeros(nz); r[xi(t) + 0] = 1.0
        add(r, p.T_max)
        if n == 3:
            r = np.zeros(nz); r[xi(t) + 2] = 1.0
            add(r, p.T_f_max)

    # state-dependent input bounds, enforced at both step endpoints (D-010)
    for t in range(N):
        for s in (t, t + 1):  # endpoint state index (0 = known x0)
            if s == 0:
                T_w0 = x0[1]
                T_f0 = x0[2] if n == 3 else None
                # ub: u_ext <= mc_max (T_w0 - floor)
                r = np.zeros(nz); r[ui(t)] = 1.0
                add(r, mc_max * (T_w0 - floor))
                # lb: -u_ext <= -mc_min (T_w0 - T_in_max)
                r = np.zeros(nz); r[ui(t)] = -1.0
                add(r, -mc_min * (T_w0 - p.T_in_max))
                if n == 3:
                    r = np.zeros(nz); r[ui(t)] = 1.0
                    add(r, mc_max * (T_w0 - T_f0 - p.delta_hx))
            else:
                # ub: u_ext - mc_max T_w,s <= -mc_max floor
                r = np.zeros(nz); r[ui(t)] = 1.0; r[xi(s) + 1] = -mc_max
                add(r, -mc_max * floor)
                # lb: -u_ext + mc_min T_w,s <= mc_min T_in_max
                r = np.zeros(nz); r[ui(t)] = -1.0; r[xi(s) + 1] = mc_min
                add(r, mc_min * p.T_in_max)
                if n == 3:
                    r = np.zeros(nz); r[ui(t)] = 1.0
                    r[xi(s) + 1] = -mc_max; r[xi(s) + 2] = mc_max
                    add(r, -mc_max * p.delta_hx)

    # ramp on q_ext (incl. transition from pre-event level, D-011)
    for t in range(N):
        r = np.zeros(nz); r[ui(t)] = 1.0
        rprev = np.zeros(nz)
        prev_const = 0.0
        if t == 0:
            prev_const = u_ext_pre
        else:
            rprev[ui(t - 1)] = 1.0
        add(r - rprev, ramp + prev_const)
        add(rprev - r, ramp - prev_const)

    A_ub = np.array(rows)
    b_ub = np.array(rhs)

    # variable bounds: power-cut cap on the rejection channel
    bounds = []
    for t in range(1, N + 1):
        for _ in range(n):
            bounds.append((None, None))
    for t in range(N):
        if n == 2:
            bounds.append((None, q_rej_cap))                       # u = q_ext (= q_rej)
        else:
            bounds.append((None, None))                            # q_ext
            bounds.append((0.0, min(q_rej_cap, p.q_rej_max)))      # q_rej

    res = linprog(c=np.zeros(nz), A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=bounds, method="highs")
    feasible = res.status == 0
    if not return_traj:
        return feasible
    if not feasible:
        return False, None
    X = np.vstack([x0, res.x[: N * n].reshape(N, n)])
    U = res.x[N * n:].reshape(N, m)
    return True, {"X": X, "U": U}


def max_sustainable_cut(p: PlantParams, case: DurationCase, d_min: float,
                        tol_W: float = 50.0) -> dict:
    """Bisection on q around the feasibility LP. d_min in minutes (multiple of 5)."""
    pc = case_params(p, case)
    n_steps = int(round(d_min / (pc.dt_ctrl / 60.0)))
    if n_steps < 1:
        raise ValueError("duration below one control step")
    x0 = initial_state(pc, case)
    base = baseline_power(pc, case.T_wb)
    q_ub = base["P_base_W"] - base["P_pump_W"]   # cut everything the chiller draws

    if not feasibility_lp(pc, case, x0, 0.0, n_steps):
        raise RuntimeError(f"q=0 infeasible for {case.label} d={d_min} — model bug")

    if feasibility_lp(pc, case, x0, q_ub, n_steps):
        q_star = q_ub
    else:
        lo, hi = 0.0, q_ub
        while hi - lo > tol_W:
            mid = 0.5 * (lo + hi)
            if feasibility_lp(pc, case, x0, mid, n_steps):
                lo = mid
            else:
                hi = mid
        q_star = lo

    _, traj = feasibility_lp(pc, case, x0, q_star, n_steps, return_traj=True)
    out = {
        "q_W": q_star,
        "q_frac_of_base": q_star / base["P_base_W"],
        "P_base_W": base["P_base_W"],
        "cop_ref": base["cop_ref"],
        "x0": x0.tolist(),
        "d_min": d_min,
    }
    if traj is not None:
        out["peak_T_j"] = float(traj["X"][:, 0].max())
        out["peak_T_w"] = float(traj["X"][:, 1].max())
        if case.n_states == 3:
            out["peak_T_f"] = float(traj["X"][:, 2].max())
    return out
