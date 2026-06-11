"""Regenerate the F2 portfolio scatter with paper-clean labels (no pipeline
jargon in titles), from the committed metrics CSV (D-052 final config)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import matplotlib.pyplot as plt
import pandas as pd

from encore.utils.plotting import savefig, use_style

OUT = REPO / "results" / "phase6"


def main():
    use_style()
    df = pd.read_csv(OUT / "metrics_20seed_jobaware_eps03.csv")
    tab = df.groupby(["week", "controller"]).agg(
        mv_mean=("market_value_usd", "mean"), mv_std=("market_value_usd", "std"),
        viol_max_K=("T_viol_K", "max")).reset_index()
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    colors = {"B1": "0.5", "B2": "C3", "B3": "C1", "B4": "C0", "B5": "C2", "B6": "C4"}
    markers = ["o", "s", "^", "v", "D", "P", "X", "*", "<", ">"]
    weeks_sorted = sorted(tab["week"].unique())
    for c, color in colors.items():
        for wi, wk in enumerate(weeks_sorted):
            sub = tab[(tab.controller == c) & (tab.week == wk)]
            ax.errorbar(sub["viol_max_K"] + 0.01, sub["mv_mean"], yerr=sub["mv_std"],
                        fmt=markers[wi % len(markers)], color=color, ms=5, lw=1,
                        capsize=2, label=c if wi == 0 else None)
    ax.set_xscale("log")
    ax.set_xlabel("max hotspot excursion [K] (log scale, +0.01 offset)")
    ax.set_ylabel("market value vs. idle [$/day per MW IT]")
    ax.legend(fontsize=7.5, ncol=3)
    fig.tight_layout()
    savefig(fig, OUT / "F2_portfolio_jobaware_eps03")
    plt.close(fig)
    print("F2 figure regenerated (paper-clean labels)")


if __name__ == "__main__":
    main()
