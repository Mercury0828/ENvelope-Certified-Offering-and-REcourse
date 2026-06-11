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
from ..plant.dynamics import steady_state
from ..plant.params import PlantParams
from ..market.offering import HourPlan

STEPS_H = 12


K_RECOVERY = 60e3      # [W/K] sprint gain for idle/recovery hours (D-048): commands
                       # full extraction/rejection headroom when hot (clipped into the
                       # realized U(x) by the simulator), recovering a 15 K post-event
                       # excursion in ~20 min — one uncommitted hour between events
                       # (adjacency pruning) therefore restores the e0-ball ready state
                       # by construction, replacing the LP terminal constraint.


def _idle_controller(p: PlantParams, target: np.ndarray, n: int):
    """Sprint track-to-target law: q_ext on T_w error (+ q_rej on T_f error, n=3)."""
    def ctl(t, x):
        x = np.asarray(x)
        u_ext = p.Q_IT_nom + K_RECOVERY * (x[1] - target[1])
        if n == 2:
            return float(u_ext)
        u_rej = p.Q_IT_nom + K_RECOVERY * (x[2] - target[2])
        return np.array([u_ext, u_rej])
    return ctl


def _idle_target(p: PlantParams, plan: HourPlan, next_plan: HourPlan | None,
                 participates: bool, n: int) -> np.ndarray:
    """Idle hours hold the NOMINAL operating point (the no-market baseline, D-035;
    floor-limited in humid weather) — pre-cooling to a ready state happens only when
    the NEXT hour carries a commitment (the D-1 pre-positioning plan, D-045)."""
    if participates and next_plan is not None and next_plan.q_W > 0:
        return next_plan.x_ready
    T_in_idle = max(p.T_in_nom, plan.spec.T_dew + p.delta_cond)
    return steady_state(p, n, p.Q_IT_nom, T_in_idle)[0]


def run_day(p: PlantParams, plans: list[HourPlan], activations: np.ndarray,
            w_day: np.ndarray, dew_res_day: np.ndarray, K: np.ndarray,
            controller: str = "mpc") -> dict:
    """controller in {'fallback', 'mpc', 'idle'} ('idle' = B1, never participates).

    activations: (24,) bool; w_day: (24, 12) realized heat deviations [W];
    dew_res_day: (24,) realized dew residuals [K]. Returns 5-min series + logs.
    """
    x = plans[0].x_ready.copy()
    P_all, Tj_all, switches, infeasible_starts = [], [], 0, 0
    infeasible_hours = []    # hours whose committed event started outside the
                             # certificate's e0-ball (warm starts; D-046/D-047)
    clip_events = 0          # hours where the realized condensation floor clipped u

    n = plans[0].spec.n_states
    n_inputs = 1 if n == 2 else 2
    for h in range(24):
        plan = plans[h]
        activated = bool(activations[h]) and plan.q_W > 0 and controller != "idle"
        if activated:
            L = build_lifted(p, plan.spec, tube=plan.tube)
            traj = extract_trajectory(L, x, plan.q_W)
            if traj is None:
                # actual state cannot start the committed event (insufficient
                # re-positioning) — keep the D-1 plan from the ready state as the
                # REFERENCE, but simulate from the TRUE carried state: feedback must
                # genuinely absorb the gap (e_0 != 0; covered by the e0 ball when
                # within 1.5 K, counted regardless; D-046/D-047).
                infeasible_starts += 1
                infeasible_hours.append(h)
                traj = extract_trajectory(L, plan.x_ready, plan.q_W)
            cert = {"x_nom": traj[0], "u_nom": traj[1], "K": K, "q": plan.q_W,
                    "spec": plan.spec, "base": L.base}
            if controller == "mpc" and n == 2:
                ctl, st = mpc_controller(p, cert, tube=plan.tube)
                out = simulate_policy(p, cert, w_day[h], dew_res_day[h], controller=ctl,
                                      x0=x)
                switches += int(st["switched"])
            else:
                # n=3 events run the certified fallback policy directly (D-049: the
                # certificate IS the fallback; the cheap-MPC layer remains 2-state)
                out = simulate_policy(p, cert, w_day[h], dew_res_day[h], x0=x)
        else:
            L = build_lifted(p, plan.spec)          # for base power bookkeeping
            target = _idle_target(p, plan, plans[h + 1] if h < 23 else None,
                                  participates=(controller != "idle"), n=n)
            cert = {"x_nom": np.tile(target, (STEPS_H + 1, 1)),
                    "u_nom": np.full((STEPS_H, n_inputs), p.Q_IT_nom), "K": K,
                    "q": 0.0, "spec": plan.spec, "base": L.base}
            ctl = _idle_controller(p, target, n)
            out = simulate_policy(p, cert, w_day[h], dew_res_day[h], controller=ctl,
                                  x0=x)
        # state continuity: hour h+1 starts where hour h ended (overwrite x)
        x = out["X"][-1].copy()
        P_all.append(out["P_W"])
        Tj_all.append(out["X"][:-1, 0])
        clip_events += int(out["max_clip_W"] > 1e3)

    return {
        "P_cool_W": np.concatenate(P_all),
        "T_j": np.concatenate(Tj_all),
        "switches": switches,
        "infeasible_starts": infeasible_starts,
        "infeasible_hours": infeasible_hours,
        "clip_events": clip_events,
    }
