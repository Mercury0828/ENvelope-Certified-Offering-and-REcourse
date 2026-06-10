"""Phase-1 duration LP smoke tests (fast, coarse grid; full grid runs in the experiment)."""

import pytest

from encore.envelope.duration import (
    DurationCase, baseline_power, case_params, feasibility_lp, initial_state,
    max_sustainable_cut,
)
from encore.plant.params import load_params

T_WB = 22.0  # [est] shared across cases (D-007)


def case(scenario="S1", workload="nominal", init="nominal", weather="dry"):
    return DurationCase(
        scenario=scenario, workload=workload, init=init, weather=weather,
        T_dew=15.0 if weather == "dry" else 22.0, T_wb=T_WB,
    )


@pytest.fixture(scope="module")
def p():
    return load_params()


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3"])
def test_zero_cut_feasible(p, scenario):
    c = case(scenario)
    pc = case_params(p, c)
    assert feasibility_lp(pc, c, initial_state(pc, c), 0.0, 6)


def test_impossible_cut_infeasible(p):
    c = case("S1")
    base = baseline_power(p, c.T_wb)
    q_over = base["P_base_W"]   # cut more than total cooling power
    assert not feasibility_lp(p, c, initial_state(p, c), q_over, 1)


def test_frontier_monotone_in_d(p):
    c = case("S1")
    q = [max_sustainable_cut(p, c, d)["q_W"] for d in (5, 15, 30)]
    assert q[0] >= q[1] - 50 >= q[2] - 100   # within bisection tolerance


def test_precool_dominates(p):
    qn = max_sustainable_cut(p, case("S1", init="nominal"), 15)["q_W"]
    qp = max_sustainable_cut(p, case("S1", init="precooled"), 15)["q_W"]
    assert qp >= qn - 50


def test_humid_inside_dry(p):
    qd = max_sustainable_cut(p, case("S1", init="precooled", weather="dry"), 15)["q_W"]
    qh = max_sustainable_cut(p, case("S1", init="precooled", weather="humid"), 15)["q_W"]
    assert qh <= qd + 50


def test_s2_buys_duration_over_s1(p):
    """The facility loop's thermal mass must extend the frontier (the S2-vs-S1 story)."""
    q1 = max_sustainable_cut(p, case("S1"), 30)["q_W"]
    q2 = max_sustainable_cut(p, case("S2"), 30)["q_W"]
    assert q2 > q1
