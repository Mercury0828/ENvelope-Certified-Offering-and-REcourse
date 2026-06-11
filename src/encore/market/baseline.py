"""Exogenous no-offer baseline P-bar^cool,0 (guide 5.4, D-035).

The baseline is the forecast-based optimal cooling schedule WITHOUT market
participation, computed once and frozen — never a decision variable.

Under the frozen-COP power surrogate (D-006), total daily cooling energy is invariant
across schedules that return to their initial state (every joule of IT heat is
extracted at the same COP), so the no-market optimum is flat: hold the nominal steady
state, P-bar_t = P_pump(nominal) + Q_IT/COP_ref. This makes B1 (no-market MPC) and the
baseline generator coincide by construction. When the COP(T_in) refinement is promoted
(PARKING_LOT), this module becomes a genuine optimization; the interface already takes
the day's forecasts.
"""

from __future__ import annotations

import numpy as np

from ..envelope.duration import baseline_power
from ..plant.params import PlantParams


def baseline_day(p: PlantParams, T_wb: float, n_steps: int = 288) -> dict:
    base = baseline_power(p, T_wb)
    return {
        "P_base_W": np.full(n_steps, base["P_base_W"]),
        "P_base_scalar_W": base["P_base_W"],
        "cop_ref": base["cop_ref"],
        "P_pump_W": base["P_pump_W"],
    }
