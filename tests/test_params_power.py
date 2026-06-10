"""Parameter loading and power-map tests (guide 6.1 calibration guards)."""

import numpy as np
import pytest

from encore.plant import power
from encore.plant.params import load_params


@pytest.fixture(scope="module")
def p():
    return load_params()


def test_si_conversion_sane(p):
    assert p.P_IT_nom == 1e6
    assert 0.5e6 <= p.C_j <= 2e6            # guide 6.1 range
    assert 8e6 <= p.C_w <= 25e6             # guide 6.1 range
    assert p.m_dot_min < p.m_dot_nom <= p.m_dot_max
    assert p.dt_ctrl == 300.0 and p.dt_sim == 30.0


def test_stored_cop_matches_fit(p):
    """config/plant.yaml [fit] values must track fit_cop_coefficients (D-014)."""
    fit = power.fit_cop_coefficients(p)
    assert fit["cop_c0"] == pytest.approx(p.cop_c0, rel=1e-4)
    assert fit["cop_c1_per_K"] == pytest.approx(p.cop_c1, rel=1e-4)


def test_pump_pwa_upper_bounds_cubic(p):
    """Chord PWA of a convex function: >= cubic everywhere, equal at breakpoints."""
    m = np.linspace(p.m_dot_min, p.m_dot_max, 401)
    pwa = power.pump_power(p, m, pwa=True)
    exact = power.pump_power(p, m, pwa=False)
    assert np.all(pwa >= exact - 1e-9)
    bps = np.linspace(p.m_dot_min, p.m_dot_max, p.pwa_segments + 1)
    assert power.pump_power(p, bps) == pytest.approx(p.a_p * bps**3)


def test_cop_clamped(p):
    assert power.cop(p, T_supply=-100.0, T_wb=20.0) == p.cop_min
    assert power.cop(p, T_supply=200.0, T_wb=20.0) == p.cop_max


def test_gheni_trend_reproduced(p):
    """17->25 degC supply sweep cuts cooling power by tens of percent (40-75% band)."""
    g = p.gheni
    T_wb = g["T_wb_calib_C"]
    P17 = power.cooling_power(p, p.m_dot_nom, g["T_supply_lo_C"], p.Q_IT_nom, T_wb)
    P25 = power.cooling_power(p, p.m_dot_nom, g["T_supply_hi_C"], p.Q_IT_nom, T_wb)
    reduction = (P17 - P25) / P17
    assert 0.40 <= reduction <= 0.75
    assert reduction == pytest.approx(g["power_reduction_target"], abs=0.02)
