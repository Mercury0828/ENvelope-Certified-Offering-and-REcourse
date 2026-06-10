"""Shared plotting style; all figures saved as PDF + PNG (guide 12 / run rules)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless runs
import matplotlib.pyplot as plt

from ..plant.params import REPO_ROOT

STYLE_FILE = REPO_ROOT / "config" / "encore.mplstyle"


def use_style() -> None:
    plt.style.use(str(STYLE_FILE))


def savefig(fig, stem: str | Path) -> list[Path]:
    """Save figure as <stem>.pdf and <stem>.png."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        out = stem.with_suffix(f".{ext}")
        fig.savefig(out)
        paths.append(out)
    return paths
