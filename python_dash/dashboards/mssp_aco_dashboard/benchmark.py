"""Benchmark-versus-actual aggregation for the MSSP ACO dashboard.

Pure pandas, no Dash and no warehouse: `layout.py` feeds these the lazily
loaded frames, and the tests feed them a synthetic DuckDB.

`semantic_layer.fact_member_month_benchmark` is one row per member-month,
one to one with `fact_member_months`. It carries the surrogate key
`member_month_sk` (`person_id || '|' || year_month`) and the natural key
`(person_id, year_month)`; the dashboard joins on the natural key so that
nothing outside the benchmark elements depends on the surrogate key being
present in `fact_member_months`. Each row carries four benchmark rates:
flat, by enrollment type, risk-adjusted (uncapped), and risk-adjusted under
the ACO's aggregate cap. A rate is NULL where the fact could not compute it
— every rate when the year has no projection, the risk-adjusted rates when
the member has no CMS score, the type rate when no enrollment type resolved.

A rollup here compares actual spend to the selected rate over the *same*
member-months: rows whose selected rate is NULL are left out of both the
benchmark side and the matched actual, and are counted as excluded, so a
practice's benchmark PMPM and the actual PMPM it is set against cover one
population. Variance is actual minus benchmark; positive means spending
above the benchmark.
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd

SURROGATE_KEY = "member_month_sk"  # carried on the fact for reference
JOIN_KEYS = ["person_id", "year_month"]  # the natural key the dashboard joins on
UNATTRIBUTED = "(unattributed)"


class Rate(NamedTuple):
    key: str
    label: str
    column: str


RATES: dict[str, Rate] = {
    r.key: r
    for r in (
        Rate("flat", "Flat", "flat_benchmark_pmpm"),
        Rate("enrollment_type", "Enrollment type", "enrollment_type_benchmark_pmpm"),
        Rate("risk_adjusted_capped", "Risk-adjusted (capped)",
             "risk_adjusted_benchmark_pmpm_capped"),
        Rate("risk_adjusted", "Risk-adjusted (uncapped)", "risk_adjusted_benchmark_pmpm"),
    )
}
DEFAULT_RATE = "flat"
RATE_COLUMNS = [r.column for r in RATES.values()]

ROLLUP_COLUMNS = [
    "member_months",
    "benchmark_member_months",
    "excluded_member_months",
    "actual_pmpm",
    "benchmark_pmpm",
    "variance_pmpm",
]


def rate(key: str | None) -> Rate:
    """The selected rate, falling back to the default for an unknown key."""
    return RATES.get(key or DEFAULT_RATE, RATES[DEFAULT_RATE])


def nullable_bool(value) -> bool | None:
    """A warehouse boolean that may have come back as NULL, numpy, or object."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    return bool(value)


def merge_benchmark(member_months: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """Left-join the benchmark fact onto member months on `(person_id, year_month)`.

    Every member-month is kept. A month the fact does not cover — or every
    month, when the fact is absent and `bench` is the empty frame the safe
    query returns — carries NULL rates and counts as excluded in `rollup`.
    The rate columns are always present on the result.
    """
    has_keys = all(k in member_months.columns for k in JOIN_KEYS) and all(
        k in bench.columns for k in JOIN_KEYS
    )
    if has_keys:
        extra = [c for c in bench.columns if c in JOIN_KEYS or c not in member_months.columns]
        merged = member_months.merge(bench[extra], on=JOIN_KEYS, how="left")
    else:
        merged = member_months.copy()
    for column in RATE_COLUMNS:
        if column not in merged.columns:
            merged[column] = float("nan")
    return merged


def rollup(df: pd.DataFrame, group_col: str, rate_key: str | None) -> pd.DataFrame:
    """Actual against the selected benchmark rate, by `group_col`.

    Returns one row per group with `member_months` (all), the
    `benchmark_member_months` that carry the rate, the
    `excluded_member_months` that do not, and three PMPMs over the covered
    member-months: `actual_pmpm`, `benchmark_pmpm`, and their difference
    `variance_pmpm` (actual minus benchmark). PMPMs are NaN where no
    member-month carries the rate.
    """
    r = rate(rate_key)
    if df.empty:
        return pd.DataFrame(columns=[group_col, *ROLLUP_COLUMNS])

    member_months = pd.to_numeric(df["member_months"], errors="coerce").fillna(0)
    paid = pd.to_numeric(df["total_paid"], errors="coerce").fillna(0)
    rate_values = pd.to_numeric(df[r.column], errors="coerce")
    covered = rate_values.notna()

    parts = pd.DataFrame({
        group_col: df[group_col].fillna(UNATTRIBUTED),
        "member_months": member_months,
        "benchmark_member_months": member_months.where(covered, 0),
        "_paid": paid.where(covered, 0),
        "_benchmark": (rate_values * member_months).where(covered, 0),
    })
    out = parts.groupby(group_col, sort=True).sum().reset_index()

    denominator = out["benchmark_member_months"].where(out["benchmark_member_months"] > 0)
    out["actual_pmpm"] = out["_paid"] / denominator
    out["benchmark_pmpm"] = out["_benchmark"] / denominator
    out["variance_pmpm"] = out["actual_pmpm"] - out["benchmark_pmpm"]
    out["excluded_member_months"] = out["member_months"] - out["benchmark_member_months"]
    return out[[group_col, *ROLLUP_COLUMNS]]


def totals(df: pd.DataFrame, rate_key: str | None) -> pd.Series:
    """The `rollup` of the whole frame as a single row."""
    if df.empty:
        return pd.Series({
            "member_months": 0, "benchmark_member_months": 0, "excluded_member_months": 0,
            "actual_pmpm": float("nan"), "benchmark_pmpm": float("nan"),
            "variance_pmpm": float("nan"),
        })
    out = rollup(df.assign(_all="all"), "_all", rate_key)
    return out.iloc[0][ROLLUP_COLUMNS]


def current_projections(aco_quarters: pd.DataFrame) -> pd.DataFrame:
    """The rows of `fact_benchmark_aco_quarter` the member rates are read from.

    One per ACO and performance year, flagged `is_current_projection` by the
    fact itself; earlier quarters of a year are carried in the fact but not
    returned here. Sorted by year.
    """
    if aco_quarters.empty or "is_current_projection" not in aco_quarters.columns:
        return aco_quarters.iloc[0:0]
    flag = aco_quarters["is_current_projection"].map(nullable_bool).fillna(False).astype(bool)
    sort_cols = [c for c in ("performance_year", "aco_id") if c in aco_quarters.columns]
    return aco_quarters[flag].sort_values(sort_cols).reset_index(drop=True)
