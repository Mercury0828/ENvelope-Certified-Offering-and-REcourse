"""One-command regeneration of every Phase-6 figure and table (guide §11 acceptance).

    python experiments/make_figures.py [--skip-table]

Runs, in order: F1 (context value), F3 (degradation sweep), stress tests, and the
20-seed main table + F2 (skippable — ~35 min). Writes an aggregate provenance manifest
mapping every artifact to its generating script, seed, git hash and config hashes.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from encore.plant.params import REPO_ROOT, config_hash
from encore.utils.provenance import manifest

SCRIPTS = [
    ("phase6_F1_context.py", ["F1_context.pdf", "F1_context.png", "F1_context.csv"]),
    ("phase6_F3_cdeg.py", ["F3_cdeg.pdf", "F3_cdeg.png", "F3_cdeg.csv"]),
    ("phase6_stress.py", ["stress_tests.csv", "stress_summary.csv"]),
    ("phase6_F2_table.py", ["F2_portfolio.pdf", "F2_portfolio.png", "main_table.csv",
                            "metrics_20seed.csv", "certificate_validity.json"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-table", action="store_true",
                    help="skip the 20-seed main-table run (~35 min)")
    args = ap.parse_args()

    ran = []
    for script, artifacts in SCRIPTS:
        skipped = args.skip_table and script == "phase6_F2_table.py"
        if not skipped:
            print(f"=== {script} ===", flush=True)
            subprocess.run([sys.executable, str(REPO / "experiments" / script)],
                           check=True)
        ran.append({"script": f"experiments/{script}",
                    "artifacts": [f"results/phase6/{a}" for a in artifacts],
                    "skipped_this_invocation": skipped})

    m = manifest(seed=20260610, extra={
        "experiment": "make_figures",
        "market_config_sha256": config_hash(REPO_ROOT / "config" / "market.yaml"),
        "mplstyle_sha256": config_hash(REPO_ROOT / "config" / "encore.mplstyle"),
        "generated": ran,
    })
    out = REPO / "results" / "phase6" / "FIGURES_MANIFEST.json"
    out.write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(f"\nmanifest -> {out}")


if __name__ == "__main__":
    main()
