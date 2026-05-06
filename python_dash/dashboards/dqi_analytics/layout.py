"""Layout for the DQI Analytics dashboard."""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import dash_table, dcc, html

from tuva_dash.components import kpi_card, kpi_row, no_data_message, page_shell

from . import queries

# Atomic-flag columns on data_quality.medical_claim_claim_flags. Each is an
# integer count of failing rows for that claim. Sum across columns gives the
# total atomic failures per claim.
_CLAIM_FLAG_COLS = [
    "claim_type_count_ne_one_per_claim",
    "multiple_person_ids_per_claim",
    "admission_date_has_multiple_values_per_inpatient_claim",
    "discharge_date_has_multiple_values_per_inpatient_claim",
    "bill_type_code_count_ne_one_for_institutional_claim",
    "drg_code_count_ne_one_for_acute_inpatient_claim",
    "no_matching_eligibility_span",
]


def _safe_pct(num: float, denom: float) -> str:
    if not denom:
        return "—"
    return f"{(num / denom) * 100:.1f}%"


def _kpis(claim_flags: pd.DataFrame, structural: pd.DataFrame, logical: pd.DataFrame) -> dbc.Row:
    if claim_flags.empty and structural.empty and logical.empty:
        return kpi_row([
            kpi_card("Claims Checked", "0"),
            kpi_card("Atomic Pass Rate", "—"),
            kpi_card("Logical Tests Passed", "—"),
            kpi_card("Tables With Data", "0"),
        ])

    total_claims = len(claim_flags)
    flagged = (
        claim_flags[_CLAIM_FLAG_COLS].fillna(0).sum(axis=1).gt(0).sum()
        if not claim_flags.empty else 0
    )
    pass_rate = _safe_pct(total_claims - flagged, total_claims)

    logical_pass_rate = _safe_pct(
        (logical["test_result"] == 0).sum() if not logical.empty else 0,
        len(logical),
    )

    tables_with_data = (
        (structural["row_count"].fillna(0) > 0).sum()
        if not structural.empty else 0
    )

    return kpi_row([
        kpi_card("Claims Checked", f"{total_claims:,}"),
        kpi_card("Atomic Pass Rate", pass_rate, sub="claims with no atomic flags"),
        kpi_card("Logical Tests Passed", logical_pass_rate),
        kpi_card("Tables With Data", f"{int(tables_with_data)}"),
    ])


def _atomic_flag_chart(claim_flags: pd.DataFrame):
    if claim_flags.empty:
        return no_data_message()
    series = claim_flags[_CLAIM_FLAG_COLS].fillna(0).gt(0).sum()
    counts = (
        pd.DataFrame({"check": series.index, "flagged_claims": series.values})
        .sort_values("flagged_claims", ascending=True)
    )
    fig = px.bar(
        counts,
        x="flagged_claims",
        y="check",
        orientation="h",
        title="Claims failing each atomic check",
    )
    fig.update_layout(height=420, yaxis_title="", xaxis_title="claims with flag")
    return dcc.Graph(figure=fig)


def _data_source_breakdown(claim_flags: pd.DataFrame):
    if claim_flags.empty or "data_source" not in claim_flags.columns:
        return no_data_message()
    df = claim_flags.copy()
    df["any_flag"] = df[_CLAIM_FLAG_COLS].fillna(0).sum(axis=1).gt(0)
    by_src = (
        df.groupby("data_source")
        .agg(claims=("claim_id", "count"), flagged=("any_flag", "sum"))
        .reset_index()
    )
    by_src["pass_rate"] = (1 - by_src["flagged"] / by_src["claims"]).round(3)
    fig = px.bar(
        by_src,
        x="data_source",
        y="pass_rate",
        title="Atomic pass rate by data source",
        text="claims",
    )
    fig.update_layout(height=400, yaxis_tickformat=".0%", xaxis_title="")
    return dcc.Graph(figure=fig)


def _logical_grid(logical: pd.DataFrame):
    if logical.empty:
        return no_data_message()
    pivot = (
        logical.assign(passed=lambda d: (d["test_result"] == 0).astype(int))
        .pivot_table(
            index="table",
            columns="test_name",
            values="passed",
            aggfunc="min",
        )
        .reset_index()
    )
    return dash_table.DataTable(
        data=pivot.to_dict("records"),
        columns=[{"name": c, "id": c} for c in pivot.columns],
        page_size=15,
        sort_action="native",
        filter_action="native",
        style_cell={"fontSize": 12, "padding": "4px"},
        style_header={"fontWeight": "bold"},
    )


def _structural_table(structural: pd.DataFrame):
    if structural.empty:
        return no_data_message()
    return dash_table.DataTable(
        data=structural.to_dict("records"),
        columns=[{"name": c, "id": c} for c in structural.columns],
        page_size=15,
        sort_action="native",
        filter_action="native",
        style_cell={"fontSize": 12},
    )


def _data_marts_chart(marts: pd.DataFrame):
    if marts.empty:
        return no_data_message()
    fig = px.bar(
        marts.sort_values("row_count", ascending=True),
        x="row_count",
        y="data_mart",
        orientation="h",
        title="Analytical data mart row counts",
    )
    fig.update_layout(height=420, yaxis_title="")
    return dcc.Graph(figure=fig)


def build_layout() -> html.Div:
    claim_flags = queries.load_claim_flags()
    structural = queries.load_structural()
    logical = queries.load_logical()
    marts = queries.load_data_marts()

    body = dbc.Tabs(
        [
            dbc.Tab(
                label="Claims Atomic Data Checks",
                children=html.Div(
                    [
                        _kpis(claim_flags, structural, logical),
                        dbc.Row(
                            [
                                dbc.Col(_atomic_flag_chart(claim_flags), md=7),
                                dbc.Col(_data_source_breakdown(claim_flags), md=5),
                            ],
                            className="mb-3",
                        ),
                    ],
                    className="pt-3",
                ),
            ),
            dbc.Tab(
                label="Logical Tests",
                children=html.Div(
                    [
                        html.P(
                            "Per-table logical tests from data_quality.logical. "
                            "0 = passing.",
                            className="text-muted",
                        ),
                        _logical_grid(logical),
                    ],
                    className="pt-3",
                ),
            ),
            dbc.Tab(
                label="Structural & Marts",
                children=html.Div(
                    [
                        dbc.Row(
                            [
                                dbc.Col(_data_marts_chart(marts), md=6),
                                dbc.Col(
                                    [
                                        html.H6("Structural test results"),
                                        _structural_table(structural),
                                    ],
                                    md=6,
                                ),
                            ]
                        ),
                    ],
                    className="pt-3",
                ),
            ),
        ]
    )

    return page_shell(
        title="DQI Analytics",
        subtitle="Tuva Data Quality Index — atomic claim flags, logical tests, structural checks.",
        body=body,
        tuva_tables=[
            "data_quality.medical_claim_claim_flags",
            "data_quality.logical",
            "data_quality.structural",
            "data_quality.analytical_data_marts",
        ],
    )
