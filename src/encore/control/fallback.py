"""Certified fallback policy (guide 6.5, D-028).

The fallback is the fixed-gain tube policy u = u_nom + K (x - x_nom) around a nominal
deliverable trajectory. Its certificate is exactly the feasibility of the
tube-TIGHTENED lifted LP (reachability.build_lifted with TubeMargins): if that LP is
feasible at (x_0, q), the policy keeps safety and delivery for every disturbance
trajectory inside W(c). "Certified" means precisely this and nothing more.

simulate_policy() plays the policy against realized disturbances (inside or outside the
box) with physically-clipped inputs, and reports safety/delivery outcomes — the
empirical side of Thm 2.
"""

from __future__ import annotations

import numpy as np

from ..envelope.geometry import extract_trajectory, max_q
from ..envelope.reachability import EnvelopeSpec, activation_steps, build_lifted
from ..plant import power
from ..plant.dynamics import discrete_matrices
from ..plant.params import PlantParams
from ..plant.virtual_input import T_in_floor, q_ext_bounds
from ..tighten.tube import TubeMargins


def certify(p: PlantParams, spec: EnvelopeSpec, tube: TubeMargins, x0: np.ndarray,
            q: float):
    """Return the fallback certificate at offer q [W], or None if not certifiable."""
    L = build_lifted(p, spec, tube=tube)
    traj = extract_trajectory(L, x0, q)
    if traj is None:
        return None
    X_nom, U_nom = traj
    return {"x_nom": X_nom, "u_nom": U_nom, "K": tube.K, "q": q, "spec": spec,
            "base": L.base}


def certified_max_q(p: PlantParams, spec: EnvelopeSpec, tube: TubeMargins,
                    x0: np.ndarray) -> float:
    """F-tilde(x, c): max offer certifiable under the tube policy [W]."""
    return max_q(build_lifted(p, spec, tube=tube), x0)


def simulate_policy(p: PlantParams, cert: dict, w_steps: np.ndarray, dew_res: float,
                    controller=None, x0: np.ndarray | None = None) -> dict:
    """Play one hour against realized disturbances.

    w_steps: (N,) realized per-step heat deviations [W]; dew_res: realized dew residual
    [K]. controller(t, x) -> u overrides the fallback policy (used by the MPC layer);
    inputs are clipped into the REALIZED U(x) before applying — physical actuation.
    x0: the ACTUAL starting state (defaults to the certificate's nominal start; the day
    simulator must pass the carried state — hour boundaries never teleport, D-046).
    """
    spec: EnvelopeSpec = cert["spec"]
    N = spec.horizon_steps
    m_act = activation_steps(spec)
    Ad, Bud, Bwd = discrete_matrices(p, 2, p.dt_ctrl)
    X_nom, U_nom, K = cert["x_nom"], cert["u_nom"], cert["K"]
    base = cert["base"]
    T_dew_real = spec.T_dew + dew_res
    floor_real = T_in_floor(p, T_dew_real)

    x = (X_nom[0] if x0 is None else np.asarray(x0, dtype=float)).copy()
    X = [x.copy()]
    U, P = [], []
    viol_T = 0.0
    clip_amount = 0.0
    for t in range(N):
        if controller is None:
            u = float(U_nom[t, 0] + K[0] @ (x - X_nom[t]))
        else:
            u = float(controller(t, x))
        lb, ub = q_ext_bounds(p, x[1], T_dew_real)
        u_cl = float(np.clip(u, lb, ub))
        clip_amount = max(clip_amount, abs(u_cl - u))
        x = Ad @ x + Bud @ [u_cl] + Bwd @ [p.Q_IT_nom + w_steps[t]]
        X.append(x.copy())
        U.append(u_cl)
        P.append(base["P_pump_W"] + u_cl / base["cop_ref"])
        viol_T = max(viol_T, x[0] - p.T_max)

    # settlement counts the WHOLE hour (guide 5.3, D-048)
    delivered = sum((base["P_base_W"] - P[t]) * p.dt_ctrl for t in range(N))
    required = cert["q"] * m_act * p.dt_ctrl
    # condensation check at realized dew: supply floor violated iff extraction demands
    # T_in below floor_real, i.e. u exceeded the realized upper bound (already clipped);
    # clipping > tol therefore flags the constraint encounter
    return {
        "X": np.array(X), "U": np.array(U), "P_W": np.array(P),
        "T_viol_K": float(viol_T),
        "delivered_J": float(delivered), "required_J": float(required),
        "delivery_ok": delivered >= required - 1e-6,
        "delivery_ratio": float(delivered / required) if required > 0 else 1.0,
        "max_clip_W": float(clip_amount),
        "floor_real_C": floor_real,
    }


def fallback_controller(cert: dict):
    """The certified policy as a controller callback."""
    X_nom, U_nom, K = cert["x_nom"], cert["u_nom"], cert["K"]

    def ctl(t, x):
        return float(U_nom[t, 0] + K[0] @ (x - X_nom[t]))

    return ctl
