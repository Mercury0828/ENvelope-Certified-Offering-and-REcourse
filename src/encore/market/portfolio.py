"""B5 (ideal battery) and B6 (workload curtailment) baselines — guide §7's deliberately
simple comparison models. Both serve the same (q, d) product and settle on the same
prices; neither touches the thermal plant.

B5: energy/power-limited ideal storage. Offers q <= min(P_max, E/(r DH)) when the
capacity payment beats the expected cycling cost; delivers by discharging; recharges
the energy at the next hour's RT price with round-trip efficiency eta; pays an
annualized capex rent every day it exists (matched-capex-band comparison, C3-ii).

B6: curtail up to kappa_max of IT power at linear opportunity cost c_opp. Offers when
pi_cap > p_act-weighted expected opportunity cost.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from ..plant.params import REPO_ROOT

J_PER_MWH = 3.6e9


def load_market_config(path: str | Path = REPO_ROOT / "config" / "market.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def battery_day(cfg: dict, pi_cap: np.ndarray, rtm_hourly: np.ndarray,
                activations: np.ndarray, p_act: float, r_act: float = 0.5) -> dict:
    b = cfg["battery_B5"]
    P_max = b["P_max_kW"] * 1e3
    E_max = b["E_kWh"] * 3.6e6
    eta = b["eta_rt"]
    capex_day = (b["capex_usd_per_kWh"] * b["E_kWh"]
                 + b["capex_usd_per_kW"] * b["P_max_kW"]) * b["annualization_frac"] / 365.0

    q = np.zeros(24)
    rev = cost = 0.0
    for h in range(24):
        q_h = min(P_max, E_max / (r_act * 3600.0))
        # cycling cost per offered W if called: recharge delivered energy at next RT/eta
        cyc = p_act * r_act * 3600.0 * rtm_hourly[(h + 1) % 24] / eta / J_PER_MWH
        if pi_cap[h] * 3600.0 / J_PER_MWH > cyc:
            q[h] = q_h
            rev += pi_cap[h] * q_h * 3600.0 / J_PER_MWH
            if activations[h]:
                cost += q_h * r_act * 3600.0 * rtm_hourly[(h + 1) % 24] / eta / J_PER_MWH
    profit = rev - cost - capex_day
    return {"controller": "B5", "sum_q_kW": float(q.sum() / 1e3), "revenue_usd": rev,
            "rt_cost_usd": cost, "penalty_usd": 0.0, "degradation_usd": 0.0,
            "capex_usd": capex_day, "profit_usd": profit, "shortfall_kWh": 0.0,
            "max_T_j": np.nan, "mpc_switches": 0, "infeasible_starts": 0,
            "market_value_vs_B1_usd": profit}


def curtailment_day(cfg: dict, p, pi_cap: np.ndarray, activations: np.ndarray,
                    p_act: float, r_act: float = 0.5) -> dict:
    w = cfg["workload_B6"]
    q_max = w["kappa_max"] * p.P_IT_nom
    c_opp = w["c_opp_usd_per_MWh"]
    q = np.zeros(24)
    rev = cost = 0.0
    for h in range(24):
        # offer iff capacity payment beats expected opportunity cost
        if pi_cap[h] > p_act * r_act * c_opp:
            q[h] = q_max
            rev += pi_cap[h] * q_max * 3600.0 / J_PER_MWH
            if activations[h]:
                cost += c_opp * q_max * r_act * 3600.0 / J_PER_MWH
    profit = rev - cost
    return {"controller": "B6", "sum_q_kW": float(q.sum() / 1e3), "revenue_usd": rev,
            "rt_cost_usd": cost, "penalty_usd": 0.0, "degradation_usd": 0.0,
            "capex_usd": 0.0, "profit_usd": profit, "shortfall_kWh": 0.0,
            "max_T_j": np.nan, "mpc_switches": 0, "infeasible_starts": 0,
            "market_value_vs_B1_usd": profit}
