"""Phase-3 tests: tube margins, tightened envelope, quantile boxes, fallback, MPC."""

import numpy as np
import pytest

from encore.control.fallback import certified_max_q, certify, simulate_policy
from encore.control.mpc import mpc_controller
from encore.data.synthetic import Context, generate_history, hourly_record
from encore.envelope.geometry import max_q
from encore.envelope.reachability import EnvelopeSpec, build_lifted
from encore.plant.dynamics import steady_state
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import ConditionalBoxes
from encore.tighten.tube import build_tube, corner_disturbance, lqr_gain

SPEC = dict(n_states=2, T_dew=15.0, d_min=30.0)


@pytest.fixture(scope="module")
def p():
    return load_params()


@pytest.fixture(scope="module")
def x0(p):
    return steady_state(p, 2, p.Q_IT_nom, p.T_in_nom)[0]


def test_lqr_gain_stabilizes(p):
    from encore.plant.dynamics import discrete_matrices
    Ad, Bud, _ = discrete_matrices(p, 2, p.dt_ctrl)
    K = lqr_gain(p)
    eig = np.linalg.eigvals(Ad + Bud @ K)
    assert np.all(np.abs(eig) < 1.0)


def test_margins_monotone(p):
    # disturbance-driven part (e0 = 0) grows along the horizon and with the set
    t1 = build_tube(p, 2, 12, w_Q=50e3, w_D=1.0, E_budget=60e6, e0_K=0.0)
    t2 = build_tube(p, 2, 12, w_Q=100e3, w_D=1.0, E_budget=120e6, e0_K=0.0)
    t_box = build_tube(p, 2, 12, w_Q=50e3, w_D=1.0, e0_K=0.0)   # persistent (no budget)
    assert np.all(np.diff(t1.M[:, 0]) >= 0)
    assert np.all(t2.M >= t1.M)
    assert np.all(t_box.M >= t1.M - 1e-12)            # budget can only shrink margins
    assert t1.M[1:, 0].min() > 0
    # the e0 (warm-start) term adds margin everywhere and equals e0 at t=0
    t_e0 = build_tube(p, 2, 12, w_Q=50e3, w_D=1.0, E_budget=60e6, e0_K=1.5)
    assert np.all(t_e0.M >= t1.M)
    assert t_e0.M[0, 0] == pytest.approx(1.5)


def test_tightened_inside_nominal(p, x0):
    spec = EnvelopeSpec(**SPEC)
    F = max_q(build_lifted(p, spec), x0)
    tube_s = build_tube(p, 2, 12, w_Q=50e3, w_D=0.5, E_budget=40e6)
    tube_l = build_tube(p, 2, 12, w_Q=150e3, w_D=2.0, E_budget=150e6)
    Fs = certified_max_q(p, spec, tube_s, x0)
    Fl = certified_max_q(p, spec, tube_l, x0)
    assert Fl <= Fs <= F
    assert Fs > 0


def test_box_coverage_on_synthetic(p, seed=3):
    rng = np.random.default_rng(seed)
    feats, recs = generate_history(rng, p.Q_IT_nom, n=4000)
    cb = ConditionalBoxes(feats, recs, eps=0.1, k=200)
    c = Context(hour=14, burst_share=0.8, T_dew_fc=22.0, sigma_regime=1)
    box = cb.box(c.features())
    hits = sum(box.contains(*hourly_record(rng, c, p.Q_IT_nom)) for _ in range(2000))
    assert hits / 2000 >= 0.88              # >= 1 - eps within sampling tolerance
    # context value: a calm context's box should be tighter than the bursty one
    box_calm = cb.box(Context(hour=3, burst_share=0.05, T_dew_fc=15.0,
                              sigma_regime=0).features())
    assert box_calm.w_Q_hi < box.w_Q_hi


def test_fallback_certificate_survives_box_corner(p, x0):
    from encore.tighten.quantile_boxes import Box
    spec = EnvelopeSpec(**SPEC)
    box = Box(w_Q_hi=80e3, E_hi=70e6, w_D_hi=1.5)
    tube = build_tube(p, 2, 12, w_Q=box.w_Q_sym, w_D=box.w_D, E_budget=box.E_hi)
    q = 0.9 * certified_max_q(p, spec, tube, x0)
    cert = certify(p, spec, tube, x0, q)
    assert cert is not None
    # front-loaded extreme point of the polytopic W
    w = corner_disturbance(box, 12, p.dt_ctrl)
    out = simulate_policy(p, cert, w, dew_res=tube.w_D)
    assert out["T_viol_K"] <= 1e-6
    assert out["delivery_ok"]


def test_mpc_tracks_and_switches(p, x0):
    spec = EnvelopeSpec(**SPEC)
    tube = build_tube(p, 2, 12, w_Q=80e3, w_D=1.5, E_budget=70e6)
    q = 0.8 * certified_max_q(p, spec, tube, x0)
    cert = certify(p, spec, tube, x0, q)
    # benign disturbances: MPC stays feasible, delivers, no switch
    ctl, state = mpc_controller(p, cert)
    out = simulate_policy(p, cert, np.zeros(12), 0.0, controller=ctl)
    assert out["T_viol_K"] <= 1e-6 and out["delivery_ok"]
    assert not state["switched"]
    # absurd injected heat (far beyond box): the LP must eventually fail -> fallback
    ctl2, state2 = mpc_controller(p, cert)
    out2 = simulate_policy(p, cert, np.full(12, 6.0 * tube.w_Q), 3.0, controller=ctl2)
    assert state2["switched"]               # switch engaged
    assert out2["X"].shape[0] == 13         # hour completed under fallback
