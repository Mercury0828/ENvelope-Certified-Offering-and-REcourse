"""Phase 2 — envelope geometry artifacts (guide 6.3 / Section 11).

Produces:
1. Envelope slice family: exact x_0-plane polygons at several offers q, dry vs humid
   (the "weather-coupled deliverable set" picture).
2. F(x_0, T_dew) curves for d in {15, 30, 60} from nominal and pre-cooled states —
   asserted monotone non-increasing in T_dew (the envelope-shrink acceptance item).
3. Readiness iteration R_k at committed offers (the terminal-set object of guide 6.3),
   with convergence diagnostics and the consecutive-hour deliverability check.
4. Virtual-battery closed forms vs LP frontiers (Thm-1 consistency evidence): table +
   overlay figure, 2-state and 3-state, dry and humid, nominal and pre-cooled starts.

All figures PDF+PNG with the shared style; tables CSV; provenance JSON.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull

from encore.envelope.geometry import max_q, poly_area, project_slice
from encore.envelope.readiness import readiness_iteration
from encore.envelope.reachability import EnvelopeSpec, build_lifted
from encore.envelope.virtual_battery import vb_frontier, vb_params
from encore.plant.dynamics import steady_state
from encore.plant.params import load_params
from encore.plant.virtual_input import T_in_floor
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase2"
SEED = 20260610
T_WB = 22.0


def ordered(verts):
    if verts.shape[0] < 3:
        return verts
    hull = ConvexHull(verts)
    return verts[hull.vertices]


def fig_slices(p):
    qs_kW = [25.0, 75.0, 150.0, 220.0]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), sharex=True, sharey=True)
    for ax, T_dew in zip(axes, (15.0, 22.0)):
        L = build_lifted(p, EnvelopeSpec(n_states=2, T_dew=T_dew, d_min=30.0))
        for i, qk in enumerate(qs_kW):
            v = ordered(project_slice(L, qk * 1e3))
            if v.shape[0] >= 3:
                poly = plt.Polygon(v[:, ::-1], closed=True, fill=True,
                                   facecolor=f"C{i}", alpha=0.25, edgecolor=f"C{i}",
                                   label=f"q = {qk:.0f} kW")
                ax.add_patch(poly)
        x0n, _ = steady_state(p, 2, p.Q_IT_nom, p.T_in_nom)
        x0p, _ = steady_state(p, 2, p.Q_IT_nom, T_in_floor(p, T_dew))
        ax.plot(*x0n[::-1], "k*", ms=10, label="nominal state")
        ax.plot(*x0p[::-1], "kv", ms=7, label="pre-cooled state")
        ax.set_xlim(12, 58); ax.set_ylim(25, 92)
        ax.set_xlabel("loop temperature $T_w$ [°C]")
        ax.set_title(f"$T_{{dew}}$ = {T_dew:.0f} °C "
                     f"({'dry' if T_dew < 20 else 'humid'})")
    axes[0].set_ylabel("junction temperature $T_j$ [°C]")
    axes[0].legend(loc="lower right", fontsize=7)
    fig.suptitle("Deliverable-set slices in the state plane (d = 30 min, 1-h horizon)")
    fig.tight_layout()
    savefig(fig, OUT / "envelope_slices")
    plt.close(fig)


def fig_dew_shrink(p):
    dews = np.linspace(10.0, 24.0, 15)
    rows = []
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.8))
    for d, color in zip((15.0, 30.0, 60.0), ("C0", "C1", "C2")):
        Fn, Fp = [], []
        for td in dews:
            L = build_lifted(p, EnvelopeSpec(n_states=2, T_dew=td, d_min=d))
            x0n, _ = steady_state(p, 2, p.Q_IT_nom, p.T_in_nom)
            x0p, _ = steady_state(p, 2, p.Q_IT_nom, T_in_floor(p, td))
            Fn.append(max_q(L, x0n) / 1e3)
            Fp.append(max_q(L, x0p) / 1e3)
            rows.append({"d_min": d, "T_dew": td, "F_nominal_kW": Fn[-1],
                         "F_precooled_kW": Fp[-1]})
        assert np.all(np.diff(Fn) <= 1e-3), f"F(nominal) not non-increasing, d={d}"
        assert np.all(np.diff(Fp) <= 1e-3), f"F(precooled) not non-increasing, d={d}"
        ax1.plot(dews, Fn, color=color, marker="o", ms=3, label=f"d = {d:.0f} min")
        ax2.plot(dews, Fp, color=color, marker="o", ms=3, label=f"d = {d:.0f} min")
    for ax, title in ((ax1, "from nominal state"), (ax2, "from pre-cooled state")):
        ax.axvline(p.T_in_min - p.delta_cond, ls=":", color="gray", lw=1)
        ax.annotate("floor saturates", xy=(p.T_in_min - p.delta_cond, 0.95),
                    xycoords=("data", "axes fraction"), fontsize=7, rotation=90,
                    ha="right", va="top", color="gray")
        ax.set_xlabel("dew point $T_{dew}$ [°C]")
        ax.set_title(title)
        ax.legend()
    ax1.set_ylabel("max certifiable offer $F(x_0, c)$ [kW]")
    fig.suptitle("Envelope shrinks monotonically with dew point (2-state, 1-h horizon)")
    fig.tight_layout()
    savefig(fig, OUT / "envelope_vs_dewpoint")
    plt.close(fig)
    pd.DataFrame(rows).to_csv(OUT / "envelope_vs_dewpoint.csv", index=False)
    return rows


def fig_readiness(p):
    info = {}
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), sharex=True, sharey=True)
    x0n, _ = steady_state(p, 2, p.Q_IT_nom, p.T_in_nom)
    for ax, q_kW in zip(axes, (50.0, 65.0)):
        spec = EnvelopeSpec(n_states=2, T_dew=15.0, d_min=30.0)
        out = readiness_iteration(p, spec, q=q_kW * 1e3, max_iter=12, tol_K=0.05)
        for k, v in enumerate(out["polygons"]):
            v = ordered(v)
            if v.shape[0] >= 3:
                ax.add_patch(plt.Polygon(v[:, ::-1], closed=True, fill=False,
                                         edgecolor=plt.cm.viridis(k / max(1, len(out["polygons"]) - 1)),
                                         lw=1.2))
        ax.plot(*x0n[::-1], "k*", ms=10)
        Rinf = out["fixed_point"]
        from encore.envelope.geometry import poly_contains, poly_halfspaces
        inside = poly_contains(poly_halfspaces(Rinf), x0n)
        ax.set_title(f"q = {q_kW:.0f} kW: {len(out['polygons']) - 1} iters, "
                     f"converged = {out['converged']}\nnominal state ready: {inside}")
        ax.set_xlabel("$T_w$ [°C]")
        info[f"q{q_kW:.0f}"] = {"iters": len(out["polygons"]) - 1,
                                "converged": out["converged"],
                                "gaps_K": out["gaps"],
                                "area_K2": poly_area(Rinf),
                                "nominal_ready": bool(inside)}
        ax.set_xlim(12, 58); ax.set_ylim(25, 92)
    axes[0].set_ylabel("$T_j$ [°C]")
    fig.suptitle("Readiness fixed-point iteration $R_k$ (d = 30 min, dry; viridis dark→light = k)")
    fig.tight_layout()
    savefig(fig, OUT / "readiness_sets")
    plt.close(fig)
    return info


def vb_consistency(p):
    rows = []
    for n_states in (2, 3):
        for T_dew, wx in ((15.0, "dry"), (22.0, "humid")):
            for init in ("nominal", "precooled"):
                T_in0 = p.T_in_nom if init == "nominal" else T_in_floor(p, T_dew)
                x0, _ = steady_state(p, n_states, p.Q_IT_nom, T_in0)
                for d in (10.0, 15.0, 20.0, 30.0, 45.0, 60.0):
                    spec = EnvelopeSpec(n_states=n_states, T_dew=T_dew, d_min=d,
                                        horizon_steps=int(d / 5), r=1.0,
                                        delivery="sustained")
                    F = max_q(build_lifted(p, spec), x0)
                    q_vb = vb_frontier(p, T_dew, T_WB, d, x0[1], n_states=n_states,
                                       T_f0=x0[2] if n_states == 3 else None)
                    rows.append({"model": f"{n_states}-state", "weather": wx,
                                 "init": init, "d_min": d, "F_lp_kW": F / 1e3,
                                 "q_vb_kW": q_vb / 1e3,
                                 "rel_err": (q_vb - F) / F if F > 0 else np.nan})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "vb_consistency.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.9), sharey=True)
    for ax, model in zip(axes, ("2-state", "3-state")):
        sub = df[(df.model == model) & (df.init == "nominal")]
        for wx, color in (("dry", "C0"), ("humid", "C1")):
            s = sub[sub.weather == wx].sort_values("d_min")
            ax.plot(s.d_min, s.F_lp_kW, color=color, marker="o", label=f"LP, {wx}")
            ax.plot(s.d_min, s.q_vb_kW, color=color, ls="--", marker="x",
                    label=f"VB closed form, {wx}")
        ax.set_xlabel("duration $d$ [min]")
        ax.set_title(f"{model} (nominal start)")
        ax.legend(fontsize=7)
    axes[0].set_ylabel("max sustainable cut [kW]")
    fig.suptitle("Virtual-battery closed form vs LP frontier (event-only, sustained)")
    fig.tight_layout()
    savefig(fig, OUT / "vb_vs_lp_frontier")
    plt.close(fig)
    return df


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()

    fig_slices(p)
    print("slices figure done")
    fig_dew_shrink(p)
    print("dew-shrink figure done (monotonicity asserted)")
    rinfo = fig_readiness(p)
    print("readiness done:", json.dumps(rinfo, default=str)[:300])

    df = vb_consistency(p)
    worst = df.loc[df.d_min >= 15, "rel_err"].abs().max()
    med = df.loc[df.d_min >= 15, "rel_err"].abs().median()
    print(f"VB closed form vs LP: median |rel err| {med:.1%}, worst (d>=15) {worst:.1%}")
    assert worst <= 0.10, "VB closed form deviates >10% from LP frontier"

    vb22 = vb_params(p, 22.0, T_WB)
    vb15 = vb_params(p, 15.0, T_WB)
    summary = {
        "readiness": rinfo,
        "vb_worst_rel_err_d_ge_15": float(worst),
        "vb_median_rel_err_d_ge_15": float(med),
        "E_cap_dry_kWh": vb15["E_cap_cut_kWh"],
        "E_cap_humid_kWh": vb22["E_cap_cut_kWh"],
        "alpha_hold_W_per_K": vb15["alpha_hold_W_per_K"],
    }
    (OUT / "geometry_summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                               encoding="utf-8")
    write_manifest(OUT / "provenance_geometry.json", seed=SEED,
                   extra={"experiment": "phase2_envelope_geometry"})
    print("all Phase-2 geometry assertions passed.")


if __name__ == "__main__":
    main()
