"""Phase 0 — step-response experiments (guide 6.1 sanity tests).

Closed-loop *physical* configuration (fixed m_dot/T_in; 3-state adds the passive CDU and
a proportional chiller-rejection law): step the IT heat load +10% and, separately, the
supply temperature -2 K, record trajectories, and report time constants from the
closed-loop eigenvalues. Acceptance bands (guide 6.1): junction lump fast relative to
the loop; loop 5-20 min; facility loop 20-60 min.

Writes plots (PDF+PNG), a time-constant table, a parameter table with source tags, and a
provenance manifest to results/phase0/.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from encore.plant.dynamics import (
    closed_loop_affine, simulate_affine, steady_state, time_constants,
)
from encore.plant.params import DEFAULT_CONFIG, load_params
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase0"
SEED = 20260610  # no randomness used; recorded for provenance convention


def parameter_table() -> pd.DataFrame:
    """Parse config/plant.yaml into a flat table with source tags from comments."""
    rows = []
    section = ""
    for line in DEFAULT_CONFIG.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\w[\w_]*:\s*(#.*)?$", line):
            section = line.split(":")[0]
            continue
        m = re.match(r"^\s+([\w_]+):\s*([-\d.eE]+)\s*#\s*(.*)$", line)
        if m:
            key, val, comment = m.groups()
            tag = re.search(r"\[(Gheni26|slides|est|fit)[^\]]*\]", comment)
            rows.append({
                "section": section, "parameter": key, "value": float(val),
                "source": tag.group(0) if tag else "(untagged)",
                "note": comment.strip(),
            })
    return pd.DataFrame(rows)


def run_step(p, n_states: int, kind: str, horizon_s: float):
    """Simulate one step experiment from the nominal steady state; return (t, X, info)."""
    x0, _ = steady_state(p, n_states, p.Q_IT_nom, p.T_in_nom)
    Q, T_in = p.Q_IT_nom, p.T_in_nom
    if kind == "QIT+10%":
        Q = 1.1 * p.Q_IT_nom
    elif kind == "Tin-2K":
        T_in = p.T_in_nom - 2.0
    else:
        raise ValueError(kind)

    if n_states == 2:
        A_cl, b = closed_loop_affine(p, 2, Q, p.m_dot_nom, T_in=T_in)
    else:
        # 3-state: passive CDU + proportional chiller law; the Tin-2K step is realized
        # by lowering the chiller's facility-temperature reference by 2 K.
        T_f_ref = (p.T_in_nom - p.delta_hx) - (p.T_in_nom - T_in)
        A_cl, b = closed_loop_affine(p, 3, Q, p.m_dot_nom, q_rej0=p.Q_IT_nom, T_f_ref=T_f_ref)

    n_steps = int(round(horizon_s / p.dt_sim))
    X, IX = simulate_affine(A_cl, b, x0, p.dt_sim, n_steps)
    t = np.arange(n_steps + 1) * p.dt_sim

    # energy bookkeeping (exact integrals)
    mc = p.m_dot_nom * p.cp
    T_total = n_steps * p.dt_sim
    if n_states == 2:
        E_out = mc * (IX[:, 1].sum() - T_in * T_total)
        C = np.array([p.C_j, p.C_w])
    else:
        q_rej_int = p.Q_IT_nom * T_total + p.k_rej * (IX[:, 2].sum() - T_f_ref * T_total)
        E_out = q_rej_int
        C = np.array([p.C_j, p.C_w, p.C_f])
    E_in = Q * T_total
    closure = abs(E_in - E_out - C @ (X[-1] - X[0])) / E_in

    taus = time_constants(A_cl)
    return t, X, {"taus_s": taus, "closure": closure, "x0": x0, "kind": kind}


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()

    state_names = {2: ["T_j", "T_w"], 3: ["T_j", "T_w", "T_f"]}
    tau_rows, closure_rows = [], []

    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), sharex="col")
    for i, n_states in enumerate((2, 3)):
        horizon = 3600.0 if n_states == 2 else 4.0 * 3600.0
        for j, kind in enumerate(("QIT+10%", "Tin-2K")):
            t, X, info = run_step(p, n_states, kind, horizon)
            ax = axes[i, j]
            for k, name in enumerate(state_names[n_states]):
                ax.plot(t / 60.0, X[:, k], label=f"${name[0]}_{{{name[2]}}}$")
            ax.set_title(f"{n_states}-state, step {kind}")
            ax.set_ylabel("temperature [°C]")
            if i == 1:
                ax.set_xlabel("time [min]")
            ax.legend(loc="best")
            closure_rows.append({"model": f"{n_states}-state", "step": kind,
                                 "energy_closure_frac": info["closure"]})
            if j == 0:
                taus = info["taus_s"] / 60.0
                row = {"model": f"{n_states}-state",
                       "tau_junction_min": taus[0], "tau_loop_min": taus[1]}
                if n_states == 3:
                    row["tau_facility_min"] = taus[2]
                tau_rows.append(row)
    savefig(fig, OUT / "step_responses")
    plt.close(fig)

    taus = pd.DataFrame(tau_rows)
    closures = pd.DataFrame(closure_rows)
    taus.to_csv(OUT / "time_constants.csv", index=False)
    closures.to_csv(OUT / "energy_closure.csv", index=False)

    par = parameter_table()
    par.to_csv(OUT / "parameter_table.csv", index=False)
    (OUT / "parameter_table.md").write_text(
        "# Plant parameter table (with source tags)\n\n" + par.to_markdown(index=False) + "\n",
        encoding="utf-8")

    # ---- acceptance assertions (guide 6.1 bands) ----
    for r in tau_rows:
        assert r["tau_junction_min"] < 1.0, f"junction lump not fast: {r}"
        assert 5.0 <= r["tau_loop_min"] <= 20.0, f"loop tau out of band: {r}"
        if "tau_facility_min" in r:
            assert 20.0 <= r["tau_facility_min"] <= 60.0, f"facility tau out of band: {r}"
        assert r["tau_junction_min"] < 0.2 * r["tau_loop_min"], "junction not fast vs loop"
    assert (closures["energy_closure_frac"] < 0.01).all(), "energy balance closure >= 1%"

    write_manifest(OUT / "provenance_step_response.json", seed=SEED,
                   extra={"experiment": "phase0_step_response"})
    print("time constants [min]:")
    print(taus.to_string(index=False))
    print("\nenergy closure:")
    print(closures.to_string(index=False))
    print("\nall Phase-0 step-response assertions passed.")


if __name__ == "__main__":
    main()
