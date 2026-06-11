"""D-day simulator: 24 hours with state continuity, activation calls, settlement inputs.

Per hour: if activated, the hour's controller runs the committed event (B4: certified
fallback or tube-margin MPC; B2/B3: the same MPC machinery WITHOUT margins around an
uncertified plan — they have no certificate, that is their defining weakness); if idle,
a track-to-ready feedback law re-positions the plant for the next obligation (D-039).
All controllers face identical realized disturbances and activation calls (common
random numbers). Outputs 5-min P_cool and T_j series for settlement.
"""

from __future__ import annotations

import numpy as np

from ..control.fallback import fallback_controller, simulate_policy
from ..control.mpc import mpc_controller
from ..envelope.geometry import extract_trajectory
from ..envelope.reachability import build_lifted
from ..plant.params import PlantParams
from ..market.offering import HourPlan

STEPS_H = 12


def _idle_controller(p: PlantParams, x_ready: np.ndarray, K: np.ndarray):
    """Track-to-ready law: u = Q_IT + K (x - x_ready)."""
    def ctl(t, x):
        return float(p.Q_IT_nom + K[0] @ (np.asarray(x) - x_ready))
    return ctl


def run_day(p: PlantParams, plans: list[HourPlan], activations: np.ndarray,
            w_day: np.ndarray, dew_res_day: np.ndarray, K: np.ndarray,
            controller: str = "mpc") -> dict:
    """controller in {'fallback', 'mpc', 'idle'} ('idle' = B1, never participates).

    activations: (24,) bool; w_day: (24, 12) realized heat deviations [W];
    dew_res_day: (24,) realized dew residuals [K]. Returns 5-min series + logs.
    """
    x = plans[0].x_ready.copy()
    P_all, Tj_all, switches, infeasible_starts = [], [], 0, 0

    for h in range(24):
        plan = plans[h]
        activated = bool(activations[h]) and plan.q_W > 0 and controller != "idle"
        if activated:
            L = build_lifted(p, plan.spec, tube=plan.tube)
            traj = extract_trajectory(L, x, plan.q_W)
            if traj is None:
                # actual state cannot start the committed event (e.g. insufficient
                # re-positioning) — fall back to the D-1 plan from the ready state;
                # feedback absorbs the gap. Counted and reported.
                infeasible_starts += 1
                traj = extract_trajectory(L, plan.x_ready, plan.q_W)
            cert = {"x_nom": traj[0], "u_nom": traj[1], "K": K, "q": plan.q_W,
                    "spec": plan.spec, "base": L.base}
            if controller == "mpc":
                ctl, st = mpc_controller(p, cert, tube=plan.tube)
                out = simulate_policy(p, cert, w_day[h], dew_res_day[h], controller=ctl)
                switches += int(st["switched"])
            else:
                out = simulate_policy(p, cert, w_day[h], dew_res_day[h])
        else:
            L = build_lifted(p, plan.spec)          # for base power bookkeeping
            cert = {"x_nom": np.tile(plan.x_ready, (STEPS_H + 1, 1)),
                    "u_nom": np.full((STEPS_H, 1), p.Q_IT_nom), "K": K,
                    "q": 0.0, "spec": plan.spec, "base": L.base}
            ctl = _idle_controller(p, plan.x_ready, K)
            out = simulate_policy(p, cert, w_day[h], dew_res_day[h], controller=ctl)
        # state continuity: hour h+1 starts where hour h ended (overwrite x)
        x = out["X"][-1].copy()
        P_all.append(out["P_W"])
        Tj_all.append(out["X"][:-1, 0])

    return {
        "P_cool_W": np.concatenate(P_all),
        "T_j": np.concatenate(Tj_all),
        "switches": switches,
        "infeasible_starts": infeasible_starts,
    }
