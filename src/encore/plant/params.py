"""Config-driven plant parameters (guide 6.1, 12).

All values live in config/plant.yaml with source tags; this module converts them to SI
(W, J/K, s, degC — see DESIGN_DECISIONS D-015) once at load time. Code never hardcodes
plant numbers.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO_ROOT / "config" / "plant.yaml"


@dataclass(frozen=True)
class PlantParams:
    """Plant parameters in SI units (W, J/K, kg/s, s, degC)."""

    # reference
    P_IT_nom: float          # W

    # thermal capacitances / conductances
    C_j: float               # J/K
    C_w: float               # J/K
    C_f: float               # J/K
    C_tank: float            # J/K (S3 sensitivity only)
    h_jw: float              # W/K
    delta_hx: float          # K

    # coolant / flow
    cp: float                # J/(kg K)
    m_dot_nom: float         # kg/s
    m_dot_min: float         # kg/s
    m_dot_max: float         # kg/s

    # limits
    T_max: float             # degC
    delta_cond: float        # K
    T_in_min: float          # degC
    T_in_max: float          # degC
    T_f_max: float           # degC
    q_ext_ramp: float        # W/s
    q_rej_max: float         # W

    # operating point
    T_in_nom: float          # degC
    Q_IT_nom: float          # W

    # power map
    a_p: float               # W/(kg/s)^3
    pwa_segments: int
    cop_c0: float
    cop_c1: float            # 1/K
    cop_min: float
    cop_max: float
    gheni: dict              # calibration anchor block (raw, SI-free scalars in degC/frac)

    # step-response characterization law
    k_rej: float             # W/K

    # discretization
    dt_sim: float            # s
    dt_ctrl: float           # s


def load_params(path: str | Path = DEFAULT_CONFIG) -> PlantParams:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    th = raw["thermal"]
    co = raw["coolant"]
    li = raw["limits"]
    op = raw["operating_point"]
    pm = raw["power_map"]

    m_dot_nom = float(co["m_dot_nom_kg_s"])
    return PlantParams(
        P_IT_nom=float(raw["reference"]["P_IT_nominal_kW"]) * 1e3,
        C_j=float(th["C_j_MJ_per_K"]) * 1e6,
        C_w=float(th["C_w_MJ_per_K"]) * 1e6,
        C_f=float(th["C_f_MJ_per_K"]) * 1e6,
        C_tank=float(th["C_tank_MJ_per_K"]) * 1e6,
        h_jw=float(th["h_jw_kW_per_K"]) * 1e3,
        delta_hx=float(th["delta_hx_K"]),
        cp=float(co["cp_J_per_kgK"]),
        m_dot_nom=m_dot_nom,
        m_dot_min=float(co["m_dot_frac_min"]) * m_dot_nom,
        m_dot_max=float(co["m_dot_frac_max"]) * m_dot_nom,
        T_max=float(li["T_max_C"]),
        delta_cond=float(li["delta_cond_K"]),
        T_in_min=float(li["T_in_min_C"]),
        T_in_max=float(li["T_in_max_C"]),
        T_f_max=float(li["T_f_max_C"]),
        q_ext_ramp=float(li["q_ext_ramp_kW_per_min"]) * 1e3 / 60.0,
        q_rej_max=float(li["q_rej_max_kW"]) * 1e3,
        T_in_nom=float(op["T_in_nom_C"]),
        Q_IT_nom=float(op["Q_IT_nom_kW"]) * 1e3,
        a_p=float(pm["pump_a_p_W_per_kgps3"]),
        pwa_segments=int(pm["pump_pwa_n_segments"]),
        cop_c0=float(pm["cop_c0"]),
        cop_c1=float(pm["cop_c1_per_K"]),
        cop_min=float(pm["cop_min"]),
        cop_max=float(pm["cop_max"]),
        gheni=dict(pm["gheni_anchor"]),
        k_rej=float(raw["step_response"]["k_rej_kW_per_K"]) * 1e3,
        dt_sim=float(raw["discretization"]["dt_sim_s"]),
        dt_ctrl=float(raw["discretization"]["dt_ctrl_s"]),
    )


def with_extra_facility_mass(p: PlantParams, extra_J_per_K: float) -> PlantParams:
    """Return params with C_f increased (S3 buffer-tank sensitivity ONLY — guide Line-C caution)."""
    return dataclasses.replace(p, C_f=p.C_f + extra_J_per_K)


def config_hash(path: str | Path = DEFAULT_CONFIG) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
