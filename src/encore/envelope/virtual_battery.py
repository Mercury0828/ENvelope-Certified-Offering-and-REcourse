"""Phase 2 — virtual-battery reparameterization (Thm 1 payload, guide 6.3).

Closed-form battery parameters of the deliverable set, in *power-cut* units (a cut of
1 W sustained for 1 s drains COP_ref W·s of thermal storage 1 W of cut):

  T_w_hi          = T_max - Q_IT/h_jw                      hottest sustainable loop temp
                                                           (quasi-steady junction gap)
  T_w_lo(c)       = T_in_floor(T_dew) + Q_IT/(m_max cp)    coldest sustainable loop temp
                                                           (condensation-coupled!)
  E_cap(c)        = (C_j + C_w)(T_w_hi - T_w_lo)/COP_ref   capacity   [W·s of cut]
                    [+ C_f (T_f_max - T_f_lo(c))/COP_ref in the 3-state plant,
                     T_f_lo = T_in_floor - delta_hx]
  P_max(x)        = chiller_share - max(0, m_min cp (T_w - T_in_max))/COP_ref
                    max discharge (cut) rate; the second term is the forced-extraction
                    penalty once the loop return exceeds the supply ceiling
  P_chg(x, c)     = (m_max cp (T_w - T_in_floor) - Q_IT)/COP_ref      max charge rate
  alpha(c)        = Q_IT c1 / COP(T_in)^2     [W of extra hold power per K of pre-cool]
                    leakage analog: zero in the frozen-COP surrogate (D-006), reported
                    symbolically from the affine COP slope

"A battery whose capacity depends on the weather": E_cap falls linearly with T_dew once
the condensation margin overtakes the equipment floor (T_dew > T_in_min - delta_cond).

The predicted frontier q(d) = min(P_max_deep, E_avail(x_0)/d) is checked against the
Phase-1 LP frontier (event-only, sustained) in the Phase-2 experiments.
"""

from __future__ import annotations

import numpy as np

from ..plant import power
from ..plant.params import PlantParams
from ..plant.virtual_input import T_in_floor


def vb_params(p: PlantParams, T_dew: float, T_wb: float, n_states: int = 2) -> dict:
    Q = p.Q_IT_nom
    cop_ref = float(power.cop(p, p.T_in_nom, T_wb))
    P_pump = float(power.pump_power(p, p.m_dot_nom))
    chiller_share = Q / cop_ref
    floor = T_in_floor(p, T_dew)

    T_w_hi = p.T_max - Q / p.h_jw
    T_w_lo = floor + Q / (p.m_dot_max * p.cp)
    E_th = (p.C_j + p.C_w) * (T_w_hi - T_w_lo)            # J thermal
    out = {
        "cop_ref": cop_ref,
        "chiller_share_W": chiller_share,
        "T_w_hi_C": T_w_hi,
        "T_w_lo_C": T_w_lo,
        "alpha_hold_W_per_K": Q * p.cop_c1 / power.cop(p, p.T_in_nom, T_wb) ** 2,
    }
    if n_states == 3:
        T_f_lo = floor - p.delta_hx
        E_th += p.C_f * (p.T_f_max - T_f_lo)
        out["T_f_lo_C"] = T_f_lo
    out["E_cap_cut_J"] = E_th / cop_ref                   # W·s of deliverable cut
    out["E_cap_cut_kWh"] = E_th / cop_ref / 3.6e6
    return out


def discharge_limit(p: PlantParams, T_w: float, T_wb: float) -> float:
    """P_max(x): max instantaneous cut [W] at loop temperature T_w (2-state)."""
    cop_ref = float(power.cop(p, p.T_in_nom, T_wb))
    chiller_share = p.Q_IT_nom / cop_ref
    forced = max(0.0, p.m_dot_min * p.cp * (T_w - p.T_in_max))
    return chiller_share - forced / cop_ref


def charge_limit(p: PlantParams, T_w: float, T_dew: float, T_wb: float) -> float:
    """P_chg(x, c): max instantaneous pre-cool (charge) rate [W of extra extraction/COP]."""
    cop_ref = float(power.cop(p, p.T_in_nom, T_wb))
    ub = p.m_dot_max * p.cp * (T_w - T_in_floor(p, T_dew))
    return (ub - p.Q_IT_nom) / cop_ref


def vb_frontier(p: PlantParams, T_dew: float, T_wb: float, d_min: float,
                T_w0: float, n_states: int = 2, T_f0: float | None = None) -> float:
    """Closed-form predicted max sustainable cut q(d) [W] from initial loop temp T_w0.

    Energy term: storage available between the initial state and the hot limits;
    power term: discharge limit at the *hottest* point of the path (conservative).
    """
    vb = vb_params(p, T_dew, T_wb, n_states)
    cop_ref = vb["cop_ref"]
    E_th = (p.C_j + p.C_w) * max(0.0, vb["T_w_hi_C"] - T_w0)
    if n_states == 3:
        T_f0 = (p.T_in_nom - p.delta_hx) if T_f0 is None else T_f0
        E_th += p.C_f * max(0.0, p.T_f_max - T_f0)
        P_max_path = vb["chiller_share_W"]      # extraction continues into facility loop
    else:
        P_max_path = discharge_limit(p, vb["T_w_hi_C"], T_wb)
    return float(min(P_max_path, (E_th / cop_ref) / (d_min * 60.0)))
