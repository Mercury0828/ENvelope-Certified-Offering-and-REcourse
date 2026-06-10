"""Virtual-input set U(x): round-trip consistency and constraint compliance (guide 6.1)."""

import numpy as np
import pytest

from encore.plant.params import load_params
from encore.plant.virtual_input import (
    T_in_floor, from_physical, q_ext_bounds, to_physical,
)


@pytest.fixture(scope="module")
def p():
    return load_params()


def test_floor_tracks_dew_point(p):
    assert T_in_floor(p, 10.0) == p.T_in_min                 # equipment limit binds when dry
    assert T_in_floor(p, 22.0) == 22.0 + p.delta_cond        # condensation margin binds when humid


@pytest.mark.parametrize("T_dew", [15.0, 22.0])
@pytest.mark.parametrize("with_Tf", [False, True])
def test_round_trip(p, T_dew, with_Tf, seed=7):
    """q -> (m_dot, T_in) -> q is exact, and the physical pair respects every limit."""
    rng = np.random.default_rng(seed)
    for _ in range(300):
        T_w = rng.uniform(30.0, 60.0)
        # operational regime: T_f below its hard limit and below the loop temperature
        T_f = rng.uniform(16.0, min(p.T_f_max, T_w - p.delta_hx - 0.5)) if with_Tf else None
        lb, ub = q_ext_bounds(p, T_w, T_dew, T_f)
        if ub <= lb:
            continue
        q = rng.uniform(max(lb, 0.0), ub)
        m_dot, T_in = to_physical(p, q, T_w, T_dew, T_f)
        assert p.m_dot_min - 1e-12 <= m_dot <= p.m_dot_max + 1e-12
        assert T_in >= T_in_floor(p, T_dew) - 1e-9            # condensation margin
        assert T_in <= p.T_in_max + 1e-9
        if T_f is not None:
            assert T_in >= T_f + p.delta_hx - 1e-9            # passive CDU (D-005)
        assert from_physical(p, m_dot, T_in, T_w) == pytest.approx(q, abs=1e-6)


def test_out_of_set_rejected(p):
    T_w = 45.0
    _, ub = q_ext_bounds(p, T_w, 15.0)
    with pytest.raises(ValueError):
        to_physical(p, ub * 1.05, T_w, 15.0)


def test_bounds_affine_in_Tw(p):
    """Bounds are affine in T_w (required by the LP formulation)."""
    T_ws = np.array([30.0, 40.0, 50.0])
    lb, ub = q_ext_bounds(p, T_ws, 15.0)
    assert np.allclose(np.diff(lb, 2), 0.0)
    assert np.allclose(np.diff(ub, 2), 0.0)
