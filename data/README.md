# data/

Raw/cached datasets live here and are gitignored (guide.md Section 9). Acquisition
scripts: `experiments/fetch_ercot_prices.py`, `experiments/preprocess_google_trace.py`
(KIAH fetched via a logged one-shot IEM request). Provenance JSONs sit next to each
dataset. Owner-approved source plan recorded as D-034.

| dataset | source | URL / route | retrieved | files |
|---|---|---|---|---|
| ERCOT DAM SPP, HB_HOUSTON, hourly, 2023–2024 | ERCOT MIS "Historical DAM Load Zone and Hub Prices" via gridstatus 0.36.0 `Ercot.get_dam_spp(year)` | ercot.com MIS (report 13060 backend) | 2026-06-10 | `ercot/dam_spp_hb_houston_2023_2024.csv` |
| ERCOT RTM SPP, HB_HOUSTON, 15-min, 2023–2024 | same route, `get_rtm_spp(year)` — 15-min settlement SPP (NOT 5-min SCED LMP; settlement granularity is what the model's ΔH-accounting needs) | ercot.com MIS (report 13061 backend) | 2026-06-10 | `ercot/rtm_spp_hb_houston_2023_2024.csv` |
| ERCOT AS MCPC (π^cap proxy) | attempted via gridstatus daily docs — see `ercot/summary.json` for outcome; manual fallback NP4-188-CD remains in DATA_REQUEST if absent | ercot.com MIS | 2026-06-10 | `ercot/as_mcpc_2023_2024.csv` (if present) |
| KIAH hourly weather (T_amb, T_dew, RH), 2023-01-01→2024-12-31 UTC | Iowa Environmental Mesonet ASOS, station IAH, routine hourly METARs (`report_type=3`) | mesonet.agron.iastate.edu/cgi-bin/request/asos.py | 2026-06-10 | `weather/kiah_asos_2023_2024.csv` (17,545 rows, 0% missing tmpf/dwpf) |
| Google Borg 2019 cell-a instance_usage (4 random shards, ~2.5M rows, full 31 days) | public GCS bucket, unauthenticated HTTPS (parquet exports; note: `.parquet.gz` files are plain parquet despite the name) | storage.googleapis.com/clusterdata_2019_a/instance_usage-00000000000{0..3}.parquet.gz | 2026-06-10 | `traces/google2019a/instance_usage-*.parquet.gz` |
| → processed 1 MW hall profile, 5-min mean + peak | `experiments/preprocess_google_trace.py` (sum-of-sampled-usage shape, affine power map idle=0.3 [est], ~6% sampling noise) | derived | 2026-06-10 | `traces/google2019a/hall_profile_5min.csv`, `hall_profile_stats.json` |

## Known caveats

- **Trace peak series is a non-simultaneity UPPER bound** (sum of per-instance 5-min
  peaks; median uplift +130% over mean). Fine as a stress upper bound; Phase 5/6 should
  concurrency-adjust using the `cpu_usage_distribution` percentile vectors before the
  burst-overlay magnitudes are finalized.
- Trace timestamps are trace-relative (day boundaries unknown vs wall clock); usable
  for profile shape and burst statistics, not for hour-of-day alignment with prices —
  alignment convention to be decided in Phase 5 scenario design (logged then).
- TMY3 (typical-year) weather deliberately NOT used: the model needs real joint
  price/weather days (guide §9); IEM ASOS observations are the real-year source.
