"""Paper-version figures (owner directives 2026-06-11): flat aspect ratios,
single-column sizes; three NEW result figures. Replots use committed CSVs;
the day-trace runs one closed-loop day; the duration sweep solves envelope LPs."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import phase5_weeks as p5
from encore.control.fallback import certified_max_q
from encore.data.loaders import load_day_prices, load_day_weather, rtm_to_5min
from encore.data.residuals import RealRecordPool
from encore.envelope.reachability import EnvelopeSpec
from encore.market.baseline import baseline_day
from encore.market.dayrun import run_day
from encore.market.offering import ready_state_for
from encore.market.portfolio import load_market_config
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import ConditionalBoxes
from encore.tighten.tube import build_tube, lqr_gain
from encore.utils.plotting import savefig, use_style
from encore.utils.stats import stable_seed

OUT = REPO / "results" / "phase6"
SEED = 20260610


def replot_F1():
    dfa = pd.read_csv(OUT / "F1_kappa.csv")
    dfb = pd.read_csv(OUT / "F1_dew.csv")
    marks = json.load(open(OUT / "provenance_F1.json"))["pai_marks"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(3.6, 1.75))
    ax1.plot(dfa.kappa, dfa.F_kW, color="0.55", lw=1.0, label="F")
    ax1.plot(dfa.kappa, dfa.Ft15_kW, color="C2", lw=1.0, marker="v", ms=2.4,
             label="F̃, d=15")
    ax1.plot(dfa.kappa, dfa.Ft30_kW, color="C0", lw=1.1, marker="o", ms=2.4,
             label="F̃, d=30")
    kc, Fc = marks["climatology"]
    kj, Fj = marks["job-aware"]
    ax1.plot([kc], [max(Fc, 1)], marker="X", ms=6, color="C3", ls="none",
             label=f"clim.\\ fc. ({Fc:.0f})")
    ax1.plot([kj], [Fj], marker="*", ms=8, color="C1", ls="none",
             label=f"job-aware ({Fj:.0f})")
    ax1.annotate("", xy=(kj, Fj), xytext=(kc, max(Fc, 1)),
                 arrowprops=dict(arrowstyle="->", color="C1", lw=0.9, ls="--"))
    ax1.set_xlabel("volatility κ (× Borg-2019)", fontsize=6.5)
    ax1.set_ylabel("certifiable offer [kW/MW IT]", fontsize=6.5)
    ax1.set_title("(a) certification wall", fontsize=7.5)
    ax1.legend(fontsize=4.8, labelspacing=0.25, handlelength=1.4)
    ax2.plot(dfb.T_dew, dfb.F_kW, color="0.55", lw=1.0, label="F")
    ax2.plot(dfb.T_dew, dfb.Ft15_kW, color="C2", lw=1.0, marker="v", ms=2.4,
             label="F̃ cond., d=15")
    ax2.plot(dfb.T_dew, dfb.Ft30_kW, color="C0", lw=1.1, marker="o", ms=2.4,
             label="F̃ cond., d=30")
    ax2.plot(dfb.T_dew, dfb.Ft30_uniform_kW, color="C3", lw=1.0,
             label="F̃ ctx-free, d=30")
    ax2.set_xlabel("DA dew forecast [°C]", fontsize=6.5)
    ax2.set_title("(b) weather coupling", fontsize=7.5)
    ax2.legend(fontsize=4.8, labelspacing=0.25, handlelength=1.4)
    for ax in (ax1, ax2):
        ax.tick_params(labelsize=6)
    fig.tight_layout(w_pad=0.8)
    savefig(fig, OUT / "F1_context")
    plt.close(fig)


def replot_portfolio():
    """Broken x-axis: the safe cluster (~0 K) and the violating cluster (>1 K)
    with the empty middle folded out."""
    df = pd.read_csv(OUT / "metrics_20seed_jobaware_eps03.csv")
    tab = df.groupby(["week", "controller"]).agg(
        mv_mean=("market_value_usd", "mean"), mv_std=("market_value_usd", "std"),
        viol_max_K=("T_viol_K", "max")).reset_index()
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(3.6, 2.0), sharey=True,
                                   gridspec_kw={"width_ratios": [1, 2.4],
                                                "wspace": 0.06})
    colors = {"B1": "0.5", "B2": "C3", "B3": "C1", "B4": "C0", "B5": "C2", "B6": "C4"}
    markers = ["o", "s", "^", "v", "D", "P", "X", "*", "<", ">"]
    for c, color in colors.items():
        for wi, wk in enumerate(sorted(tab["week"].unique())):
            sub = tab[(tab.controller == c) & (tab.week == wk)]
            for ax in (axl, axr):
                ax.errorbar(sub["viol_max_K"], sub["mv_mean"], yerr=sub["mv_std"],
                            fmt=markers[wi % len(markers)], color=color, ms=2.8,
                            lw=0.7, capsize=1.2,
                            label=c if (wi == 0 and ax is axl) else None)
    axl.set_xlim(-0.08, 0.35)
    axr.set_xlim(0.9, 11)
    axr.set_xscale("log")
    axl.spines.right.set_visible(False)
    axr.spines.left.set_visible(False)
    axr.tick_params(left=False)
    d = 0.5
    kw = dict(marker=[(-1, -d), (1, d)], markersize=6, linestyle="none",
              color="k", mec="k", mew=1, clip_on=False)
    axl.plot([1, 1], [0, 1], transform=axl.transAxes, **kw)
    axr.plot([0, 0], [0, 1], transform=axr.transAxes, **kw)
    axl.set_ylabel("market value [$/day/MW]", fontsize=7)
    fig.supxlabel("max hotspot excursion [K] (axis broken)", fontsize=7, y=0.04)
    for ax in (axl, axr):
        ax.tick_params(labelsize=6)
    axl.legend(fontsize=5.2, ncol=2, columnspacing=0.6, handletextpad=0.3)
    fig.tight_layout()
    savefig(fig, OUT / "F2_portfolio_jobaware_eps03")
    plt.close(fig)


def replot_F3():
    df = pd.read_csv(OUT / "F3_cdeg.csv")
    fig, axes = plt.subplots(1, 2, figsize=(3.6, 1.3), sharex=True)
    for ax, (day, sub) in zip(axes, df.groupby("day")):
        ax.semilogx(sub.c_deg, sub.sum_q_kW, color="C0", lw=1.0, marker="o", ms=2.4)
        ax.set_title(day.split(" ")[0], fontsize=7.5)
        ax.set_xlabel("$c_{deg}$ [\\$/K·h]", fontsize=6.5)
        ax.tick_params(labelsize=6)
    axes[0].set_ylabel("committed\n[kW/day]", fontsize=6.5)
    fig.tight_layout(w_pad=0.8)
    savefig(fig, OUT / "F3_cdeg")
    plt.close(fig)


def fig_weekly_mv():
    df = pd.read_csv(OUT / "metrics_20seed_jobaware_eps03.csv")
    tab = df[df.controller.isin(["B2", "B3", "B4", "B6"])].groupby(
        ["week", "controller"])["market_value_usd"].mean().unstack()
    weeks = sorted(tab.index)
    x = np.arange(len(weeks))
    fig, ax = plt.subplots(figsize=(3.6, 1.8))
    for i, (c, color) in enumerate([("B2", "C3"), ("B3", "C1"), ("B4", "C0"),
                                    ("B6", "C4")]):
        ax.bar(x + (i - 1.5) * 0.2, tab[c].loc[weeks], width=0.2,
               color=color, label=c)
    ax.set_xticks(x)
    ax.set_xticklabels([w.split("-")[1][:3] for w in weeks], fontsize=6.5)
    ax.set_ylabel("market value [$/day/MW]", fontsize=7)
    ax.set_yscale("symlog", linthresh=1.0)
    ax.set_ylim(0, 420)
    ax.tick_params(labelsize=6)
    ax.legend(fontsize=6, ncol=4)
    fig.tight_layout()
    savefig(fig, OUT / "weekly_mv")
    plt.close(fig)


def fig_duration():
    p = load_params()
    K = lqr_gain(p, 3, r_u=1.0 / (300e3) ** 2)
    pool = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=p5.SOURCE)
    feats, recs = pool.features_records()
    cb_d = ConditionalBoxes(feats, recs, eps=p5.EPS, k=80, k_cal=150)
    cb_s = ConditionalBoxes(feats, recs, eps=p5.EPS_SAFE, k=80, k_cal=150)
    b = cb_d.box(RealRecordPool.hour_features(14))
    bs = cb_s.box(RealRecordPool.hour_features(14))
    durations = [10, 15, 20, 30, 45, 60]
    fig, ax = plt.subplots(figsize=(3.6, 1.9))
    for dew, color, lbl in ((12.0, "C0", "dry (12 °C)"), (22.0, "C3", "humid (22 °C)")):
        F = []
        for d in durations:
            spec = EnvelopeSpec(n_states=3, T_dew=dew, d_min=float(d))
            x = ready_state_for(p, dew + bs.w_D, 3)
            tube = build_tube(p, 3, 12, bs.w_Q_sym, bs.w_D, K=K, E_budget=bs.E_hi,
                              w_Q_del=b.w_Q_sym, E_del=b.E_hi)
            F.append(max(certified_max_q(p, spec, tube, x), 0) / 1e3)
        ax.plot(durations, F, color=color, lw=1.0, marker="o", ms=2.6, label=lbl)
        assert all(np.diff(F) <= 1e-6), "F not non-increasing in d"
    ax.set_xlabel("product duration d [min]", fontsize=7)
    ax.set_ylabel("certifiable offer\n[kW/MW IT]", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.legend(fontsize=6)
    fig.tight_layout()
    savefig(fig, OUT / "duration_sweep")
    plt.close(fig)


def fig_daytrace():
    """Closed-loop anatomy of the highest-value scarcity day (2024-01-16, seed 0)."""
    DATE = "2024-01-16"
    p = load_params()
    cfg = load_market_config()
    pr = cfg["product"]
    K = lqr_gain(p, p5.N_STATES, r_u=1.0 / (p5.R_GAIN_KW * 1e3) ** 2)
    pool_fit = RealRecordPool(p.Q_IT_nom, seed=SEED, role="fit", source=p5.SOURCE)
    feats, recs = pool_fit.features_records()
    cb = ConditionalBoxes(feats, recs, eps=p5.EPS, k=80, k_cal=150)
    cb_s = ConditionalBoxes(feats, recs, eps=p5.EPS_SAFE, k=80, k_cal=150)
    prices = load_day_prices(DATE)
    weather = load_day_weather(DATE)
    base = baseline_day(p, p5.T_WB)
    offers = p5.day_offers(p, cfg, cb,
                           RealRecordPool(p.Q_IT_nom, seed=SEED + 1, role="fit",
                                          source=p5.SOURCE),
                           prices, weather, K, eps=p5.EPS, cb_safe=cb_s)
    rng = np.random.default_rng(stable_seed(DATE, 0))
    pool_e = RealRecordPool(p.Q_IT_nom, seed=stable_seed("replay", 0), role="eval",
                            source=p5.SOURCE)
    acts = rng.uniform(size=24) < pr["p_act"]
    w_day = np.array([pool_e.draw_hour(h)[0] for h in range(24)])
    dew = np.asarray(weather["dew_resid_hourly"], dtype=float)
    runs = {n: run_day(p, offers[k], acts, w_day, dew, K, controller=c)
            for n, k, c in (("B4", "B4", "mpc"), ("B2", "B2", "mpc"))}
    q4 = np.array([pl.q_W for pl in offers["B4"]])
    t5 = np.arange(288) / 12.0
    fig, axes = plt.subplots(3, 1, figsize=(3.6, 3.7), sharex=True)
    ax = axes[0]
    ax.step(range(24), prices["pi_cap_hourly"], where="post", color="0.3", lw=0.9)
    ax.set_ylabel("ECRS price\n[$/MWh]", fontsize=7)
    for h in range(24):
        if acts[h] and q4[h] > 0:
            for a in axes:
                a.axvspan(h, h + 1, color="C1", alpha=0.18, lw=0)
    ax = axes[1]
    Pb = float(np.atleast_1d(base["P_base_W"]).mean())
    ax.axhline(Pb / 1e3, color="0.5", ls=":", lw=0.9, label="baseline")
    ax.plot(t5, runs["B2"]["P_cool_W"] / 1e3, color="C3", lw=0.6, label="B2")
    ax.plot(t5, runs["B4"]["P_cool_W"] / 1e3, color="C0", lw=0.75, label="ENCORE")
    ax.set_ylabel("cooling power\n[kW]", fontsize=7)
    ax.legend(fontsize=5.6, ncol=3)
    ax = axes[2]
    ax.axhline(p.T_max, color="r", ls="--", lw=0.8)
    ax.plot(t5, runs["B2"]["T_j"], color="C3", lw=0.6, label="B2")
    ax.plot(t5, runs["B4"]["T_j"], color="C0", lw=0.75, label="ENCORE")
    ax.set_ylabel("$T_j$ [°C]", fontsize=7)
    ax.set_xlabel("hour of day", fontsize=7)
    ax.legend(fontsize=5.6, ncol=2)
    for a in axes:
        a.tick_params(labelsize=6.5)
    fig.tight_layout(h_pad=0.6)
    savefig(fig, OUT / "day_trace")
    plt.close(fig)


if __name__ == "__main__":
    use_style()
    replot_F1()
    replot_portfolio()
    replot_F3()
    fig_weekly_mv()
    fig_duration()
    fig_daytrace()
    print("paper figures done")
