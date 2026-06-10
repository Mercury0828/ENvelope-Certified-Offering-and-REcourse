"""Energy-balance closure tests (Phase 0 acceptance: <1%; LTI+ZOH should be ~exact)."""

import numpy as np
import pytest

from encore.plant.dynamics import simulate_affine, closed_loop_affine, steady_state
from encore.plant.params import load_params
from encore.plant.simulate import simulate


@pytest.fixture(scope="module")
def p():
    return load_params()


@pytest.mark.parametrize("n_states", [2, 3])
def test_steady_state_balance(p, n_states):
    """At the constructed steady state, constant inputs hold the state and the books close."""
    x0, u_ss = steady_state(p, n_states, p.Q_IT_nom, p.T_in_nom)
    N = 120  # 1 h at 30 s
    res = simulate(p, n_states, x0, np.tile(u_ss, (N, 1)), np.full(N, p.Q_IT_nom))
    assert np.allclose(res.X[-1], x0, atol=1e-6)
    assert res.energy["closure_frac"] < 1e-9


@pytest.mark.parametrize("n_states", [2, 3])
def test_transient_balance(p, n_states, seed=20260610):
    """Seeded random piecewise-constant inputs: closure stays at machine precision (<1%)."""
    rng = np.random.default_rng(seed)
    x0, u_ss = steady_state(p, n_states, p.Q_IT_nom, p.T_in_nom)
    N = 240
    U = u_ss * (1.0 + 0.3 * rng.uniform(-1, 1, size=(N, u_ss.size)))
    Q = p.Q_IT_nom * (1.0 + 0.2 * rng.uniform(-1, 1, size=N))
    res = simulate(p, n_states, x0, U, Q)
    assert res.energy["closure_frac"] < 1e-9   # well under the 1% acceptance bar


def test_closed_loop_balance_2state(p):
    """Step-response (physical-law) simulation: exact integrals close the books.

    Energy in = integral Q_IT; energy out = integral m cp (T_w - T_in); storage = C dT.
    """
    Q = 1.1 * p.Q_IT_nom  # +10% step
    A_cl, b = closed_loop_affine(p, 2, Q, p.m_dot_nom, T_in=p.T_in_nom)
    x0, _ = steady_state(p, 2, p.Q_IT_nom, p.T_in_nom)
    N = 240
    X, IX = simulate_affine(A_cl, b, x0, p.dt_sim, N)
    T_total = N * p.dt_sim
    E_in = Q * T_total
    mc = p.m_dot_nom * p.cp
    E_out = mc * (IX[:, 1].sum() - p.T_in_nom * T_total)   # integral of m cp (T_w - T_in)
    dE = p.C_j * (X[-1, 0] - X[0, 0]) + p.C_w * (X[-1, 1] - X[0, 1])
    closure = abs(E_in - E_out - dE) / E_in
    assert closure < 1e-9
