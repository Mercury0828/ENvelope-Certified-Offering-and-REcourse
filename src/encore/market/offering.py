"""D-1 offering problem (guide 6.6), V1 per-hour separable form.

max over {q_h}:  sum_h  pi_cap_h q_h  -  E_scenarios[ RT-shift cost + degradation ]
subject to       (q_h, d) in F-tilde(x_ready(c_h), c_h)      (the envelope constraint)

Structure notes (logged D-036/D-037):
- The envelope constraint is enforced BY CONSTRUCTION: q_h is optimized over
  [0, F-tilde_h] only, and an assertion re-checks every offer against the envelope.
- Under the frozen-COP surrogate, in-box scenarios incur zero shortfall for the
  certified controller (that is what the certificate says), so the SAA penalty term
  vanishes for B4; B2/B3 use the same objective with their own (optimistic) envelopes
  and pay penalties at settlement instead — exactly the comparison the paper wants.
- RT energy term = energy-neutral shift (D-036): heat not extracted during the event
  is extracted during recovery at the same COP, so the expected RT cost difference is
  E[r_h] q_h DH (pi_rt_recovery - pi_rt_event). Negative when events sit on price peaks.
- Degradation: c_deg * integral [T_j - T_thr]_+ evaluated on the certified nominal plan
  trajectory per candidate q (exact for the plan; convex grid search per hour, D-037).
- Hours are separable in V1 because the plant re-enters the ready state between hours
  (readiness fixed point) and pre-cool holding is free under the frozen-COP surrogate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..control.fallback import certified_max_q
from ..envelope.geometry import extract_trajectory, max_q
from ..envelope.reachability import EnvelopeSpec, activation_steps, build_lifted
from ..plant.dynamics import steady_state
from ..plant.params import PlantParams
from ..plant.virtual_input import T_in_floor
from ..tighten.quantile_boxes import Box
from ..tighten.tube import build_tube

J_PER_MWH = 3.6e9


@dataclass
class HourPlan:
    hour: int
    q_W: float
    F_W: float                 # envelope value used (certified or naive)
    spec: EnvelopeSpec
    tube: object | None
    x_ready: np.ndarray
    expected_value_usd: float


def ready_state_for(p: PlantParams, T_dew_fc: float) -> np.ndarray:
    return steady_state(p, 2, p.Q_IT_nom, T_in_floor(p, T_dew_fc))[0]


def envelope_for(p: PlantParams, spec: EnvelopeSpec, x_ready, kind: str,
                 box: Box | None = None, K=None):
    """(F_W, tube) for the chosen certification style."""
    if kind == "certified":
        tube = build_tube(p, 2, spec.horizon_steps, w_Q=box.w_Q_sym, w_D=box.w_D,
                          K=K, E_budget=box.E_hi)
        return certified_max_q(p, spec, tube, x_ready), tube
    if kind == "deterministic":            # B2: naive envelope, no tightening
        return max_q(build_lifted(p, spec), x_ready), None
    if kind == "saa":                      # B3: empirical-scenario box, no guarantee
        tube = build_tube(p, 2, spec.horizon_steps, w_Q=box.w_Q_sym, w_D=box.w_D,
                          K=K, E_budget=box.E_hi)
        return certified_max_q(p, spec, tube, x_ready), tube
    raise ValueError(kind)


def degradation_usd(p: PlantParams, spec: EnvelopeSpec, tube, x_ready, q: float,
                    c_deg_per_Kh: float, T_thr: float) -> float:
    """Degradation cost of one activated hour at commitment q, on the nominal plan."""
    L = build_lifted(p, spec, tube=tube)
    traj = extract_trajectory(L, x_ready, q)
    if traj is None:
        return np.inf
    T_j = traj[0][:, 0]
    return c_deg_per_Kh * float(np.maximum(T_j - T_thr, 0.0).sum()) * (p.dt_ctrl / 3600.0)


def make_offers(p: PlantParams, contexts: list[dict], kind: str, boxes=None, K=None,
                d_min: float = 30.0, p_act: float = 0.15, c_deg_per_Kh: float = 2.0,
                T_thr: float = 70.0, n_grid: int = 15) -> list[HourPlan]:
    """One HourPlan per hour. contexts[h]: T_dew_fc, T_wb, pi_cap ($/MWh),
    pi_rt_event, pi_rt_recovery ($/MWh)."""
    plans = []
    r_act = d_min / 60.0
    for h, c in enumerate(contexts):
        x_ready = ready_state_for(p, c["T_dew_fc"])
        # Terminal readiness: V1 deliberately uses NO terminal constraint (D-041).
        # A ready-state-box terminal was tried and provably over-tightens (F-tilde = 0
        # everywhere — naive return-to-start terminals kill the product, which is
        # exactly why guide 6.3 defines readiness as a SET). Wiring the Phase-2
        # readiness polygon R(q) into committed plans is Phase-5 work; until then the
        # day simulator falls back to the D-1 plan on hot starts and reports the count.
        spec = EnvelopeSpec(n_states=2, T_dew=c["T_dew_fc"], T_wb=c["T_wb"], d_min=d_min)
        box = boxes[h] if boxes is not None else None
        F, tube = envelope_for(p, spec, x_ready, kind, box=box, K=K)
        F = max(F, 0.0)

        best_q, best_v = 0.0, 0.0
        if F > 0:
            shift = (c["pi_rt_recovery"] - c["pi_rt_event"]) / J_PER_MWH  # $/J shifted
            for q in np.linspace(0.0, F - 100.0, n_grid)[1:]:
                deg = degradation_usd(p, spec, tube, x_ready, q, c_deg_per_Kh, T_thr)
                value = (c["pi_cap"] * q * 3600.0 / J_PER_MWH
                         - p_act * (r_act * q * 3600.0 * shift + deg))
                if value > best_v:
                    best_q, best_v = float(q), float(value)
        # the envelope constraint, by construction and re-asserted:
        assert best_q <= F + 1e-6, "offer exceeds its envelope — construction broken"
        plans.append(HourPlan(hour=h, q_W=best_q, F_W=F, spec=spec, tube=tube,
                              x_ready=x_ready, expected_value_usd=best_v))
    return plans
