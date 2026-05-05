"""SQL queries for the DQI Analytics dashboard.

The Power BI version of this dashboard reads denormalized PBI-specific views
(`data_quality.data_quality_for_pbi`, `summary`, `quality_trend`,
`claim_type_summary`) that aren't published by the open-source Tuva dbt
project. To stay portable across local DuckDB / Snowflake / etc, this Dash
version reads the standard Tuva data-quality outputs instead:

  - data_quality.analytical_data_marts        (mart-level row counts)
  - data_quality.structural                   (per-table structural test)
  - data_quality.logical                      (per-table logical test rollup)
  - data_quality.medical_claim_claim_flags    (claim-level atomic flags)

These are the same tables the Tuva CLI populates via `dbt build`.
"""

from __future__ import annotations

import pandas as pd

from tuva_dash import run_query
from tuva_dash.config import get_settings

DQ_SCHEMA = "data_quality"


def load_data_marts() -> pd.DataFrame:
    s = get_settings()
    sql = f"SELECT * FROM {s.qualified(DQ_SCHEMA, 'analytical_data_marts')}"
    return run_query(sql, columns=["data_mart", "row_count"])


def load_structural() -> pd.DataFrame:
    s = get_settings()
    sql = f"SELECT * FROM {s.qualified(DQ_SCHEMA, 'structural')}"
    return run_query(
        sql,
        columns=[
            "data_source", "table_name", "table_exists", "columns_exist",
            "data_types", "primary_keys", "row_count",
        ],
    )


def load_logical() -> pd.DataFrame:
    s = get_settings()
    sql = f"SELECT * FROM {s.qualified(DQ_SCHEMA, 'logical')}"
    return run_query(
        sql,
        columns=["data_source", "table", "test_name", "test_result"],
    )


def load_claim_flags() -> pd.DataFrame:
    s = get_settings()
    sql = f"SELECT * FROM {s.qualified(DQ_SCHEMA, 'medical_claim_claim_flags')}"
    return run_query(
        sql,
        columns=[
            "claim_id", "data_source",
            "claim_type_count_ne_one_per_claim",
            "multiple_person_ids_per_claim",
            "admission_date_has_multiple_values_per_inpatient_claim",
            "discharge_date_has_multiple_values_per_inpatient_claim",
            "bill_type_code_count_ne_one_for_institutional_claim",
            "drg_code_count_ne_one_for_acute_inpatient_claim",
            "no_matching_eligibility_span",
        ],
    )
