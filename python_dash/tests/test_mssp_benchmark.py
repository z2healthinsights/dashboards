"""MSSP ACO dashboard: benchmark facts beside actual spend.

Runs the query and aggregation functions against the synthetic DuckDB in
conftest.py. Expected figures are worked in the conftest docstring.
"""

from __future__ import annotations

import math

import dash_bootstrap_components as dbc
import pytest
from dash import dash_table

from dashboards.mssp_aco_dashboard import benchmark, layout, queries

PRACTICE = "payer_attributed_provider_practice"
PROVIDER = "payer_attributed_provider"


def _row(df, group_col, value):
    hit = df[df[group_col] == value]
    assert len(hit) == 1, f"{value!r} not found once in {df[group_col].tolist()}"
    return hit.iloc[0]


def _find(component, cls):
    """Depth-first search of a Dash component tree for instances of cls."""
    found = []
    stack = [component]
    while stack:
        node = stack.pop()
        if isinstance(node, (list, tuple)):  # callbacks may return a list of children
            stack.extend(node)
            continue
        if isinstance(node, cls):
            found.append(node)
        children = getattr(node, "children", None)
        if children is not None and not isinstance(children, (str, int, float)):
            stack.append(children)
    return found


# -- queries -----------------------------------------------------------------

def test_member_months_do_not_depend_on_the_surrogate_key(full_db):
    mm = queries.load_member_months()
    assert len(mm) == 8
    assert "member_month_sk" not in mm.columns
    assert {"person_id", "year_month"} <= set(mm.columns)


def test_member_month_benchmark_joins_one_to_one_on_the_natural_key(full_db):
    bench = queries.load_member_month_benchmark()
    assert len(bench) == 8
    # The fact carries the surrogate key for reference; the join uses the natural key.
    assert bench["member_month_sk"].is_unique
    assert not bench.duplicated(["person_id", "year_month"]).any()
    joined = benchmark.merge_benchmark(queries.load_member_months(), bench)
    assert len(joined) == 8
    assert joined["flat_benchmark_pmpm"].notna().all()
    # Each member-month picked up its own row, not a neighbour's.
    p1_jan = joined[(joined["person_id"] == "P1") & (joined["year_month"] == "202601")]
    assert p1_jan["risk_adjusted_benchmark_pmpm_capped"].item() == pytest.approx(1440.0)
    # P2 has no score and P4 no enrollment type: their risk-adjusted rate is NULL.
    assert joined["risk_adjusted_benchmark_pmpm_capped"].isna().sum() == 4


def test_benchmark_renders_when_member_months_lack_the_surrogate_key(legacy_db):
    mm = queries.load_member_months()
    assert len(mm) == 8  # the existing view is intact
    joined = benchmark.merge_benchmark(mm, queries.load_member_month_benchmark())
    assert joined["flat_benchmark_pmpm"].notna().all()
    page = layout.build_layout()
    assert "BENCH-T26" in str(page)
    kpis, practice_section = layout._render_program_benchmark("flat")
    assert len(_find(kpis, dbc.Card)) == 5
    table = _find(practice_section, dash_table.DataTable)[0]
    by_practice = {r["Practice"]: r for r in table.data}
    assert by_practice["Practice A"]["Benchmark PMPM"] == pytest.approx(1000.0)
    assert by_practice["Practice A"]["Variance"] == pytest.approx(50.0)


def test_absent_benchmark_tables_return_empty_frames(no_benchmark_db):
    bench = queries.load_member_month_benchmark()
    aco = queries.load_benchmark_aco_quarter()
    assert bench.empty and aco.empty
    assert "risk_adjusted_benchmark_pmpm_capped" in bench.columns
    assert "is_current_projection" in aco.columns
    # The existing member-month load is untouched by the missing facts.
    assert len(queries.load_member_months()) == 8


# -- rollups -----------------------------------------------------------------

@pytest.fixture
def joined(full_db):
    return benchmark.merge_benchmark(
        queries.load_member_months(), queries.load_member_month_benchmark()
    )


def test_practice_rollup_flat_rate(joined):
    out = benchmark.rollup(joined, PRACTICE, "flat")
    a = _row(out, PRACTICE, "Practice A")
    assert a["benchmark_member_months"] == 4
    assert a["excluded_member_months"] == 0
    assert a["actual_pmpm"] == pytest.approx(1050.0)
    assert a["benchmark_pmpm"] == pytest.approx(1000.0)
    assert a["variance_pmpm"] == pytest.approx(50.0)  # above benchmark: positive

    b = _row(out, PRACTICE, "Practice B")
    assert b["actual_pmpm"] == pytest.approx(400.0)
    assert b["variance_pmpm"] == pytest.approx(-600.0)


def test_variance_sign_flips_with_the_selected_rate(joined):
    flat = _row(benchmark.rollup(joined, PRACTICE, "flat"), PRACTICE, "Practice A")
    by_type = _row(
        benchmark.rollup(joined, PRACTICE, "enrollment_type"), PRACTICE, "Practice A"
    )
    assert flat["variance_pmpm"] > 0
    assert by_type["benchmark_pmpm"] == pytest.approx(1200.0)
    assert by_type["variance_pmpm"] == pytest.approx(-150.0)


def test_null_rates_are_excluded_from_both_sides(joined):
    out = benchmark.rollup(joined, PRACTICE, "risk_adjusted_capped")
    a = _row(out, PRACTICE, "Practice A")
    # P2 (no score) drops out of the benchmark side and of the matched actual.
    assert a["member_months"] == 4
    assert a["benchmark_member_months"] == 2
    assert a["excluded_member_months"] == 2
    assert a["actual_pmpm"] == pytest.approx(1600.0)
    assert a["benchmark_pmpm"] == pytest.approx(1440.0)
    assert a["variance_pmpm"] == pytest.approx(160.0)

    b = _row(out, PRACTICE, "Practice B")
    assert b["excluded_member_months"] == 2  # P4: no enrollment type
    assert b["benchmark_pmpm"] == pytest.approx(320.0)
    assert b["variance_pmpm"] == pytest.approx(380.0)


def test_uncapped_rate_is_available(joined):
    out = benchmark.rollup(joined, PRACTICE, "risk_adjusted")
    a = _row(out, PRACTICE, "Practice A")
    assert a["benchmark_pmpm"] == pytest.approx(1800.0)
    assert a["variance_pmpm"] == pytest.approx(-200.0)


def test_provider_rollup(joined):
    out = benchmark.rollup(joined, PROVIDER, "enrollment_type")
    three = _row(out, PROVIDER, "Dr Three")
    assert three["benchmark_member_months"] == 0
    assert three["excluded_member_months"] == 2
    assert math.isnan(three["benchmark_pmpm"])
    assert math.isnan(three["variance_pmpm"])


def test_totals(joined):
    t = benchmark.totals(joined, "enrollment_type")
    assert t["member_months"] == 8
    assert t["excluded_member_months"] == 2
    assert t["actual_pmpm"] == pytest.approx(5600 / 6)
    assert t["benchmark_pmpm"] == pytest.approx(6400 / 6)
    assert t["variance_pmpm"] == pytest.approx(-800 / 6)


def test_rollup_of_empty_benchmark_is_empty(full_db):
    mm = queries.load_member_months()
    empty = benchmark.merge_benchmark(mm, queries.load_member_month_benchmark().iloc[0:0])
    assert len(empty) == len(mm)
    out = benchmark.rollup(empty, PRACTICE, "flat")
    assert (out["benchmark_member_months"] == 0).all()
    assert out["benchmark_pmpm"].isna().all()


# -- ACO panel ----------------------------------------------------------------

def test_current_projections_pick_one_row_per_year(full_db):
    aco = queries.load_benchmark_aco_quarter()
    assert len(aco) == 3
    current = benchmark.current_projections(aco)
    assert current["performance_year"].tolist() == [2025, 2026]
    assert current["period"].tolist() == ["2025Q4", "2026Q2"]
    py26 = current.iloc[1]
    assert bool(py26["is_cap_binding"]) is True
    assert py26["cap_factor"] == pytest.approx(0.8)
    assert py26["benchmark_submission_id"] == "BENCH-T26"
    py25 = current.iloc[0]
    assert bool(py25["is_cap_binding"]) is False
    assert bool(py25["is_agreement_defaulted"]) is True


# -- layout -------------------------------------------------------------------

def test_layout_builds_with_benchmark_facts(full_db):
    page = layout.build_layout()
    radios = _find(page, dbc.RadioItems)
    assert any(r.id == "mssp-benchmark-rate" for r in radios)
    # ACO panel: one card per current-projection year, labelled by delivery.
    text = str(page)
    assert "2026Q2" in text and "BENCH-T26" in text
    assert "2025Q4" in text and "BENCH-T25" in text
    assert "2026Q1" not in text  # not the current projection


def test_program_callback_renders_kpis_and_practice_table(full_db):
    kpis, practice_section = layout._render_program_benchmark("flat")
    cards = _find(kpis, dbc.Card)
    assert len(cards) == 5
    tables = _find(practice_section, dash_table.DataTable)
    assert len(tables) == 1
    cols = [c["name"] for c in tables[0].columns]
    assert "Benchmark PMPM" in cols and "Variance" in cols and "Excluded MM" in cols
    by_practice = {r["Practice"]: r for r in tables[0].data}
    assert by_practice["Practice A"]["Variance"] == pytest.approx(50.0)
    assert by_practice["Practice B"]["Variance"] == pytest.approx(-600.0)


def test_practice_callback_shows_provider_benchmark(full_db):
    out = layout._render_practice("Practice A", "risk_adjusted_capped")
    tables = _find(out, dash_table.DataTable)
    assert len(tables) == 1
    by_provider = {r["Provider"]: r for r in tables[0].data}
    assert by_provider["Dr One"]["Benchmark PMPM"] == pytest.approx(1440.0)
    assert by_provider["Dr One"]["Variance"] == pytest.approx(160.0)
    assert by_provider["Dr One"]["Excluded MM"] == 2


def test_provider_callback_shows_benchmark_cards(full_db):
    out = layout._render_provider("Dr Two", "enrollment_type")
    labels = [c.children[0].children for c in _find(out, dbc.CardBody)]
    assert any("Benchmark PMPM" in str(lbl) for lbl in labels)
    assert any("Variance" in str(lbl) for lbl in labels)


def test_layout_without_benchmark_facts_shows_alert_and_keeps_the_rest(no_benchmark_db):
    page = layout.build_layout()
    assert page is not None
    kpis, practice_section = layout._render_program_benchmark("flat")
    assert _find(kpis, dbc.Alert), "benchmark KPI row should fall back to the alert"
    tables = _find(practice_section, dash_table.DataTable)
    assert len(tables) == 1
    cols = [c["name"] for c in tables[0].columns]
    assert "PMPM" in cols and "Benchmark PMPM" not in cols
    assert "ACO-TEST" not in str(page)

    out = layout._render_practice("Practice A", "flat")
    provider_cols = [c["name"] for c in _find(out, dash_table.DataTable)[0].columns]
    assert "Benchmark PMPM" not in provider_cols


def test_layout_builds_with_load_data_false(no_load_data):
    page = layout.build_layout()
    assert page is not None
    kpis, practice_section = layout._render_program_benchmark("flat")
    assert _find(kpis, dbc.Alert)
