"""SQL queries for the Risk-Adjusted Benchmarks dashboard.

Mirrors the partition queries in
../../power_bi/risk_adjust_benchmark/Risk-adjusted Benchmarks.SemanticModel/
definition/tables/*.tmdl. The TMDL hard-codes Snowflake; this module assumes
the warehouse is Snowflake too but goes through `tuva_dash.run_query` so any
ANSI-SQL warehouse with the same `BENCHMARKS` schema will work.
"""

from __future__ import annotations

import logging

import pandas as pd

from tuva_dash import run_query
from tuva_dash.config import get_settings

log = logging.getLogger(__name__)

BENCHMARKS_SCHEMA = "benchmarks"

_MEMBER_MONTH_COLS = [
    "person_id", "year_month", "service_category_1", "service_category_2",
    "actual_pmpm", "expected_pmpm", "member_months",
]
_INPATIENT_COLS = [
    "encounter_id", "person_id", "admit_date", "discharge_date",
    "actual_los", "expected_los", "actual_readmission",
    "expected_readmission", "actual_discharge_home",
    "expected_discharge_home", "paid_amount",
]


def _row_limit_clause() -> str:
    s = get_settings()
    return f"LIMIT {s.row_limit}" if s.row_limit else ""


def _safe_query(sql: str, columns: list[str]) -> pd.DataFrame:
    """Return an empty frame if the query fails (e.g. benchmarks schema not loaded).

    The risk-adjusted `benchmarks` schema is published separately from the
    open-source Tuva dbt project, so it may not exist in every Tuva install
    (notably local DuckDB builds). Treating "table missing" as empty data
    lets the dashboard still render with a no-data message.
    """
    try:
        return run_query(sql, columns=columns)
    except Exception as exc:
        log.warning("benchmarks query failed (returning empty frame): %s", exc)
        return pd.DataFrame(columns=columns)


def load_member_month() -> pd.DataFrame:
    s = get_settings()
    sql = (
        f"SELECT * FROM {s.qualified(BENCHMARKS_SCHEMA, 'predict_member_month')} "
        f"{_row_limit_clause()}"
    )
    return _safe_query(sql, _MEMBER_MONTH_COLS)


def load_inpatient() -> pd.DataFrame:
    s = get_settings()
    sql = (
        f"SELECT * FROM {s.qualified(BENCHMARKS_SCHEMA, 'predict_inpatient')} "
        f"{_row_limit_clause()}"
    )
    return _safe_query(sql, _INPATIENT_COLS)
