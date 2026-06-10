"""Phase 1 — duration accounting (GO/NO-GO gate #1, guide Section 11).

For each duration d in {5,10,15,20,30,45,60} min, bisection on q around an open-loop
feasibility LP (5-min model) gives the maximum sustainable cooling-power cut q*(d) such
that T_j <= T_max and T_in >= T_dew + delta_cond hold throughout.

Grid: scenarios S1 (coolant loop only, 2-state), S2 (+facility loop, 3-state),
S3 (S2 + small buffer tank — SENSITIVITY ONLY, Line-C adjacent, not the main story)
x workload {nominal, burst} x initial state {nominal, precooled} x T_dew {15 dry, 22 humid}.
T_wb fixed at 22 degC across cases (D-007) so humidity enters only via the condensation
floor and the required orderings are structurally meaningful.

Programmatic acceptance assertions (guide):
  (1) frontier monotone non-increasing in d for every case;
  (2) precooled dominates nominal start; humid weakly inside dry;
  (3) S3 present but labeled sensitivity-only.

Outputs to results/phase1/: q-d frontier plots (panel per scenario), frontier.csv,
key_numbers.json, provenance JSON. DURATION_MEMO.md is authored from these numbers.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import itertools
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from encore.envelope.duration import DurationCase, baseline_power, max_sustainable_cut
from encore.plant.params import load_params
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase1"
SEED = 20260610          # deterministic grid; recorded by convention
DURATIONS = [5, 10, 15, 20, 30, 45, 60]
T_WB = 22.0              # [est] shared across cases (D-007)
T_DEW = {"dry": 15.0, "humid": 22.0}
TOL_W = 20.0             # bisection tolerance
SLACK = 3 * TOL_W        # assertion slack for bisection noise


def run_grid(p) -> pd.DataFrame:
    rows = []
    grid = list(itertools.product(
        ("S1", "S2", "S3"), ("nominal", "burst"), ("nominal", "precooled"), ("dry", "humid")))
    for scenario, workload, init, weather in grid:
        case = DurationCase(scenario=scenario, workload=workload, init=init,
                            weather=weather, T_dew=T_DEW[weather], T_wb=T_WB)
        for d in DURATIONS:
            res = max_sustainable_cut(p, case, d, tol_W=TOL_W)
            rows.append({
                "scenario": scenario, "workload": workload, "init": init,
                "weather": weather, "d_min": d,
                "q_kW": res["q_W"] / 1e3,
                "q_pct_of_base": 100.0 * res["q_frac_of_base"],
                "P_base_kW": res["P_base_W"] / 1e3,
                "cop_ref": res["cop_ref"],
                "peak_T_j_C": res.get("peak_T_j", np.nan),
                "peak_T_f_C": res.get("peak_T_f", np.nan),
            })
        print(f"  done {case.label}")
    return pd.DataFrame(rows)


def check_acceptance(df: pd.DataFrame) -> dict:
    """Programmatic Phase-1 acceptance assertions; returns a summary dict."""
    keys = ["scenario", "workload", "init", "weather"]
    slack_kw = SLACK / 1e3

    # (1) monotone non-increasing frontier in d
    for _, grp in df.groupby(keys):
        q = grp.sort_values("d_min")["q_kW"].to_numpy()
        assert np.all(np.diff(q) <= slack_kw), f"frontier not monotone: {grp[keys].iloc[0].to_dict()}"

    # (2a) precooled dominates nominal start
    piv = df.pivot_table(index=["scenario", "workload", "weather", "d_min"],
                         columns="init", values="q_kW")
    bad = piv[piv["precooled"] < piv["nominal"] - slack_kw]
    assert bad.empty, f"precool dominance violated:\n{bad}"

    # (2b) humid weakly inside dry
    piv = df.pivot_table(index=["scenario", "workload", "init", "d_min"],
                         columns="weather", values="q_kW")
    bad = piv[piv["humid"] > piv["dry"] + slack_kw]
    assert bad.empty, f"humid-inside-dry violated:\n{bad}"

    # (2c) burst weakly inside nominal workload (extra sanity, same logic)
    piv = df.pivot_table(index=["scenario", "init", "weather", "d_min"],
                         columns="workload", values="q_kW")
    bad = piv[piv["burst"] > piv["nominal"] + slack_kw]
    assert bad.empty, f"burst-inside-nominal violated:\n{bad}"

    return {"monotone": True, "precool_dominates": True,
            "humid_inside_dry": True, "burst_inside_nominal": True}


def plot_frontiers(df: pd.DataFrame):
    titles = {
        "S1": "S1 — coolant loop only (2-state)",
        "S2": "S2 — + facility loop (3-state)",
        "S3": "S3 — + buffer tank\n(sensitivity only — Line-C adjacent, not the main story)",
    }
    color = {"dry": "C0", "humid": "C1"}
    ls = {"nominal": "-", "precooled": "--"}
    marker = {"nominal": "o", "burst": "s"}

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2), sharey=True)
    for ax, scen in zip(axes, ("S1", "S2", "S3")):
        sub = df[df["scenario"] == scen]
        for (wl, init, wx), grp in sub.groupby(["workload", "init", "weather"]):
            grp = grp.sort_values("d_min")
            ax.plot(grp["d_min"], grp["q_pct_of_base"],
                    color=color[wx], linestyle=ls[init], marker=marker[wl],
                    label=f"{wx}, {init}, {wl}")
        ax.set_title(titles[scen], fontsize=9.5)
        ax.set_xlabel("duration $d$ [min]")
        ax.set_xticks(DURATIONS)
    axes[0].set_ylabel("max sustainable cut $q$ [% of baseline $P_{cool}$]")
    axes[0].legend(title="weather, init, workload", fontsize=6.5, title_fontsize=7)
    fig.suptitle("Phase 1 — q–d frontier: max sustainable cooling-power cut vs duration", y=1.02)
    fig.tight_layout()
    savefig(fig, OUT / "q_d_frontier")
    plt.close(fig)


def key_numbers(df: pd.DataFrame, base: dict) -> dict:
    def q(scen, d, init="nominal", wl="nominal", wx="dry", col="q_pct_of_base"):
        m = df[(df.scenario == scen) & (df.d_min == d) & (df.init == init)
               & (df.workload == wl) & (df.weather == wx)]
        return float(m[col].iloc[0])

    # gate: most conservative standard S2 case at d=30 (burst workload, nominal start, humid)
    s2_worst_30 = q("S2", 30, init="nominal", wl="burst", wx="humid")
    go = s2_worst_30 >= 15.0
    return {
        "P_base_kW": base["P_base_W"] / 1e3,
        "P_pump_kW": base["P_pump_W"] / 1e3,
        "cop_ref": base["cop_ref"],
        "q30_S1_nominal_dry_pct": q("S1", 30),
        "q30_S1_precooled_dry_pct": q("S1", 30, init="precooled"),
        "q30_S2_nominal_dry_pct": q("S2", 30),
        "q30_S2_precooled_dry_pct": q("S2", 30, init="precooled"),
        "q30_S2_worst_pct_burst_humid_nominalstart": s2_worst_30,
        "q30_S1_nominal_dry_kW": q("S1", 30, col="q_kW"),
        "q30_S2_nominal_dry_kW": q("S2", 30, col="q_kW"),
        "precool_value_S1_d30_pct_pts": q("S1", 30, init="precooled") - q("S1", 30),
        "precool_value_S1_d30_humid_pct_pts":
            q("S1", 30, init="precooled", wx="humid") - q("S1", 30, wx="humid"),
        "humid_shrink_S1_precooled_d30_pct_pts":
            q("S1", 30, init="precooled") - q("S1", 30, init="precooled", wx="humid"),
        "gate_rule": "GO if S2 sustains >=15-20% of baseline cooling power for d=30 min",
        "gate_case": "S2, burst workload, nominal start, humid (most conservative standard case)",
        "gate_verdict": "GO" if go else "NO-GO",
    }


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    base = baseline_power(p, T_WB)
    print(f"baseline: P_base = {base['P_base_W']/1e3:.1f} kW "
          f"(pump {base['P_pump_W']/1e3:.1f} kW, COP_ref {base['cop_ref']:.3f})")

    df = run_grid(p)
    df.to_csv(OUT / "frontier.csv", index=False)

    checks = check_acceptance(df)
    print("acceptance assertions:", checks)

    plot_frontiers(df)
    nums = key_numbers(df, base)
    (OUT / "key_numbers.json").write_text(json.dumps(nums, indent=2), encoding="utf-8")
    write_manifest(OUT / "provenance_duration.json", seed=SEED,
                   extra={"experiment": "phase1_duration", "T_wb": T_WB,
                          "T_dew": T_DEW, "durations_min": DURATIONS,
                          "bisection_tol_W": TOL_W, "acceptance": checks})

    print(json.dumps(nums, indent=2))
    print("\nPhase-1 grid complete; all programmatic assertions passed.")


if __name__ == "__main__":
    main()
