"""Phase-2 envelope geometry tests: lifted-system consistency, monotonicity,
projection exactness, virtual-battery closed forms, readiness iteration."""

import numpy as np
import pytest

from encore.envelope.duration import DurationCase, max_sustainable_cut
from encore.envelope.geometry import (
    is_member, max_q, poly_contains, poly_halfspaces, project_slice,
)
from encore.envelope.reachability import EnvelopeSpec, build_lifted
from encore.envelope.readiness import readiness_iteration
from encore.envelope.virtual_battery import vb_frontier
from encore.plant.dynamics import steady_state
from encore.plant.params import load_params


@pytest.fixture(scope="module")
def p():
    return load_params()


@pytest.fixture(scope="module")
def x0(p):
    return steady_state(p, 2, p.Q_IT_nom, p.T_in_nom)[0]


def event_spec(n_states, d, T_dew=15.0):
    """Event-only sustained spec — must reproduce the Phase-1 frontier."""
    return EnvelopeSpec(n_states=n_states, T_dew=T_dew, d_min=d,
                        horizon_steps=int(d / 5), r=1.0, delivery="sustained")


@pytest.mark.parametrize("scenario,n_states", [("S1", 2), ("S2", 3)])
def test_lifted_reproduces_phase1(p, scenario, n_states):
    case = DurationCase(scenario=scenario, workload="nominal", init="nominal",
                        weather="dry", T_dew=15.0, T_wb=22.0)
    q1 = max_sustainable_cut(p, case, 30, tol_W=20.0)["q_W"]
    x0s, _ = steady_state(p, n_states, p.Q_IT_nom, p.T_in_nom)
    F = max_q(build_lifted(p, event_spec(n_states, 30)), x0s)
    assert F == pytest.approx(q1, abs=60.0)   # within bisection tolerance


def test_membership_monotone_in_q(p, x0):
    L = build_lifted(p, EnvelopeSpec(n_states=2, T_dew=15.0, d_min=30.0))
    F = max_q(L, x0)
    qs = np.linspace(0, L.q_ub, 40)
    members = np.array([is_member(L, x0, q) for q in qs])
    flips = np.diff(members.astype(int))
    assert (flips <= 0).all(), "membership not monotone in q"
    assert members[qs <= F - 1.0].all() and not members[qs >= F + 1.0].any()


def test_F_monotone_in_Tdew(p, x0):
    Fs = [max_q(build_lifted(p, EnvelopeSpec(n_states=2, T_dew=td, d_min=30.0)), x0)
          for td in (10.0, 16.0, 18.0, 20.0, 22.0, 24.0)]
    assert np.all(np.diff(Fs) <= 1.0), f"F not non-increasing in T_dew: {Fs}"
    assert Fs[0] == pytest.approx(Fs[1], abs=1.0)   # floor saturates below 16 degC


def test_cumulative_at_least_sustained(p, x0):
    spec_c = EnvelopeSpec(n_states=2, T_dew=15.0, d_min=30.0, delivery="cumulative")
    spec_s = EnvelopeSpec(n_states=2, T_dew=15.0, d_min=30.0, delivery="sustained")
    assert max_q(build_lifted(p, spec_c), x0) >= max_q(build_lifted(p, spec_s), x0) - 1.0


def test_slice_projection_matches_lp(p, x0, seed=11):
    """Exact-projection check: polygon membership == LP membership at on-grid q."""
    rng = np.random.default_rng(seed)
    L = build_lifted(p, EnvelopeSpec(n_states=2, T_dew=15.0, d_min=30.0))
    for q in (30e3, 80e3, 150e3):
        hs = poly_halfspaces(project_slice(L, q))
        for _ in range(25):
            x = np.array([rng.uniform(30, 92), rng.uniform(15, 56)])
            margin_ok = True
            if hs is not None:
                A, b = hs
                margin_ok = np.abs(A @ x - b).min() > 1e-3   # skip knife-edge points
            if margin_ok:
                assert poly_contains(hs, x) == is_member(L, x, q)


def test_vb_closed_form_tracks_lp(p, x0):
    for d in (15, 30, 60):
        F = max_q(build_lifted(p, event_spec(2, d)), x0)
        q_vb = vb_frontier(p, 15.0, 22.0, d, x0[1])
        assert q_vb == pytest.approx(F, rel=0.10)


def test_readiness_one_step_nonempty_fixed_point_empty(p):
    """D-048: the STARTABLE set R1 is a healthy polygon, but the infinite-horizon
    fixed point is EMPTY under whole-hour settlement (consecutive full-depth delivery
    is thermodynamically impossible) — which is why commitments are adjacency-pruned."""
    from encore.envelope.geometry import poly_area, poly_halfspaces as hsf
    spec = EnvelopeSpec(n_states=2, T_dew=15.0, d_min=30.0)
    one = readiness_iteration(p, spec, q=50e3, max_iter=1, tol_K=0.05)
    R1 = one["fixed_point"]
    assert R1.shape[0] >= 3 and poly_area(R1) > 100.0      # startable set is large
    # monotone: R1 inside R0 (the safety box)
    hs = hsf(one["polygons"][0])
    A, b = hs
    assert (A @ R1.T - b[:, None]).max() < 0.05
    deep = readiness_iteration(p, spec, q=50e3, max_iter=10, tol_K=0.05)
    assert not deep["converged"] and deep["fixed_point"].shape[0] == 0
