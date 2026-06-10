"""Discretization consistency (Phase 0 acceptance): 30 s simulation aggregated to 5 min
must match the 5-min control model when inputs are constant over each 5-min block."""

import numpy as np
import pytest

from encore.plant.dynamics import discrete_matrices, steady_state
from encore.plant.params import load_params
from encore.plant.simulate import simulate


@pytest.fixture(scope="module")
def p():
    return load_params()


@pytest.mark.parametrize("n_states", [2, 3])
def test_sim_aggregates_to_ctrl_model(p, n_states, seed=42):
    rng = np.random.default_rng(seed)
    sub = int(p.dt_ctrl / p.dt_sim)        # 10 substeps per control step
    N_ctrl = 12                            # one hour
    x0, u_ss = steady_state(p, n_states, p.Q_IT_nom, p.T_in_nom)
    U_ctrl = u_ss * (1.0 + 0.4 * rng.uniform(-1, 1, size=(N_ctrl, u_ss.size)))
    Q_ctrl = p.Q_IT_nom * (1.0 + 0.2 * rng.uniform(-1, 1, size=N_ctrl))

    # fine simulation at 30 s holding each control input for 10 substeps
    U_fine = np.repeat(U_ctrl, sub, axis=0)
    Q_fine = np.repeat(Q_ctrl, sub)
    res = simulate(p, n_states, x0, U_fine, Q_fine, dt=p.dt_sim)

    # coarse model at 5 min
    Ad, Bud, Bwd = discrete_matrices(p, n_states, p.dt_ctrl)
    x = x0.copy()
    for k in range(N_ctrl):
        x = Ad @ x + Bud @ U_ctrl[k] + Bwd @ np.array([Q_ctrl[k]])
        x_fine = res.X[(k + 1) * sub]
        assert np.allclose(x, x_fine, atol=1e-8), f"mismatch at control step {k}"


def test_zoh_limit_is_identity(p):
    Ad, Bud, _ = discrete_matrices(p, 2, 1e-6)
    assert np.allclose(Ad, np.eye(2), atol=1e-6)
    assert np.allclose(Bud, 0.0, atol=1e-9)
