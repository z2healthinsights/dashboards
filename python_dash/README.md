# Tuva Dash — Python alternatives to the Power BI dashboards

This directory mirrors `../power_bi/` with Python [Dash](https://dash.plotly.com/)
applications, for users who want to explore the [Tuva Project](https://thetuvaproject.com/)
data model without installing Power BI Desktop.

Each PBI dashboard has a corresponding Dash app under `dashboards/`.

## Layout

```
python_dash/
├── tuva_dash/                 # shared library
│   ├── config.py              # loads connection params from .env
│   ├── db.py                  # multi-warehouse connector
│   ├── theme.py               # shared Dash theme + Plotly template
│   └── components.py          # KPI cards, page-shell helpers
└── dashboards/
    ├── dqi_analytics/         # Data Quality Index
    ├── risk_adjust_benchmark/ # Risk-Adjusted Benchmarks
    ├── cost_and_utilization/  # Cost & Utilization (7 PBI pages)
    ├── cost_drivers/          # Cost Drivers (chronic-condition cohort filter)
    ├── mssp_aco_dashboard/    # MSSP ACO Performance (practice/provider/patient drill-down)
    ├── population_health/     # Population Health (6 PBI pages)
    ├── quality_measures/      # Quality Measures (clinical + AHRQ PQI)
    └── semantic_layer/        # Semantic Layer model browser
```

All eight dashboards are implemented end-to-end against the standard
Tuva schemas (`semantic_layer.*`, `data_quality.*`, `quality_measures.*`,
`ahrq_measures.*`). They render against any Tuva install, with graceful
"data not loaded" alerts on tabs whose source tables are empty (e.g.
`fact_risk_*` in synthetic builds, `benchmarks.*` which ships separately).

## Setup

```bash
# from the python_dash/ directory
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in connection details
```

Tested on Python 3.10+.

### Warehouse drivers

`requirements.txt` installs the **DuckDB** and **Snowflake** drivers by
default — DuckDB is the easiest local option (it's what Tuva's `dbt build`
writes to), and Snowflake is the most common hosted target. To use any
other warehouse, uncomment the relevant line in `requirements.txt` and
re-run `pip install`.

The connector dispatches on `DATA_WAREHOUSE_TYPE`. Supported values:
`duckdb`, `snowflake`, `bigquery`, `redshift`, `odbc`, `sqlserver`, `fabric`
(the non-DuckDB values match the PBI `data_warehouse_type` parameter).

### Pointing at a local Tuva DuckDB

If you've run `dbt build` against a local DuckDB Tuva install:

```bash
# .env
LOAD_DATA=true
DATA_WAREHOUSE_TYPE=duckdb
DUCKDB_DATABASE=../../tuva/tuva.duckdb   # relative to python_dash/
SCHEMA_PREPEND_NAME=NULL
```

Caveats specific to local DuckDB Tuva installs:

- **DQI Analytics** has been ported to read the standard Tuva DQ tables
  (`data_quality.medical_claim_claim_flags`, `logical`, `structural`,
  `analytical_data_marts`) instead of the PBI-only
  `data_quality_for_pbi` view, so it works against a fresh `dbt build`.
- **Risk-Adjusted Benchmarks** depends on the `benchmarks` schema, which
  is published separately by Tuva and isn't part of the standard dbt
  build. The dashboard renders gracefully with empty visuals if that
  schema is missing.
- The six scaffolded dashboards don't issue queries yet, so they render
  identically against any backend.

## Running a dashboard

From `python_dash/` with the venv active:

```bash
python -m dashboards.dqi_analytics
python -m dashboards.risk_adjust_benchmark
python -m dashboards.cost_and_utilization
# ...etc
```

Each app starts a local Dash server (defaults to http://127.0.0.1:8050).
Override host/port via `DASH_HOST` / `DASH_PORT` in `.env`.

### Running without warehouse credentials

Set `LOAD_DATA=false` in `.env`. Apps will open with empty frames matching the
expected schema, exactly as the PBI files do when their `load_data` parameter
is false.

## Adding a new dashboard

1. Create a new package under `dashboards/<name>/`.
2. Add a `queries.py` (SQL strings + a `load_*` function per table).
3. Add a `layout.py` returning a Dash component.
4. Add a `__main__.py` that wires layout + callbacks to a Dash app and calls
   `app.run_server(...)`.
5. The shared lib (`tuva_dash.db.run_query`, `tuva_dash.theme.make_app`,
   `tuva_dash.components.kpi_card`) handles the common plumbing.

## Mapping to Power BI dashboards

| Power BI file | Dash app |
| --- | --- |
| `power_bi/dqi_analytics/` | `dashboards/dqi_analytics/` |
| `power_bi/risk_adjust_benchmark/` | `dashboards/risk_adjust_benchmark/` |
| `power_bi/cost_and_utilization/` | `dashboards/cost_and_utilization/` |
| `power_bi/cost_drivers/` | `dashboards/cost_drivers/` |
| `power_bi/mssp_aco_dashboard/` | `dashboards/mssp_aco_dashboard/` |
| `power_bi/population_health/` | `dashboards/population_health/` |
| `power_bi/quality_measures/` | `dashboards/quality_measures/` |
| `power_bi/semantic_layer/` | `dashboards/semantic_layer/` |
