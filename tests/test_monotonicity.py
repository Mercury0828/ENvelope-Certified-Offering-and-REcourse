"""Monotonicity smoke checks (Phase 0 acceptance)."""

import numpy as np
import pytest

from encore.plant.dynamics import steady_state
from encore.plant.params import load_params
from encore.plant.simulate import simulate


@pytest.fixture(scope="module")
def p():
    return load_params()


@pytest.mark.parametrize("n_states", [2, 3])
def test_more_heat_higher_Tj(p, n_states):
    """Higher IT load -> strictly higher steady-state junction temperature."""
    loads = np.array([0.6, 0.8, 1.0, 1.2]) * p.Q_IT_nom
    Tj = [steady_state(p, n_states, Q, p.T_in_nom)[0][0] for Q in loads]
    assert np.all(np.diff(Tj) > 0)


@pytest.mark.parametrize("n_states", [2, 3])
def test_more_extraction_lower_Tw(p, n_states):
    """Higher constant q_ext -> componentwise lower trajectory of T_w (and T_j)."""
    x0, u_ss = steady_state(p, n_states, p.Q_IT_nom, p.T_in_nom)
    N = 60
    Q = np.full(N, p.Q_IT_nom)
    u_lo = np.tile(u_ss, (N, 1))
    u_hi = u_lo.copy()
    u_hi[:, 0] += 0.1 * p.Q_IT_nom     # extract 100 kW more (rejection unchanged)
    lo = simulate(p, n_states, x0, u_lo, Q)
    hi = simulate(p, n_states, x0, u_hi, Q)
    assert np.all(hi.X[1:, 1] < lo.X[1:, 1])     # T_w strictly lower
    assert np.all(hi.X[1:, 0] <= lo.X[1:, 0] + 1e-12)


def test_warmer_supply_higher_Tj(p):
    """Raising supply temperature shifts the whole steady profile up."""
    x_cool, _ = steady_state(p, 2, p.Q_IT_nom, 20.0)
    x_warm, _ = steady_state(p, 2, p.Q_IT_nom, 30.0)
    assert np.all(x_warm > x_cool)
