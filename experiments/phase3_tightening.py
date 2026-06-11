"""Phase 3 — conditional tightening + certified fallback + online MPC (guide §11).

Pipeline (synthetic contextual ground truth, D-025 — real data swaps in via
data/DATA_REQUEST.md):
1. Conformally calibrated k-NN quantile sets W(c) (budget polytope, D-031/D-033);
   empirical coverage >= 1 - eps per context bin verified against the ground truth.
2. Tightened envelope F-tilde via tube margins (fixed LQR gain, authority swept over
   {10,20,50,100} kW/K, best total certified depth kept and logged). Commitments are
   quoted from the pre-cooled READY state (the product's operating concept; nominal-
   state values reported alongside). Comparators: pooled box (under-covers bursty bins
   -> invalid) and uniform box (valid context-free certificate, D-030).
3. Acceptance validation per certifiable bin (eps = 0.1): commit q = F-tilde_cond(x_ready);
   500 held-out scenarios: ZERO safety violations for in-box scenarios (Thm 2), overall
   delivery-failure rate <= eps (binomial CI); same under tube-margin MPC with fallback
   switch (Thm 3); box-corner injection survives; 1.5x beyond-box injection demonstrates
   the switch. Bins with empty F-tilde are recorded as "not certifiable" — context telling
   the D-1 layer when NOT to offer is a result, not a failure (guide §8 honest-result clause).

Outputs to results/phase3/: proto_F1.{pdf,png}, validation.csv, coverage.csv,
envelopes.csv, key_numbers.json, provenance.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from encore.control.fallback import certified_max_q, certify, simulate_policy
from encore.control.mpc import mpc_controller
from encore.data.synthetic import Context, draw_dew_residual, draw_step_heat_devs, generate_history
from encore.envelope.geometry import max_q, poly_halfspaces
from encore.envelope.readiness import readiness_iteration
from encore.envelope.reachability import EnvelopeSpec, build_lifted
from encore.plant.dynamics import steady_state
from encore.plant.params import load_params
from encore.plant.virtual_input import T_in_floor
from encore.tighten.quantile_boxes import Box, ConditionalBoxes
from encore.tighten.tube import build_tube, corner_disturbance, lqr_gain
from encore.utils.plotting import savefig, use_style
from encore.utils.provenance import write_manifest

OUT = REPO / "results" / "phase3"
SEED = 20260610
EPS = 0.1
N_HIST = 6000
N_SCEN = 500
D_MIN = 30.0

BINS = {
    "dry-calm": Context(hour=3, burst_share=0.05, T_dew_fc=15.0, sigma_regime=0),
    "dry-bursty": Context(hour=14, burst_share=0.8, T_dew_fc=15.0, sigma_regime=0),
    "humid-calm": Context(hour=3, burst_share=0.05, T_dew_fc=22.0, sigma_regime=1),
    "humid-bursty": Context(hour=14, burst_share=0.8, T_dew_fc=22.0, sigma_regime=1),
}


def spec_for(c: Context) -> EnvelopeSpec:
    return EnvelopeSpec(n_states=2, T_dew=c.T_dew_fc, d_min=D_MIN)


def ready_state(p, c: Context):
    return steady_state(p, 2, p.Q_IT_nom, T_in_floor(p, c.T_dew_fc))[0]


def coverage(rng, c, box: Box, p, n=2000) -> float:
    hits = 0
    for _ in range(n):
        devs = draw_step_heat_devs(rng, c, p.Q_IT_nom)
        rec_E = float(np.maximum(devs, 0.0).sum() * p.dt_ctrl)
        hits += box.contains(devs.max(), rec_E, draw_dew_residual(rng, c))
    return hits / n


def tube_for(p, box: Box, K=None):
    return build_tube(p, 2, 12, w_Q=box.w_Q_sym, w_D=box.w_D, K=K, E_budget=box.E_hi)


def pick_gain(p, cb, x0_nom):
    """Sweep feedback-authority levels; keep K maximizing total certified depth
    (sum of positive F-tilde over bins x {nominal, ready} states)."""
    best = None
    for r_kW in (10.0, 20.0, 50.0, 100.0):
        K = lqr_gain(p, r_u=1.0 / (r_kW * 1e3) ** 2)
        score = 0.0
        for c in BINS.values():
            tube = tube_for(p, cb.box(c.features()), K=K)
            for x0 in (x0_nom, ready_state(p, c)):
                score += max(certified_max_q(p, spec_for(c), tube, x0), 0.0)
        if best is None or score > best[1]:
            best = (r_kW, score, K)
    return best


def main():
    use_style()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    rng = np.random.default_rng(SEED)
    x0_nom, _ = steady_state(p, 2, p.Q_IT_nom, p.T_in_nom)

    feats, recs = generate_history(rng, p.Q_IT_nom, n=N_HIST)
    cb = ConditionalBoxes(feats, recs, eps=EPS)
    cb05 = ConditionalBoxes(feats, recs, eps=0.05)

    r_kW, _, K = pick_gain(p, cb, x0_nom)
    print(f"fallback gain: LQR authority {r_kW:.0f} kW/K -> K = {np.round(K[0] / 1e3, 2)} kW/K")

    # uniform unconditional box: elementwise max over a context sample (valid everywhere)
    ctx_sample = [Context(h, s, td, rg) for h in (3, 9, 14, 20) for s in (0.05, 0.5, 0.95)
                  for td in (12.0, 18.0, 24.0) for rg in (0, 1)]
    boxes = [cb.box(c.features()) for c in ctx_sample]
    uni = Box(w_Q_hi=max(b.w_Q_hi for b in boxes), E_hi=max(b.E_hi for b in boxes),
              w_D_hi=max(b.w_D_hi for b in boxes))
    pooled = cb.unconditional_box()

    cov_rows, env_rows, val_rows = [], [], []
    key = {"eps": EPS, "gain_authority_kW_per_K": r_kW}
    n_certifiable = 0

    for name, c in BINS.items():
        box = cb.box(c.features())
        cov_c = coverage(rng, c, box, p)
        cov_rows.append({"bin": name, "cov_conditional": cov_c,
                         "cov_pooled": coverage(rng, c, pooled, p),
                         "cov_uniform": coverage(rng, c, uni, p),
                         "w_Q_kW": box.w_Q_sym / 1e3, "E_MJ": box.E_hi / 1e6,
                         "w_D_K": box.w_D})
        assert cov_c >= 1 - EPS - 0.02, f"conditional box under-covers in {name}: {cov_c:.3f}"

        spec = spec_for(c)
        x0_rdy = ready_state(p, c)
        tube_c = tube_for(p, box, K=K)
        env_rows.append({
            "bin": name,
            "F_nom_kW": max_q(build_lifted(p, spec), x0_nom) / 1e3,
            "F_ready_kW": max_q(build_lifted(p, spec), x0_rdy) / 1e3,
            "Ft_cond_nom_kW": certified_max_q(p, spec, tube_c, x0_nom) / 1e3,
            "Ft_cond_ready_kW": certified_max_q(p, spec, tube_c, x0_rdy) / 1e3,
            "Ft_cond05_ready_kW":
                certified_max_q(p, spec, tube_for(p, cb05.box(c.features()), K=K), x0_rdy) / 1e3,
            "Ft_uniform_ready_kW": certified_max_q(p, spec, tube_for(p, uni, K=K), x0_rdy) / 1e3,
            "Ft_pooled_ready_kW": certified_max_q(p, spec, tube_for(p, pooled, K=K), x0_rdy) / 1e3,
        })
        row = env_rows[-1]
        assert row["Ft_cond_ready_kW"] <= row["F_ready_kW"] + 1e-3
        assert row["Ft_uniform_ready_kW"] <= row["Ft_cond_ready_kW"] + 1e-3, \
            f"uniform-box envelope exceeds conditional in {name}"

        # ---- held-out validation at the committed offer from the READY state ----
        q = max(row["Ft_cond_ready_kW"] * 1e3 - 100.0, 0.0)
        if q <= 0.0:
            val_rows.append({"bin": name, "policy": "n/a", "q_committed_kW": 0.0,
                             "certifiable": False})
            print(f"  {name}: NOT certifiable at eps={EPS} (F̃_ready <= 0) — "
                  "context flags this bin as no-offer")
            continue
        n_certifiable += 1
        cert = certify(p, spec, tube_c, x0_rdy, q)
        assert cert is not None, f"certificate vanished below its own F-tilde in {name}"
        ready = readiness_iteration(p, spec, q=q, max_iter=8, tol_K=0.1)
        term_hs = poly_halfspaces(ready["fixed_point"])

        stats = {m: {"viol_in": 0, "viol_out": 0, "dfail": 0, "switches": 0, "n_in": 0}
                 for m in ("fallback", "mpc")}
        for _ in range(N_SCEN):
            w = draw_step_heat_devs(rng, c, p.Q_IT_nom)
            dres = draw_dew_residual(rng, c)
            in_box = box.contains(w.max(), float(np.maximum(w, 0).sum() * p.dt_ctrl), dres)
            for mode in ("fallback", "mpc"):
                if mode == "fallback":
                    out = simulate_policy(p, cert, w, dres)
                else:
                    ctl, st = mpc_controller(p, cert, terminal_hs=term_hs, tube=tube_c)
                    out = simulate_policy(p, cert, w, dres, controller=ctl)
                    stats[mode]["switches"] += int(st["switched"])
                s = stats[mode]
                s["n_in"] += int(in_box)
                if out["T_viol_K"] > 1e-6:
                    s["viol_in" if in_box else "viol_out"] += 1
                if not out["delivery_ok"]:
                    s["dfail"] += 1

        for mode, s in stats.items():
            rate = s["dfail"] / N_SCEN
            val_rows.append({"bin": name, "policy": mode, "q_committed_kW": q / 1e3,
                             "certifiable": True, "n": N_SCEN, "n_in_box": s["n_in"],
                             "safety_viol_in_box": s["viol_in"],
                             "safety_viol_out_box": s["viol_out"],
                             "delivery_fail_rate": rate,
                             "delivery_fail_ci95_hi":
                                 rate + 1.96 * np.sqrt(max(rate * (1 - rate), 1e-9) / N_SCEN),
                             "mpc_switches": s["switches"] if mode == "mpc" else None})
            assert s["viol_in"] == 0, f"safety violation INSIDE the box: {name}/{mode}"
            assert rate <= EPS + 1.96 * np.sqrt(EPS * (1 - EPS) / N_SCEN), \
                f"delivery-failure rate {rate:.3f} above eps in {name}/{mode}"

        # ---- worst-case injections ----
        w_corner = corner_disturbance(box, 12, p.dt_ctrl)
        corner = simulate_policy(p, cert, w_corner, tube_c.w_D)
        assert corner["T_viol_K"] <= 1e-6 and corner["delivery_ok"], \
            f"box-corner injection failed in {name}"
        ctl, st = mpc_controller(p, cert, terminal_hs=term_hs, tube=tube_c)
        beyond = simulate_policy(p, cert, 1.5 * w_corner, 1.5 * tube_c.w_D, controller=ctl)
        key[f"{name}_beyond_box"] = {"switched": st["switched"],
                                     "T_viol_K": beyond["T_viol_K"],
                                     "delivery_ratio": beyond["delivery_ratio"]}
        print(f"  {name}: q={q/1e3:.1f} kW committed (ready state); cov {cov_c:.3f}; "
              f"corner OK; beyond-box switch={st['switched']}")

    assert n_certifiable >= 1, "no bin certifiable — machinery cannot be validated"

    cov_df = pd.DataFrame(cov_rows)
    env_df = pd.DataFrame(env_rows)
    val_df = pd.DataFrame(val_rows)
    cov_df.to_csv(OUT / "coverage.csv", index=False)
    env_df.to_csv(OUT / "envelopes.csv", index=False)
    val_df.to_csv(OUT / "validation.csv", index=False)

    # ---- proto-F1 figure (ready-state quotes) ----
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    xb = np.arange(len(env_df))
    wd = 0.19
    clip = lambda v: np.maximum(v, 0.0)
    ax.bar(xb - 1.5 * wd, clip(env_df.F_ready_kW), wd, label="F (no uncertainty)", color="0.75")
    ax.bar(xb - 0.5 * wd, clip(env_df.Ft_cond_ready_kW), wd,
           label="F̃ conditional (ε=0.1)", color="C0")
    ax.bar(xb + 0.5 * wd, clip(env_df.Ft_cond05_ready_kW), wd,
           label="F̃ conditional (ε=0.05)", color="C2")
    ax.bar(xb + 1.5 * wd, clip(env_df.Ft_uniform_ready_kW), wd,
           label="F̃ context-free (uniform box)", color="C1")
    ax.set_xticks(xb, env_df["bin"])
    ax.set_ylabel("max certifiable offer from ready state [kW]")
    ax.set_title("Value of context (proto-F1), d = 30 min, synthetic ground truth\n"
                 "zero-height bars = not certifiable; pooled-box comparator additionally "
                 "UNDER-COVERS bursty bins (coverage.csv)")
    ax.legend(fontsize=7.5)
    fig.tight_layout()
    savefig(fig, OUT / "proto_F1")
    plt.close(fig)

    key.update({
        "n_certifiable_bins": n_certifiable,
        "coverage": cov_rows, "envelopes_kW": env_df.to_dict("records"),
        "uniform_box": {"w_Q_kW": uni.w_Q_sym / 1e3, "E_MJ": uni.E_hi / 1e6,
                        "w_D_K": uni.w_D},
        "pooled_box": {"w_Q_kW": pooled.w_Q_sym / 1e3, "E_MJ": pooled.E_hi / 1e6,
                       "w_D_K": pooled.w_D},
    })
    (OUT / "key_numbers.json").write_text(json.dumps(key, indent=2, default=float),
                                          encoding="utf-8")
    write_manifest(OUT / "provenance_tightening.json", seed=SEED,
                   extra={"experiment": "phase3_tightening", "eps": EPS,
                          "n_hist": N_HIST, "n_scen": N_SCEN})
    print("\nenvelope summary [kW]:")
    print(env_df.round(1).to_string(index=False))
    print("\nvalidation summary:")
    print(val_df.to_string(index=False))
    print("\nall Phase-3 assertions passed.")


if __name__ == "__main__":
    main()
