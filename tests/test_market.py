"""Phase-4 tests: settlement reconciliation (guide §12), offering/envelope discipline,
baseline freezing."""

import numpy as np
import pytest

from encore.market.baseline import baseline_day
from encore.market.offering import make_offers
from encore.market.settlement import J_PER_MWH, settle_day
from encore.plant.params import load_params


@pytest.fixture(scope="module")
def p():
    return load_params()


def test_settlement_reconciles_exactly(seed=5):
    """Profit identity and the 5.3 shortfall formula re-derived independently."""
    rng = np.random.default_rng(seed)
    q = rng.uniform(0, 100e3, 24)
    r = (rng.uniform(size=24) < 0.3) * 0.5
    pi_cap = rng.uniform(1, 80, 24)
    P_base = np.full(288, 288e3)
    P = P_base - rng.uniform(-20e3, 120e3, 288)      # sometimes under-delivers
    pi_rt = rng.uniform(10, 200, 288)
    T_j = rng.uniform(60, 80, 288)

    led = settle_day(q, r, pi_cap, P, P_base, pi_rt, T_j,
                     gamma_mult=2.0, c_deg_per_Kh=2.0, T_thr=70.0)

    # independent recomputation
    rev = np.sum(pi_cap * q * 3600.0) / J_PER_MWH
    s = np.zeros(24)
    for h in range(24):
        delivered = np.sum((P_base[h * 12:(h + 1) * 12] - P[h * 12:(h + 1) * 12]) * 300.0)
        s[h] = max(r[h] * q[h] * 3600.0 - delivered, 0.0)
    pen = np.sum(2.0 * pi_cap * s / J_PER_MWH)
    rt = np.sum(P * pi_rt * 300.0) / J_PER_MWH
    deg = 2.0 * np.sum(np.maximum(T_j - 70.0, 0.0)) * 300.0 / 3600.0

    assert led["revenue_usd"] == pytest.approx(rev, abs=1e-9)
    assert led["penalty_usd"] == pytest.approx(pen, abs=1e-9)
    assert led["rt_cost_usd"] == pytest.approx(rt, abs=1e-9)
    assert led["degradation_usd"] == pytest.approx(deg, abs=1e-9)
    assert led["profit_usd"] == pytest.approx(rev - rt - pen - deg, abs=1e-9)
    assert np.allclose(led["shortfall_J"], s)


def test_no_offer_no_market_terms(p):
    base = baseline_day(p, 22.0)
    led = settle_day(np.zeros(24), np.zeros(24), np.full(24, 50.0),
                     base["P_base_W"], base["P_base_W"], np.full(288, 30.0),
                     np.full(288, 65.0))
    assert led["revenue_usd"] == 0.0 and led["penalty_usd"] == 0.0
    assert led["profit_usd"] == -led["rt_cost_usd"]   # deg zero below T_thr


def test_baseline_is_frozen_and_flat(p):
    base = baseline_day(p, 22.0)
    assert np.ptp(base["P_base_W"]) == 0.0            # D-035: flat under frozen COP
    assert base["P_base_scalar_W"] == pytest.approx(288.3e3, rel=1e-3)


def test_offers_respect_envelope_by_construction(p):
    ctx = [{"T_dew_fc": 15.0, "T_wb": 22.0, "pi_cap": 60.0,
            "pi_rt_event": 30.0, "pi_rt_recovery": 25.0}]
    plans = make_offers(p, ctx, "deterministic", n_grid=8)
    assert 0.0 <= plans[0].q_W <= plans[0].F_W
    assert plans[0].F_W > 0
