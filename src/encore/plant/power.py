"""Cooling power map (guide 6.1).

P_cool = P_pump(m_dot) + P_chiller, with
  P_pump : 3-segment piecewise-affine (convex, max-of-affines) approximation of a_p m^3
  P_chiller = q_rej / COP,  COP affine in (T_supply - T_wb), clamped to [cop_min, cop_max]

The two free COP coefficients are calibrated so the 17->25 degC supply-temperature sweep
reproduces the [Gheni26] ~63.3% cooling-power reduction (trend anchor, D-014).
"""

from __future__ import annotations

import numpy as np

from .params import PlantParams


# ----------------------------------------------------------------- pump (PWA)

def pump_pwa_coeffs(p: PlantParams):
    """Chord (secant) coefficients of the 3-segment PWA over [m_dot_min, m_dot_max].

    Returns (slopes a_k [W/(kg/s)], intercepts b_k [W]); the PWA value is
    max_k (a_k m + b_k). Chords of a convex function upper-bound it (conservative
    power over-estimate) and match it exactly at the 4 breakpoints.
    """
    bps = np.linspace(p.m_dot_min, p.m_dot_max, p.pwa_segments + 1)
    f = p.a_p * bps**3
    slopes = np.diff(f) / np.diff(bps)
    intercepts = f[:-1] - slopes * bps[:-1]
    return slopes, intercepts


def pump_power(p: PlantParams, m_dot, pwa: bool = True):
    """Pump power [W]; PWA (default, optimization-consistent) or exact cubic."""
    m_dot = np.asarray(m_dot, dtype=float)
    if not pwa:
        return p.a_p * m_dot**3
    a, b = pump_pwa_coeffs(p)
    return np.max(a[:, None] * m_dot[None, :] + b[:, None], axis=0) if m_dot.ndim \
        else float(np.max(a * m_dot + b))


# --------------------------------------------------------------------- chiller

def cop(p: PlantParams, T_supply, T_wb: float):
    """Effective COP, affine in (T_supply - T_wb), clamped (guide 6.1)."""
    val = p.cop_c0 + p.cop_c1 * (np.asarray(T_supply, dtype=float) - T_wb)
    return np.clip(val, p.cop_min, p.cop_max)


def chiller_power(p: PlantParams, q_rej, T_supply, T_wb: float):
    """P_chiller = q_rej / COP [W]."""
    return np.asarray(q_rej, dtype=float) / cop(p, T_supply, T_wb)


def cooling_power(p: PlantParams, m_dot, T_in, q_rej, T_wb: float):
    """Total cooling power [W] = PWA pump + chiller."""
    return pump_power(p, m_dot) + chiller_power(p, q_rej, T_in, T_wb)


# ----------------------------------------------------------------- calibration

def fit_cop_coefficients(p: PlantParams) -> dict:
    """Fit (c0, c1) to the [Gheni26] supply-sweep trend (D-014).

    Conditions:
      (i)  COP(T_lo - T_wb_cal) = cop_at_lo_anchor                       [est anchor]
      (ii) P_cool(T_hi) = (1 - reduction_target) * P_cool(T_lo)          [Gheni26]
    with Q_IT at nominal, pump at nominal flow (PWA value), steady state q_rej = Q_IT.
    Two affine conditions in (c0, c1) -> closed form.
    """
    g = p.gheni
    T_wb = float(g["T_wb_calib_C"])
    T_lo, T_hi = float(g["T_supply_lo_C"]), float(g["T_supply_hi_C"])
    target = float(g["power_reduction_target"])
    cop_lo = float(g["cop_at_lo_anchor"])

    P_pump_nom = pump_power(p, p.m_dot_nom)
    Q = p.Q_IT_nom
    P_lo = P_pump_nom + Q / cop_lo
    chiller_hi = (1.0 - target) * P_lo - P_pump_nom
    if chiller_hi <= 0:
        raise ValueError("Gheni target unreachable: pump power alone exceeds target")
    cop_hi = Q / chiller_hi

    d_lo, d_hi = T_lo - T_wb, T_hi - T_wb
    c1 = (cop_hi - cop_lo) / (d_hi - d_lo)
    c0 = cop_lo - c1 * d_lo
    return {
        "cop_c0": float(c0),
        "cop_c1_per_K": float(c1),
        "cop_at_lo": cop_lo,
        "cop_at_hi": float(cop_hi),
        "P_cool_lo_W": float(P_lo),
        "P_cool_hi_W": float(P_pump_nom + chiller_hi),
        "reduction_target": target,
    }
