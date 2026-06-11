"""Settlement accounting — guide 5.3, implemented symbol-for-symbol.

Revenue   = sum_h pi_cap_h * q_h
Shortfall s_h = [ r_h q_h DH - sum_{t in T(h)} (Pbar_t - P_t) dt ]_+
Penalty   = sum_h gamma_h s_h,           gamma_h = 2 * pi_cap_h (default, 5.3)
RT cost   = sum_t P_t pi_rt_t dt         (cooling subsystem meter, 5.4)
Degr.     = c_deg * sum_t [T_j,t - T_thr]_+ dt
Profit    = Revenue - RT cost - Penalty - Degradation

Units: power in W internally, prices in $/MWh, energy converted once here.
The ledger carries every intermediate so tests can re-derive profit exactly.
"""

from __future__ import annotations

import numpy as np

J_PER_MWH = 3.6e9


def settle_day(q_W: np.ndarray, r: np.ndarray, pi_cap: np.ndarray,
               P_cool_W: np.ndarray, P_base_W: np.ndarray, pi_rt_5min: np.ndarray,
               T_j: np.ndarray, dt_s: float = 300.0, gamma_mult: float = 2.0,
               c_deg_per_Kh: float = 2.0, T_thr: float = 70.0) -> dict:
    """One-day ledger. q_W, r, pi_cap: (24,); P_cool_W, P_base_W, pi_rt_5min: (288,);
    T_j: (288,) or (289,) junction trajectory."""
    q_W = np.asarray(q_W, dtype=float)
    r = np.asarray(r, dtype=float)
    pi_cap = np.asarray(pi_cap, dtype=float)
    P = np.asarray(P_cool_W, dtype=float)
    Pb = np.asarray(P_base_W, dtype=float)
    T_j = np.asarray(T_j, dtype=float)[: P.size]
    steps_h = int(round(3600.0 / dt_s))
    assert P.size == 24 * steps_h == Pb.size == pi_rt_5min.size

    revenue = float(np.sum(pi_cap * q_W * 3600.0) / J_PER_MWH)

    shortfall_J = np.zeros(24)
    for h in range(24):
        if r[h] * q_W[h] <= 0.0:
            continue        # no activated obligation -> no settlement this hour (D-040)
        sl = slice(h * steps_h, (h + 1) * steps_h)
        delivered = float(np.sum((Pb[sl] - P[sl]) * dt_s))
        shortfall_J[h] = max(r[h] * q_W[h] * 3600.0 - delivered, 0.0)
    gamma = gamma_mult * pi_cap                       # $/MWh equivalent (5.3 default)
    penalty = float(np.sum(gamma * shortfall_J / J_PER_MWH))

    rt_cost = float(np.sum(P * np.asarray(pi_rt_5min) * dt_s) / J_PER_MWH)
    deg_Kh = float(np.sum(np.maximum(T_j - T_thr, 0.0)) * dt_s / 3600.0)
    degradation = c_deg_per_Kh * deg_Kh

    return {
        "revenue_usd": revenue,
        "rt_cost_usd": rt_cost,
        "penalty_usd": penalty,
        "degradation_usd": degradation,
        "profit_usd": revenue - rt_cost - penalty - degradation,
        "shortfall_J": shortfall_J,
        "shortfall_kWh_total": float(shortfall_J.sum() / 3.6e6),
        "delivered_ok_hours": int(np.sum((shortfall_J <= 1e-6) | (r * q_W <= 0))),
        "deg_Kh": deg_Kh,
        "gamma_mult": gamma_mult,
        "c_deg_per_Kh": c_deg_per_Kh,
        "T_thr": T_thr,
    }
