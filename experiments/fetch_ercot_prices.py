"""Data acquisition — ERCOT prices via gridstatus (owner-approved route, D-034).

Pulls the annual MIS "Historical DAM/RTM Load Zone and Hub Prices" packages
(the same backend as the manual fallback), filters HB_HOUSTON, writes tidy CSVs to
data/ercot/ (gitignored) plus a provenance manifest.

DAM: hourly SPP. RTM: 15-min SPP (the settlement-relevant granularity for our
ΔH-accounting; 5-min SCED LMPs are a different report and not needed by the model).
AS MCPC (pi^cap proxy, REGDN/REGUP/RRS/NSPIN/ECRS): the daily NP4-188 docs expire on
MIS, so we pull the ANNUAL "Historical DAM Clearing Prices for Capacity" packages
(report type 13091, DAMASMCPC_<year>), discovered dynamically from the MIS listing.
Note: ECRS is NaN before its June-2023 market launch — a fact, not a gap.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import io
import json
import urllib.request
import zipfile

import gridstatus
import pandas as pd

from encore.utils.provenance import write_manifest

MIS_LIST = "https://www.ercot.com/misapp/servlets/IceDocListJsonWS?reportTypeId=13091"
MIS_DL = "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId={doc_id}"


def fetch_as_mcpc(years) -> pd.DataFrame:
    req = urllib.request.Request(MIS_LIST, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        docs = json.load(r)["ListDocsByRptTypeRes"]["DocumentList"]
    by_name = {d["Document"]["FriendlyName"]: d["Document"]["DocID"] for d in docs}
    frames = []
    for y in years:
        doc_id = by_name[f"DAMASMCPC_{y}"]
        req = urllib.request.Request(MIS_DL.format(doc_id=doc_id),
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            zf = zipfile.ZipFile(io.BytesIO(r.read()))
        with zf.open(zf.namelist()[0]) as f:
            frames.append(pd.read_csv(f))
    df = pd.concat(frames, ignore_index=True)
    df.columns = [c.strip() for c in df.columns]
    return df

OUT = REPO / "data" / "ercot"
YEARS = (2023, 2024)
HUB = "HB_HOUSTON"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    iso = gridstatus.Ercot()
    info = {"gridstatus": gridstatus.__version__, "hub": HUB, "years": list(YEARS)}

    for kind, getter in (("dam", iso.get_dam_spp), ("rtm", iso.get_rtm_spp)):
        path = OUT / f"{kind}_spp_hb_houston_{YEARS[0]}_{YEARS[-1]}.csv"
        if path.exists():
            info[f"{kind}_rows"] = len(pd.read_csv(path))
            info[f"{kind}_file"] = path.name
            print(f"{path.name} exists ({info[f'{kind}_rows']} rows) — skipping")
            continue
        frames = []
        for y in YEARS:
            df = getter(y)
            df = df[df["Location"] == HUB].copy()
            frames.append(df)
            print(f"{kind.upper()} {y}: {len(df)} {HUB} rows")
        alldf = pd.concat(frames).sort_values("Interval Start").reset_index(drop=True)
        alldf.to_csv(path, index=False)
        info[f"{kind}_rows"] = len(alldf)
        info[f"{kind}_file"] = path.name
        print(f"wrote {path.name}: {len(alldf)} rows, "
              f"{alldf['Interval Start'].min()} -> {alldf['Interval End'].max()}")

    # AS capacity prices (pi^cap proxy) via the annual 13091 packages
    as_df = fetch_as_mcpc(YEARS)
    as_path = OUT / f"as_mcpc_{YEARS[0]}_{YEARS[-1]}.csv"
    as_df.to_csv(as_path, index=False)
    info["as_rows"] = len(as_df)
    info["as_file"] = as_path.name
    info["as_note"] = "ECRS NaN before its 2023-06 launch (market fact)"
    print(f"wrote {as_path.name}: {len(as_df)} rows")

    write_manifest(OUT / "provenance_ercot.json", seed=None,
                   extra={"experiment": "fetch_ercot_prices", **info})
    (OUT / "summary.json").write_text(json.dumps(info, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
