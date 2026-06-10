"""Virtual-input set U(x) and the map back to physical (m_dot, T_in) (guide 6.1).

The control is the heat-extraction rate q_ext [W] directly; the bilinear relation
q_ext = m_dot cp (T_w - T_in) is handled entirely by state-dependent, affine-in-x box
bounds. No bilinear terms ever enter optimization-facing code.

Bounds (all affine in x for fixed T_dew):
    q_ext >= m_dot_min cp (T_w - T_in_max)                      (may be negative)
    q_ext <= m_dot_max cp (T_w - T_in_floor(T_dew))             (condensation + T_in_min)
    q_ext <= m_dot_max cp (T_w - T_f - delta_hx)   [3-state]    (passive CDU, D-005)

The box is an exact image of the (m_dot, T_in) rectangle — hence an inner approximation
of nothing and outer of nothing, it IS U(x) — provided the effective supply-temperature
window [max(T_in_floor, T_f + delta_hx), T_in_max] is nonempty. The plant guarantees
this in operation: T_f <= T_f_max (35) gives a floor of at most 37 degC < T_in_max (45).
to_physical() raises outside that regime.
"""

from __future__ import annotations

import numpy as np

from .params import PlantParams


def T_in_floor(p: PlantParams, T_dew: float) -> float:
    """Lowest admissible supply temperature: max(equipment min, condensation margin)."""
    return max(p.T_in_min, T_dew + p.delta_cond)


def q_ext_bounds(p: PlantParams, T_w, T_dew: float, T_f=None):
    """Box bounds [q_lb(x), q_ub(x)] of U(x) [W]. Vectorized over T_w (and T_f)."""
    T_w = np.asarray(T_w, dtype=float)
    lb = p.m_dot_min * p.cp * (T_w - p.T_in_max)
    ub = p.m_dot_max * p.cp * (T_w - T_in_floor(p, T_dew))
    if T_f is not None:
        ub = np.minimum(ub, p.m_dot_max * p.cp * (T_w - np.asarray(T_f, dtype=float) - p.delta_hx))
    return lb, ub


def to_physical(p: PlantParams, q_ext: float, T_w: float, T_dew: float,
                T_f: float | None = None) -> tuple[float, float]:
    """Map (q_ext, x) to a feasible physical pair (m_dot, T_in).

    Chooses the minimum-pump-power realization: the smallest admissible flow such that
    the implied supply temperature stays above the effective floor. Raises ValueError
    if q_ext is outside U(x).
    """
    lb, ub = q_ext_bounds(p, T_w, T_dew, T_f)
    tol = 1e-6 * max(1.0, abs(p.Q_IT_nom))
    if not (lb - tol <= q_ext <= ub + tol):
        raise ValueError(f"q_ext={q_ext:.1f} W outside U(x)=[{lb:.1f}, {ub:.1f}] W")

    floor = T_in_floor(p, T_dew)
    if T_f is not None:
        floor = max(floor, T_f + p.delta_hx)
    if floor > p.T_in_max:
        raise ValueError(
            f"empty supply-temperature window: floor {floor:.2f} > T_in_max "
            f"{p.T_in_max:.2f} (T_f outside operating range?)"
        )

    if q_ext <= 0 or T_w <= floor:
        m_dot = p.m_dot_min
    else:
        m_dot = float(np.clip(q_ext / (p.cp * (T_w - floor)), p.m_dot_min, p.m_dot_max))
    T_in = T_w - q_ext / (m_dot * p.cp)
    # numerical guard: clamp T_in into its admissible interval and keep q consistent by
    # adjusting m_dot once more (only triggers within tol of the boundary)
    if T_in > p.T_in_max:
        T_in = p.T_in_max
        m_dot = float(np.clip(q_ext / (p.cp * (T_w - T_in)), p.m_dot_min, p.m_dot_max)) \
            if T_w > T_in else p.m_dot_min
    return m_dot, T_in


def from_physical(p: PlantParams, m_dot: float, T_in: float, T_w: float) -> float:
    """q_ext = m_dot cp (T_w - T_in) [W]."""
    return m_dot * p.cp * (T_w - T_in)
