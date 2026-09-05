"""Synthetic DuckDB fixtures for the MSSP ACO benchmark tests.

Every row here is invented. The numbers are chosen so the expected
rollups are exact and the variance sign flips between rates:

Practice A  P1 (aged/dual, scored) pays 1600/month, P2 (aged/dual, no
            score) pays 500/month. Flat 1000, enrollment-type 1200. P1's
            risk ratio 1.5 gives an uncapped risk-adjusted rate of 1800,
            capped by the year's factor 0.8 to 1440. P2 has no
            risk-adjusted rate.
Practice B  P3 (disabled, scored) pays 700/month against a type rate of
            800, ratio 0.5, so 400 uncapped and 320 capped. P4 has no
            resolved enrollment type and carries the flat rate only.

Two months (202601, 202602) per member, one member-month per row.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from tuva_dash.config import get_settings
from tuva_dash.lazy import LazyFrame

MONTHS = ["202601", "202602"]

MEMBERS = [
    # person_id, practice, provider, paid, enrollment_type, risk_score,
    # risk_ratio, enrollment_type_rate, risk_adjusted_rate
    ("P1", "Practice A", "Dr One", 1600.0, "aged_dual", 1.5, 1.5, 1200.0, 1800.0),
    ("P2", "Practice A", "Dr One", 500.0, "aged_dual", None, None, 1200.0, None),
    ("P3", "Practice B", "Dr Two", 700.0, "disabled", 0.5, 0.5, 800.0, 400.0),
    ("P4", "Practice B", "Dr Three", 100.0, None, 1.1, None, None, None),
]

FLAT_RATE = 1000.0
CAP_FACTOR = 0.8


def _member_month_frames() -> dict[str, pd.DataFrame]:
    fact_rows, dim_rows, bench_rows = [], [], []
    for pid, practice, provider, paid, etype, score, ratio, et_rate, ra_rate in MEMBERS:
        for ym in MONTHS:
            sk = f"{pid}|{ym}"
            fact_rows.append({
                "person_id": pid, "data_source": "synthetic", "year_month": ym,
                "year_nbr": "2026", "member_month_sk": sk,
                "patient_source_key": f"{pid}|synthetic", "member_months": 1,
                "total_paid": paid, "medical_paid": paid, "pharmacy_paid": 0.0,
                "normalized_risk_score": score if score is not None else 1.0,
            })
            dim_rows.append({
                "person_id": pid, "year_month": ym, "payer": "synthetic",
                "payer_attributed_provider": provider,
                "payer_attributed_provider_practice": practice,
                "custom_attributed_provider": None,
            })
            capped = ra_rate * CAP_FACTOR if ra_rate is not None else None
            bench_rows.append({
                "member_month_sk": sk, "person_id": pid, "data_source": "synthetic",
                "patient_source_key": f"{pid}|synthetic", "year_month": ym,
                "performance_year": 2026, "aco_id": "ACO-TEST", "is_assigned": True,
                "enrollment_type": etype, "risk_score": score, "risk_ratio": ratio,
                "flat_benchmark_pmpm": FLAT_RATE,
                "enrollment_type_benchmark_pmpm": et_rate,
                "risk_adjusted_benchmark_pmpm": ra_rate,
                "cap_factor": CAP_FACTOR,
                "risk_adjusted_benchmark_pmpm_capped": capped,
                "total_paid": paid,
                "variance_to_flat": paid - FLAT_RATE,
                "variance_to_enrollment_type": paid - et_rate if et_rate is not None else None,
                "variance_to_risk_adjusted": paid - ra_rate if ra_rate is not None else None,
                "variance_to_risk_adjusted_capped": paid - capped if capped is not None else None,
                "has_benchmark": True, "benchmark_period": "2026Q2",
                "benchmark_submission_id": "BENCH-T26",
                "is_agreement_defaulted": False,
            })
    members = pd.DataFrame([
        {"person_id": pid, "first_name": f"First{pid}", "last_name": f"Last{pid}",
         "age": 70, "sex": "female", "birth_date": "1956-01-01", "address": "1 Test St",
         "city": "Testville", "state": "ZZ", "zip_code": "00000", "race": None,
         "data_source": "synthetic"}
        for pid, *_ in MEMBERS
    ])
    return {
        "fact_member_months": pd.DataFrame(fact_rows),
        "dim_member_months": pd.DataFrame(dim_rows),
        "dim_member": members,
        "fact_member_month_benchmark": pd.DataFrame(bench_rows),
    }


def _aco_quarter_frame() -> pd.DataFrame:
    common = {"aco_id": "ACO-TEST", "risk_score_cap": 0.03, "cap_upper_bound": 1.03,
              "estimated_msr": 0.02}
    return pd.DataFrame([
        # Earlier quarter of 2026: carried, but not the current projection.
        {**common, "performance_year": 2026, "period": "2026Q1", "quarter_num": 1,
         "is_current_projection": False, "benchmark_submission_id": "BENCH-T26",
         "quarterly_submission_id": "QTR-T26-1",
         "mean_projected_updated_benchmark_pmpm": 900.0,
         "aco_expenditure_per_capita_pmpm": 950.0,
         "projected_savings_percentage": -0.0556, "msr_basis_applied": "variable",
         "savings_status": "no_savings", "aggregate_risk_ratio": 1.4,
         "cap_factor": 1.03 / 1.4, "is_cap_binding": True,
         "risk_adjusted_benchmark_pmpm": 1050.0, "national_growth_projected": 1.05,
         "cap_upper_bound_scenario": 1.08, "is_cap_binding_scenario": True,
         "is_agreement_defaulted": False},
        {**common, "performance_year": 2026, "period": "2026Q2", "quarter_num": 2,
         "is_current_projection": True, "benchmark_submission_id": "BENCH-T26",
         "quarterly_submission_id": "QTR-T26-2",
         "mean_projected_updated_benchmark_pmpm": 1000.0,
         "aco_expenditure_per_capita_pmpm": 950.0,
         "projected_savings_percentage": 0.05, "msr_basis_applied": "fixed",
         "savings_status": "above_msr", "aggregate_risk_ratio": 1.2875,
         "cap_factor": CAP_FACTOR, "is_cap_binding": True,
         "risk_adjusted_benchmark_pmpm": 1100.0, "national_growth_projected": 1.05,
         "cap_upper_bound_scenario": 1.08, "is_cap_binding_scenario": True,
         "is_agreement_defaulted": False},
        # Prior year: cap not binding, agreement row defaulted, no scenario.
        {**common, "performance_year": 2025, "period": "2025Q4", "quarter_num": 4,
         "is_current_projection": True, "benchmark_submission_id": "BENCH-T25",
         "quarterly_submission_id": "QTR-T25-4",
         "mean_projected_updated_benchmark_pmpm": 950.0,
         "aco_expenditure_per_capita_pmpm": 1000.0,
         "projected_savings_percentage": -0.0526, "msr_basis_applied": "variable",
         "savings_status": "no_savings", "aggregate_risk_ratio": 0.9,
         "cap_factor": 1.0, "is_cap_binding": False,
         "risk_adjusted_benchmark_pmpm": 900.0, "national_growth_projected": None,
         "cap_upper_bound_scenario": None, "is_cap_binding_scenario": None,
         "is_agreement_defaulted": True},
    ])


def build_duckdb(path: Path, *, with_benchmark: bool, with_surrogate_key: bool = True) -> Path:
    """`with_surrogate_key=False` mimics a `fact_member_months` that predates
    `member_month_sk`; the benchmark fact still carries it."""
    frames = _member_month_frames()
    if with_benchmark:
        frames["fact_benchmark_aco_quarter"] = _aco_quarter_frame()
    else:
        frames.pop("fact_member_month_benchmark")
    if not with_surrogate_key:
        frames["fact_member_months"] = frames["fact_member_months"].drop(
            columns=["member_month_sk"]
        )
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE SCHEMA semantic_layer")
        for name, frame in frames.items():
            con.register("src", frame)
            con.execute(f"CREATE TABLE semantic_layer.{name} AS SELECT * FROM src")
            con.unregister("src")
    finally:
        con.close()
    return path


@pytest.fixture(scope="session")
def full_db_path(tmp_path_factory) -> Path:
    return build_duckdb(tmp_path_factory.mktemp("duck") / "full.duckdb", with_benchmark=True)


@pytest.fixture(scope="session")
def no_benchmark_db_path(tmp_path_factory) -> Path:
    return build_duckdb(
        tmp_path_factory.mktemp("duck") / "no_benchmark.duckdb", with_benchmark=False
    )


@pytest.fixture(scope="session")
def legacy_db_path(tmp_path_factory) -> Path:
    return build_duckdb(
        tmp_path_factory.mktemp("duck") / "legacy.duckdb",
        with_benchmark=True, with_surrogate_key=False,
    )


def _reset_caches() -> None:
    """Settings and the layout's lazy frames are process-level caches."""
    get_settings.cache_clear()
    from dashboards.mssp_aco_dashboard import layout

    for value in vars(layout).values():
        if isinstance(value, LazyFrame):
            value._load.cache_clear()


def _point_at(monkeypatch, db_path: Path | None) -> None:
    if db_path is None:
        # As .env.example ships: queries skipped, DuckDB the nominal target.
        monkeypatch.setenv("LOAD_DATA", "false")
        monkeypatch.setenv("DATA_WAREHOUSE_TYPE", "duckdb")
    else:
        monkeypatch.setenv("LOAD_DATA", "true")
        monkeypatch.setenv("DATA_WAREHOUSE_TYPE", "duckdb")
        monkeypatch.setenv("DUCKDB_DATABASE", str(db_path))
        monkeypatch.setenv("SCHEMA_PREPEND_NAME", "NULL")
    _reset_caches()


@pytest.fixture
def full_db(monkeypatch, full_db_path):
    _point_at(monkeypatch, full_db_path)
    yield full_db_path
    _reset_caches()


@pytest.fixture
def no_benchmark_db(monkeypatch, no_benchmark_db_path):
    _point_at(monkeypatch, no_benchmark_db_path)
    yield no_benchmark_db_path
    _reset_caches()


@pytest.fixture
def legacy_db(monkeypatch, legacy_db_path):
    _point_at(monkeypatch, legacy_db_path)
    yield legacy_db_path
    _reset_caches()


@pytest.fixture
def no_load_data(monkeypatch):
    _point_at(monkeypatch, None)
    yield
    _reset_caches()
