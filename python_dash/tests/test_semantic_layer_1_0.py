"""Semantic layer 1.0 compatibility for every dashboard's queries.

Semantic layer 1.0 retired `dim_condition`, `fact_member_condition_bridge` and
`fact_expected_values`, and deprecated `member_month_sk` (person and month,
not unique on 1.0 member months; join on `member_month_id`).

Two checks:

- `test_no_query_reads_a_retired_relation` runs every loader of every
  dashboard with `run_query` stubbed and fails if any SQL names a retired
  relation or column. It needs no warehouse.
- `test_page_queries_run_against_a_v1_build` runs each affected page's
  loaders against a real 1.0 DuckDB and fails on any query error in the
  `semantic_layer` schema. It runs only when `TUVA_V1_DUCKDB` points at one,
  for example the cms_mssp_connector `scripts/dbt-local build` output.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import re
from pathlib import Path

import pandas as pd
import pytest

from tuva_dash import conditions
from tuva_dash.config import get_settings
from tuva_dash.lazy import LazyFrame

ALL_PAGES = [
    "cost_and_utilization", "cost_drivers", "dqi_analytics", "mssp_aco_dashboard",
    "population_health", "quality_measures", "risk_adjust_benchmark", "semantic_layer",
]
# The pages TUVA-128 ported: each read a retired relation or column.
PORTED_PAGES = [
    "cost_and_utilization", "cost_drivers", "mssp_aco_dashboard",
    "population_health", "semantic_layer",
]
RETIRED = re.compile(
    r"\b(dim_condition|fact_member_condition_bridge|fact_expected_values|member_month_sk)\b",
    re.IGNORECASE,
)


def _loaders(page: str):
    module = importlib.import_module(f"dashboards.{page}.queries")
    for name, fn in inspect.getmembers(module, inspect.isfunction):
        if name.startswith("load_") and fn.__module__ == module.__name__:
            yield module, name, fn


def _call(fn):
    # The model browser's sampler is the only loader that takes arguments.
    if "table_name" in inspect.signature(fn).parameters:
        return fn("fact_member_months")
    return fn()


@pytest.mark.parametrize("page", ALL_PAGES)
def test_no_query_reads_a_retired_relation(page, monkeypatch, full_db):
    issued: list[str] = []

    def capture(sql, *args, columns=None, **kwargs):
        issued.append(sql)
        return pd.DataFrame(columns=columns or [])

    loaders = list(_loaders(page))
    assert loaders
    for module, _name, fn in loaders:
        monkeypatch.setattr(module, "run_query", capture)
        _call(fn)
    assert issued
    offending = [sql for sql in issued if RETIRED.search(sql)]
    assert not offending, offending


def test_model_browser_maps_no_retired_relation():
    from dashboards.semantic_layer import layout

    named = [part for rel in layout._RELATIONSHIPS for part in rel]
    assert not [n for n in named if RETIRED.search(n)]


def test_conditions_come_from_cms_hcc_disease_factors(full_db):
    from dashboards.cost_drivers import queries
    from tests.fixture_data import CONDITIONS

    got = queries.load_member_conditions()
    assert list(got.columns) == conditions.COLUMNS
    expected = {(p, c) for p, cs in CONDITIONS.items() for c in cs}
    # The demographic factor on P1 is not a condition.
    assert set(map(tuple, got[["person_id", "condition"]].values)) == expected


V1_DUCKDB = os.environ.get("TUVA_V1_DUCKDB")


@pytest.fixture
def v1_db(monkeypatch):
    if not V1_DUCKDB or not Path(V1_DUCKDB).exists():
        pytest.skip("set TUVA_V1_DUCKDB to a semantic layer 1.0 DuckDB build")
    monkeypatch.setenv("LOAD_DATA", "true")
    monkeypatch.setenv("DATA_WAREHOUSE_TYPE", "duckdb")
    monkeypatch.setenv("DUCKDB_DATABASE", V1_DUCKDB)
    monkeypatch.setenv("SCHEMA_PREPEND_NAME", os.environ.get("TUVA_V1_SCHEMA_PREPEND", "NULL"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _clear_lazy_frames(layout) -> None:
    for value in vars(layout).values():
        if isinstance(value, LazyFrame):
            value._load.cache_clear()


@pytest.mark.parametrize("page", PORTED_PAGES)
def test_page_queries_run_against_a_v1_build(page, v1_db, caplog):
    caplog.set_level(logging.WARNING)
    for _module, _name, fn in _loaders(page):
        _call(fn)
    failures = [r.getMessage() for r in caplog.records if "query failed" in r.getMessage()]
    assert not failures, failures
    layout = importlib.import_module(f"dashboards.{page}.layout")
    _clear_lazy_frames(layout)
    try:
        assert layout.build_layout() is not None
    finally:
        _clear_lazy_frames(layout)
