"""Layout for the MSSP ACO Performance dashboard.

Mirrors the 6 PBI pages: Program Performance Summary, Practice, Provider,
Patient, Quality Measure Detail, HCC Gaps Detail.

The Program Performance and Practice pages also set actual PMPM against the
MSSP benchmark from the two semantic layer benchmark facts (see
`benchmark.py`). A rate selector above the tabs switches the benchmark
between the flat, enrollment-type and risk-adjusted rates.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Input, Output, callback, dash_table, dcc, html

from tuva_dash.components import kpi_card, kpi_row, no_data_message, page_shell
from tuva_dash.config import get_settings
from tuva_dash.lazy import LazyFrame

from . import benchmark, queries

# Lazy module-level cache. Importing this module registers callbacks without
# pulling every MSSP table from Snowflake during app startup.
_MM = LazyFrame(queries.load_member_months)
_DIM_MM = LazyFrame(queries.load_dim_member_months)
_MEMBERS = LazyFrame(queries.load_members)
_CONDITIONS = LazyFrame(queries.load_member_conditions)
_HCC_GAPS = LazyFrame(queries.load_hcc_gaps)
_ENCOUNTERS = LazyFrame(queries.load_encounters)
_PQI_RATE = LazyFrame(queries.load_pqi_rate)
_PQI_DENOM = LazyFrame(queries.load_pqi_denom)
_BENCH = LazyFrame(queries.load_member_month_benchmark)
_ACO_QUARTERS = LazyFrame(queries.load_benchmark_aco_quarter)
# Member months with the benchmark rates beside them: the same rows as _MM,
# with NaN rates wherever the benchmark fact is absent or does not cover.
_BENCH_MM = LazyFrame(lambda: benchmark.merge_benchmark(_MM.frame(), _BENCH.frame()))

QUALITY_TARGET = 0.80

_SAVINGS_STATUS = {
    "above_msr": ("Savings above MSR", "success"),
    "below_msr": ("Savings below MSR", "warning"),
    "no_savings": ("No savings", "danger"),
}

_ROLLUP_LABELS = {
    "practice": "Practice", "provider": "Provider", "members": "Members",
    "member_months": "Member Months", "paid": "Paid", "pmpm": "PMPM",
    "actual_pmpm": "Actual PMPM", "benchmark_pmpm": "Benchmark PMPM",
    "variance_pmpm": "Variance", "excluded_member_months": "Excluded MM",
    "avg_risk": "Avg Risk",
}
_BENCHMARK_ROLLUP_COLUMNS = ["actual_pmpm", "benchmark_pmpm", "variance_pmpm",
                             "excluded_member_months"]


# -- formatting helpers ------------------------------------------------------

def _money(v) -> str:
    return "—" if pd.isna(v) else f"${v:,.0f}"


def _pmpm(v) -> str:
    return "—" if pd.isna(v) else f"${v:,.2f}"


def _signed_pmpm(v) -> str:
    return "—" if pd.isna(v) else f"{'+' if v >= 0 else '-'}${abs(v):,.2f}"


def _pct(v) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.1f}%"


def _ratio(v) -> str:
    return "—" if pd.isna(v) else f"{v:.3f}"


def _has_benchmark() -> bool:
    return not _BENCH.empty


def _benchmark_missing_message() -> dbc.Alert:
    """Context-aware alert for the benchmark elements.

    With LOAD_DATA=false the shared message tells the user how to enable
    queries. With LOAD_DATA=true an empty benchmark frame means the two
    benchmark facts are not in the warehouse, which the standard Tuva
    build does not produce, so say that instead of blaming LOAD_DATA.
    """
    if not get_settings().load_data:
        return no_data_message()
    return dbc.Alert(
        [
            html.Strong("Benchmark facts not loaded. "),
            "This view reads ",
            html.Code("semantic_layer.fact_member_month_benchmark"),
            " and ",
            html.Code("semantic_layer.fact_benchmark_aco_quarter"),
            ", which the MSSP benchmark models build beside the Tuva semantic "
            "layer. Build those models to populate the benchmark comparison; "
            "the rest of this dashboard is unaffected.",
        ],
        color="info",
    )


# -- shared rollup helpers ---------------------------------------------------

def _quality_meeting_target_pct() -> float:
    """Headline quality figure shared across pages."""
    if _PQI_RATE.empty:
        return 0.0
    rate = _PQI_RATE.copy()
    rate["overall"] = rate["num_count"] / rate["denom_count"].where(rate["denom_count"] != 0)
    return float((rate["overall"].fillna(0) >= QUALITY_TARGET).mean())


def _attribution_label(col: str) -> str:
    return col.replace("_", " ").title()


def _rollup(df: pd.DataFrame, group_col: str, name_col: str,
            rate_key: str | None) -> pd.DataFrame:
    """Members, member-months, paid, PMPM and risk by group, plus — when a
    rate is selected and the benchmark fact is present — actual against the
    selected benchmark over the member-months that carry that rate."""
    g = (
        df.groupby(group_col, dropna=False)
        .agg(
            members=("person_id", "nunique"),
            member_months=("member_months", "sum"),
            paid=("total_paid", "sum"),
            avg_risk=("normalized_risk_score", "mean"),
        ).reset_index()
    )
    g[name_col] = g[group_col].fillna(benchmark.UNATTRIBUTED)
    g["pmpm"] = g["paid"] / g["member_months"].where(g["member_months"] != 0)
    cols = [name_col, "members", "member_months", "paid", "pmpm"]
    if rate_key is not None and _has_benchmark():
        b = benchmark.rollup(df, group_col, rate_key).rename(columns={group_col: name_col})
        g = g.merge(b[[name_col, *_BENCHMARK_ROLLUP_COLUMNS]], on=name_col, how="left")
        cols += _BENCHMARK_ROLLUP_COLUMNS
    return g[[*cols, "avg_risk"]]


def _practice_rollup(rate_key: str | None = None) -> pd.DataFrame:
    if _MM.empty:
        return pd.DataFrame()
    return _rollup(_BENCH_MM.frame(), "payer_attributed_provider_practice", "practice",
                   rate_key)


def _provider_rollup(practice: str | None = None,
                     rate_key: str | None = None) -> pd.DataFrame:
    if _MM.empty:
        return pd.DataFrame()
    df = _BENCH_MM.frame()
    if practice and practice != "(all)":
        df = df[df["payer_attributed_provider_practice"].fillna(benchmark.UNATTRIBUTED)
                == practice]
    return _rollup(df, "payer_attributed_provider", "provider", rate_key)


def _rollup_table(rollup: pd.DataFrame) -> dash_table.DataTable:
    disp = rollup.copy()
    disp["paid"] = disp["paid"].round(0)
    for col in ("pmpm", "avg_risk", "actual_pmpm", "benchmark_pmpm", "variance_pmpm"):
        if col in disp.columns:
            disp[col] = disp[col].round(2)
    if "excluded_member_months" in disp.columns:
        disp["excluded_member_months"] = disp["excluded_member_months"].astype(int)
    disp = disp.rename(columns=_ROLLUP_LABELS)
    return dash_table.DataTable(
        data=disp.to_dict("records"),
        columns=[{"name": c, "id": c} for c in disp.columns],
        page_size=15, sort_action="native",
        style_cell={"fontSize": 12, "padding": "4px"},
        style_header={"fontWeight": "bold"},
        style_table={"overflowX": "auto"},
    )


def _pmpm_bar(rollup: pd.DataFrame, name_col: str, title: str, rate_label: str | None):
    """Horizontal PMPM bars; grouped actual-vs-benchmark when a rate is shown."""
    if rate_label is None or "benchmark_pmpm" not in rollup.columns:
        fig = px.bar(rollup.sort_values("pmpm"), x="pmpm", y=name_col,
                     orientation="h", title=title)
    else:
        long = rollup.sort_values("actual_pmpm").melt(
            id_vars=[name_col], value_vars=["actual_pmpm", "benchmark_pmpm"],
            var_name="measure", value_name="value",
        )
        long["measure"] = long["measure"].map({
            "actual_pmpm": "Actual", "benchmark_pmpm": f"Benchmark ({rate_label})",
        })
        fig = px.bar(long, x="value", y=name_col, color="measure", orientation="h",
                     barmode="group", title=title)
        fig.update_layout(legend_title_text="", legend=dict(orientation="h", y=-0.15))
    fig.update_layout(height=320, xaxis_tickprefix="$", xaxis_tickformat=",",
                      yaxis_title="", xaxis_title="")
    return fig


def _rollup_section(rollup: pd.DataFrame, name_col: str, table_title: str,
                    bar_title: str, rate_key: str | None):
    """Bar chart beside the rollup table, with the benchmark note when shown."""
    if rollup.empty:
        return no_data_message()
    label = benchmark.rate(rate_key).label if rate_key is not None else None
    note = []
    if label is not None:
        note = [html.P(
            f"Actual PMPM, Benchmark PMPM and Variance are over the member-months "
            f"that carry a {label.lower()} benchmark rate; Excluded MM counts those "
            f"without one. Variance is actual minus benchmark, so positive means "
            f"spending above the benchmark.",
            className="text-muted small mt-2 mb-0",
        )]
    return dbc.Row([
        dbc.Col(dcc.Graph(figure=_pmpm_bar(rollup, name_col, bar_title, label)), md=6),
        dbc.Col([html.H5(table_title), _rollup_table(rollup), *note], md=6),
    ])


def _benchmark_kpis(df: pd.DataFrame, rate_key: str | None) -> dbc.Row:
    """Actual PMPM, the three benchmark rates, and the variance to the selected one."""
    selected = benchmark.rate(rate_key)
    sel = benchmark.totals(df, selected.key)
    flat = benchmark.totals(df, "flat")
    by_type = benchmark.totals(df, "enrollment_type")
    ra_key = "risk_adjusted" if selected.key == "risk_adjusted" else "risk_adjusted_capped"
    ra = benchmark.totals(df, ra_key)
    variance = sel["variance_pmpm"]
    if pd.isna(variance):
        variance_color = "secondary"
    else:
        variance_color = "danger" if variance > 0 else "success"
    return kpi_row([
        kpi_card("Actual PMPM", _pmpm(sel["actual_pmpm"]),
                 sub=f"{int(sel['benchmark_member_months']):,} member-months with a "
                     f"{selected.label.lower()} rate"),
        kpi_card("Flat Benchmark PMPM", _pmpm(flat["benchmark_pmpm"])),
        kpi_card("Enrollment-Type Benchmark PMPM", _pmpm(by_type["benchmark_pmpm"])),
        kpi_card("Risk-Adjusted Benchmark PMPM", _pmpm(ra["benchmark_pmpm"]),
                 sub="uncapped" if ra_key == "risk_adjusted"
                 else "capped by the aggregate risk ratio cap"),
        kpi_card(f"Variance vs {selected.label}", _signed_pmpm(variance),
                 sub=f"actual minus benchmark; "
                     f"{int(sel['excluded_member_months']):,} member-months excluded",
                 color=variance_color),
    ])


# -- ACO benchmark panel ------------------------------------------------------

def _text(value) -> str | None:
    """A nullable string column, whether NULL came back as None or NaN."""
    return value if isinstance(value, str) and value else None


def _aco_year_card(row: pd.Series) -> dbc.Card:
    status = _text(row["savings_status"])
    status_label, status_color = _SAVINGS_STATUS.get(status, (status or "—", "secondary"))
    binding = benchmark.nullable_bool(row["is_cap_binding"])
    if binding is None:
        cap_text = "—"
    elif binding:
        cap_text = f"Yes (factor {_ratio(row['cap_factor'])})"
    else:
        cap_text = "No"
    basis = _text(row["msr_basis_applied"])
    msr_text = _pct(row["estimated_msr"]) + (f" ({basis})" if basis else "")

    lines = [
        ("Benchmark PMPM", _pmpm(row["mean_projected_updated_benchmark_pmpm"])),
        ("Expenditure PMPM", _pmpm(row["aco_expenditure_per_capita_pmpm"])),
        ("Projected savings", _pct(row["projected_savings_percentage"])),
        ("MSR", msr_text),
        ("Savings status", dbc.Badge(status_label, color=status_color)),
        ("Aggregate risk ratio", _ratio(row["aggregate_risk_ratio"])),
        ("Cap upper bound", _ratio(row["cap_upper_bound"])),
        ("Cap binds", cap_text),
        ("Risk-adjusted benchmark PMPM", _pmpm(row["risk_adjusted_benchmark_pmpm"])),
    ]
    body = html.Table(
        html.Tbody([
            html.Tr([html.Td(k, className="text-muted small pe-3"),
                     html.Td(v, className="small fw-semibold")])
            for k, v in lines
        ]),
        className="table table-sm table-borderless mb-0",
    )
    parts = [
        dbc.CardHeader([
            html.Strong(f"PY {int(row['performance_year'])} — {row['period']}"),
            html.Br(),
            html.Small(f"Benchmark delivery {row['benchmark_submission_id']}",
                       className="text-muted"),
        ]),
        dbc.CardBody(body),
    ]
    if benchmark.nullable_bool(row["is_agreement_defaulted"]):
        parts.append(dbc.CardFooter(html.Small(
            "Agreement row defaulted: the prospective trend behind this "
            "projection was defaulted, so these figures rest on that default.",
            className="text-warning",
        )))
    return dbc.Card(parts, className="h-100")


def _aco_panel():
    """One card per performance year from the current-projection rows."""
    if _ACO_QUARTERS.empty:
        return _benchmark_missing_message()
    current = benchmark.current_projections(_ACO_QUARTERS.frame())
    if current.empty:
        return dbc.Alert("No current-projection rows in fact_benchmark_aco_quarter.",
                         color="info")
    return dbc.Row([
        dbc.Col(_aco_year_card(row), md=6, xl=4, className="mb-3")
        for _, row in current.iterrows()
    ])


# -- Program Performance Summary --------------------------------------------

def _program_summary_tab() -> html.Div:
    if _MM.empty:
        return html.Div([no_data_message()], className="pt-3")

    members_n = _MM["person_id"].nunique()
    total_mm = float(_MM["member_months"].sum()) or 1.0
    total_paid = float(_MM["total_paid"].sum())
    avg_risk = float(_MM["normalized_risk_score"].mean())
    quality_pct = _quality_meeting_target_pct()

    cards = kpi_row([
        kpi_card("Attributed Members", f"{members_n:,}"),
        kpi_card("Member Months", f"{int(total_mm):,}"),
        kpi_card("Total Paid", _money(total_paid)),
        kpi_card("PMPM", _pmpm(total_paid / total_mm)),
        kpi_card("Avg Normalized Risk",
                 f"{avg_risk:.2f}" if avg_risk == avg_risk else "—"),
        kpi_card("Quality Meeting Target", _pct(quality_pct)),
    ])

    return html.Div([
        cards,
        html.H5("Benchmark comparison"),
        html.Div(id="mssp-benchmark-kpis"),
        html.Div(id="mssp-practice-rollup"),
        html.H5("ACO benchmark projections", className="mt-3"),
        _aco_panel(),
    ], className="pt-3")


@callback(
    Output("mssp-benchmark-kpis", "children"),
    Output("mssp-practice-rollup", "children"),
    Input("mssp-benchmark-rate", "value"),
)
def _render_program_benchmark(rate_key):
    """Benchmark KPI row and the practice rollup, both on the selected rate.

    Without the benchmark fact the KPI row is the benchmark alert and the
    practice rollup is the plain PMPM view it always was.
    """
    has = _has_benchmark()
    rate_key = rate_key if has else None
    kpis = _benchmark_kpis(_BENCH_MM.frame(), rate_key) if has else _benchmark_missing_message()
    section = _rollup_section(_practice_rollup(rate_key), "practice", "Practice rollup",
                              "PMPM by attributed practice", rate_key)
    return kpis, section


# -- Practice tab (callback-driven) -----------------------------------------

@callback(
    Output("mssp-practice-content", "children"),
    Input("mssp-practice-select", "value"),
    Input("mssp-benchmark-rate", "value"),
)
def _render_practice(practice, rate_key=None):
    if not practice:
        return dbc.Alert("Pick a practice to see provider-level performance.",
                         color="info", className="mt-3")

    frame = _BENCH_MM.frame()
    df = frame[frame["payer_attributed_provider_practice"].fillna(benchmark.UNATTRIBUTED)
               == practice]
    members_n = df["person_id"].nunique()
    total_mm = float(df["member_months"].sum()) or 1.0
    total_paid = float(df["total_paid"].sum())
    avg_risk = float(df["normalized_risk_score"].mean()) if not df.empty else float("nan")
    quality_pct = _quality_meeting_target_pct()
    has = _has_benchmark()
    rate_key = rate_key if has else None

    cards = [
        kpi_card("Practice", practice),
        kpi_card("Members", f"{members_n:,}"),
        kpi_card("PMPM", _pmpm(total_paid / total_mm) if total_mm else "—"),
    ]
    if has:
        cards += _benchmark_cards(df, rate_key)
    cards += [
        kpi_card("Avg Risk",
                 f"{avg_risk:.2f}" if avg_risk == avg_risk else "—"),
        kpi_card("Quality Meeting Target", _pct(quality_pct)),
    ]

    section = _rollup_section(_provider_rollup(practice, rate_key), "provider",
                              "Provider rollup", "PMPM by provider", rate_key)
    return [kpi_row(cards), section]


def _benchmark_cards(df: pd.DataFrame, rate_key: str | None) -> list[dbc.Card]:
    """Benchmark PMPM and variance cards for a filtered member-month frame."""
    selected = benchmark.rate(rate_key)
    t = benchmark.totals(df, selected.key)
    variance = t["variance_pmpm"]
    if pd.isna(variance):
        color = "secondary"
    else:
        color = "danger" if variance > 0 else "success"
    return [
        kpi_card(f"Benchmark PMPM ({selected.label})", _pmpm(t["benchmark_pmpm"]),
                 sub=f"{int(t['excluded_member_months']):,} member-months excluded"),
        kpi_card("Variance", _signed_pmpm(variance),
                 sub=f"actual {_pmpm(t['actual_pmpm'])} over the same member-months",
                 color=color),
    ]


# -- Provider tab (callback-driven) -----------------------------------------

@callback(
    Output("mssp-provider-content", "children"),
    Input("mssp-provider-select", "value"),
    Input("mssp-benchmark-rate", "value"),
)
def _render_provider(provider, rate_key=None):
    if not provider:
        return dbc.Alert("Pick a provider to see their patient panel and quality / HCC gaps.",
                         color="info", className="mt-3")

    frame = _BENCH_MM.frame()
    df = frame[frame["payer_attributed_provider"].fillna(benchmark.UNATTRIBUTED) == provider]
    panel = df["person_id"].unique()
    panel_members = _MEMBERS[_MEMBERS["person_id"].isin(panel)]
    panel_n = len(panel)
    total_mm = float(df["member_months"].sum()) or 1.0
    total_paid = float(df["total_paid"].sum())
    avg_risk = float(df["normalized_risk_score"].mean()) if not df.empty else float("nan")

    cards = [
        kpi_card("Provider", provider),
        kpi_card("Panel size", f"{panel_n:,}"),
        kpi_card("PMPM", _pmpm(total_paid / total_mm) if total_mm else "—"),
    ]
    if _has_benchmark():
        cards += _benchmark_cards(df, rate_key)
    cards.append(kpi_card("Avg Risk",
                          f"{avg_risk:.2f}" if avg_risk == avg_risk else "—"))
    cards = kpi_row(cards)

    # Top HCC gaps for the panel
    hcc = _HCC_GAPS[_HCC_GAPS["person_id"].isin(panel)] if panel_n else pd.DataFrame()
    if not hcc.empty:
        hcc_top = (
            hcc.dropna(subset=["hcc_description"])
            .groupby("hcc_description")["person_id"].count().reset_index()
            .rename(columns={"person_id": "gaps"})
            .sort_values("gaps", ascending=True).tail(15)
        )
        fig_hcc = px.bar(hcc_top, x="gaps", y="hcc_description", orientation="h",
                         title="Top HCC gaps in panel")
        fig_hcc.update_layout(height=380, yaxis_title="", xaxis_title="member gaps")
        hcc_chart = dcc.Graph(figure=fig_hcc)
    else:
        hcc_chart = no_data_message()

    # Patient panel detail with conditions and HCC gap counts
    if panel_members.empty:
        panel_table = no_data_message()
    else:
        cond_join = (
            _CONDITIONS[_CONDITIONS["person_id"].isin(panel)]
            .groupby("person_id")["condition"]
            .apply(lambda s: ", ".join(sorted(set(s.dropna()))))
            .reset_index().rename(columns={"condition": "conditions"})
        )
        gap_counts = (
            hcc.groupby("person_id")["hcc_code"].count().reset_index()
            .rename(columns={"hcc_code": "hcc_gaps"})
            if not hcc.empty else pd.DataFrame(columns=["person_id", "hcc_gaps"])
        )
        panel_disp = panel_members[["person_id", "first_name", "last_name",
                                    "age", "sex"]].merge(
            cond_join, on="person_id", how="left"
        ).merge(gap_counts, on="person_id", how="left")
        panel_disp["hcc_gaps"] = panel_disp["hcc_gaps"].fillna(0).astype(int)
        panel_table = dash_table.DataTable(
            data=panel_disp.to_dict("records"),
            columns=[{"name": c, "id": c} for c in panel_disp.columns],
            page_size=15, sort_action="native", filter_action="native",
            style_cell={"fontSize": 12, "padding": "4px",
                        "minWidth": 80, "maxWidth": 320,
                        "textOverflow": "ellipsis", "overflow": "hidden"},
            style_header={"fontWeight": "bold"},
            style_table={"overflowX": "auto"},
        )

    return [cards,
            dbc.Row([
                dbc.Col(hcc_chart, md=6),
                dbc.Col([html.H5("Patient panel"), panel_table], md=6),
            ])]


# -- Patient tab (callback-driven) ------------------------------------------

@callback(
    Output("mssp-patient-content", "children"),
    Input("mssp-patient-select", "value"),
)
def _render_patient(person_id):
    if not person_id:
        return dbc.Alert("Pick a patient to see their full chart.",
                         color="info", className="mt-3")

    member = _MEMBERS[_MEMBERS["person_id"] == person_id]
    if member.empty:
        return no_data_message()
    m = member.iloc[0]

    # Latest provider attribution
    attr = (
        _DIM_MM[_DIM_MM["person_id"] == person_id]
        .sort_values("year_month").tail(1)
    )
    attributed_provider = attr["payer_attributed_provider"].iloc[0] if not attr.empty else None
    custom_provider = attr["custom_attributed_provider"].iloc[0] if not attr.empty else None

    paid = float(_MM[_MM["person_id"] == person_id]["total_paid"].sum())
    mm_n = float(_MM[_MM["person_id"] == person_id]["member_months"].sum())
    risk = float(_MM[_MM["person_id"] == person_id]["normalized_risk_score"].mean())

    cards = kpi_row([
        kpi_card("Patient",
                 f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip()
                 or person_id),
        kpi_card("Age / Sex",
                 f"{int(m['age']) if pd.notna(m['age']) else '—'} / "
                 f"{(m.get('sex') or '—')}"),
        kpi_card("PMPM", _pmpm(paid / mm_n) if mm_n else "—"),
        kpi_card("Avg Risk", f"{risk:.2f}" if risk == risk else "—"),
        kpi_card("Provider", attributed_provider or "(unattributed)"),
    ])

    demographics = pd.DataFrame([{
        "person_id": person_id,
        "name": f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip(),
        "birth_date": str(m.get("birth_date") or ""),
        "address": m.get("address") or "",
        "city": m.get("city") or "",
        "state": m.get("state") or "",
        "zip": m.get("zip_code") or "",
        "data_source": m.get("data_source") or "",
        "payer_attributed_provider": attributed_provider or "",
        "custom_attributed_provider": custom_provider or "",
    }])

    conditions = _CONDITIONS[_CONDITIONS["person_id"] == person_id]
    cond_list = ", ".join(sorted(conditions["condition"].dropna().unique())) or "—"

    hcc = _HCC_GAPS[_HCC_GAPS["person_id"] == person_id]
    hcc_disp = hcc[["hcc_code", "hcc_description", "latest_suspect_date",
                    "reason", "contributing_factor"]] if not hcc.empty else pd.DataFrame()

    # Encounter history
    enc = _ENCOUNTERS[_ENCOUNTERS["person_id"] == person_id].copy()
    if not enc.empty:
        enc = enc.sort_values("encounter_start_date", ascending=False)
        enc_disp = enc[["encounter_id", "encounter_start_date", "encounter_group",
                        "encounter_type", "primary_diagnosis_description",
                        "facility_name", "paid_amount"]]
    else:
        enc_disp = pd.DataFrame()

    return [
        cards,
        html.H5("Demographics", className="mt-3"),
        dash_table.DataTable(
            data=demographics.to_dict("records"),
            columns=[{"name": c, "id": c} for c in demographics.columns],
            style_cell={"fontSize": 12, "padding": "4px",
                        "minWidth": 80, "maxWidth": 220,
                        "textOverflow": "ellipsis", "overflow": "hidden"},
            style_header={"fontWeight": "bold"},
            style_table={"overflowX": "auto"},
        ),
        html.H6("Chronic conditions", className="mt-3 text-muted"),
        html.P(cond_list),
        html.H5("HCC gaps", className="mt-3"),
        (dash_table.DataTable(
            data=hcc_disp.to_dict("records"),
            columns=[{"name": c, "id": c} for c in hcc_disp.columns],
            page_size=10, sort_action="native",
            style_cell={"fontSize": 12, "padding": "4px"},
            style_header={"fontWeight": "bold"},
        ) if not hcc_disp.empty else
         dbc.Alert("No HCC gaps for this patient.", color="success", className="mt-1")),
        html.H5("Encounter history", className="mt-3"),
        (dash_table.DataTable(
            data=enc_disp.to_dict("records"),
            columns=[{"name": c, "id": c} for c in enc_disp.columns],
            page_size=15, sort_action="native", filter_action="native",
            style_cell={"fontSize": 11, "padding": "3px",
                        "minWidth": 80, "maxWidth": 240,
                        "textOverflow": "ellipsis", "overflow": "hidden"},
            style_header={"fontWeight": "bold"},
            style_table={"overflowX": "auto"},
        ) if not enc_disp.empty else no_data_message()),
    ]


# -- Quality / HCC gap detail tabs -------------------------------------------

def _quality_detail_tab() -> html.Div:
    if _PQI_DENOM.empty:
        return html.Div([no_data_message()], className="pt-3")

    df = _PQI_DENOM.merge(_MEMBERS[["person_id", "age", "sex"]],
                          on="person_id", how="left")
    attr = _DIM_MM.sort_values("year_month").drop_duplicates("person_id", keep="last")
    df = df.merge(
        attr[["person_id", "payer_attributed_provider",
              "payer_attributed_provider_practice"]],
        on="person_id", how="left",
    )
    df = df.rename(columns={
        "pqi_number": "Measure ID",
        "person_id": "Person",
        "age": "Age", "sex": "Sex",
        "year_number": "Year",
        "payer_attributed_provider": "Provider",
        "payer_attributed_provider_practice": "Practice",
    })
    df["Measure Name"] = "AHRQ PQI " + df["Measure ID"].astype(str)
    cols = ["Measure ID", "Measure Name", "Person", "Age", "Sex",
            "Provider", "Practice", "Year"]

    return html.Div([
        html.P(f"{len(df):,} member-measure rows in any AHRQ PQI denominator",
               className="text-muted small"),
        dash_table.DataTable(
            data=df[cols].to_dict("records"),
            columns=[{"name": c, "id": c} for c in cols],
            page_size=25, sort_action="native", filter_action="native",
            style_cell={"fontSize": 12, "padding": "4px"},
            style_header={"fontWeight": "bold"},
        ),
    ], className="pt-3")


def _hcc_detail_tab() -> html.Div:
    if _HCC_GAPS.empty:
        return html.Div([no_data_message()], className="pt-3")

    df = _HCC_GAPS.merge(_MEMBERS[["person_id", "age", "sex"]], on="person_id",
                         how="left")
    attr = _DIM_MM.sort_values("year_month").drop_duplicates("person_id", keep="last")
    df = df.merge(
        attr[["person_id", "payer_attributed_provider",
              "payer_attributed_provider_practice"]],
        on="person_id", how="left",
    )
    df = df.rename(columns={
        "hcc_code": "HCC Code", "hcc_description": "HCC Description",
        "person_id": "Person", "age": "Age", "sex": "Sex",
        "latest_suspect_date": "Latest Suspect Date",
        "reason": "Reason", "contributing_factor": "Evidence",
        "payer_attributed_provider": "Provider",
        "payer_attributed_provider_practice": "Practice",
    })
    cols = ["HCC Code", "HCC Description", "Person", "Age", "Sex",
            "Provider", "Practice", "Latest Suspect Date", "Reason", "Evidence"]

    return html.Div([
        html.P(f"{len(df):,} suspected HCC gaps", className="text-muted small"),
        dash_table.DataTable(
            data=df[cols].to_dict("records"),
            columns=[{"name": c, "id": c} for c in cols],
            page_size=25, sort_action="native", filter_action="native",
            style_cell={"fontSize": 12, "padding": "4px",
                        "minWidth": 80, "maxWidth": 280,
                        "textOverflow": "ellipsis", "overflow": "hidden"},
            style_header={"fontWeight": "bold"},
            style_table={"overflowX": "auto"},
        ),
    ], className="pt-3")


# -- entry point --------------------------------------------------------------

def build_layout() -> html.Div:
    practice_options = [
        {"label": p, "value": p}
        for p in sorted(
            _MM["payer_attributed_provider_practice"].fillna("(unattributed)").unique()
        )
    ] if not _MM.empty else []

    provider_options = [
        {"label": p, "value": p}
        for p in sorted(
            _MM["payer_attributed_provider"].fillna("(unattributed)").unique()
        )
    ] if not _MM.empty else []

    patient_options = []
    if not _MEMBERS.empty:
        for _, m in _MEMBERS.iterrows():
            label = f"{m['person_id']}"
            if m.get("first_name") or m.get("last_name"):
                first = (m.get("first_name") or "").strip()
                last = (m.get("last_name") or "").strip()
                label += f" — {first} {last}"
            patient_options.append({"label": label, "value": m["person_id"]})

    practice_tab = html.Div([
        html.Div([
            html.Label("Practice:", className="small text-muted"),
            dcc.Dropdown(
                id="mssp-practice-select",
                options=practice_options,
                placeholder="Select a practice",
            ),
        ], style={"maxWidth": "500px"}, className="mb-3"),
        html.Div(id="mssp-practice-content"),
    ], className="pt-3")

    provider_tab = html.Div([
        html.Div([
            html.Label("Provider:", className="small text-muted"),
            dcc.Dropdown(
                id="mssp-provider-select",
                options=provider_options,
                placeholder="Select a provider",
            ),
        ], style={"maxWidth": "500px"}, className="mb-3"),
        html.Div(id="mssp-provider-content"),
    ], className="pt-3")

    patient_tab = html.Div([
        html.Div([
            html.Label("Patient:", className="small text-muted"),
            dcc.Dropdown(
                id="mssp-patient-select",
                options=patient_options,
                placeholder="Select a patient",
            ),
        ], style={"maxWidth": "500px"}, className="mb-3"),
        html.Div(id="mssp-patient-content"),
    ], className="pt-3")

    # The benchmark rate drives the Program Performance KPI row and the
    # practice and provider rollups, so it sits above the tabs.
    rate_selector = html.Div([
        html.Label("Benchmark rate:", className="small text-muted me-2"),
        dbc.RadioItems(
            id="mssp-benchmark-rate",
            options=[{"label": r.label, "value": r.key} for r in benchmark.RATES.values()],
            value=benchmark.DEFAULT_RATE,
            inline=True,
        ),
    ], className="d-flex align-items-center flex-wrap mb-2")

    tabs = dbc.Tabs([
        dbc.Tab(_program_summary_tab(), label="Program Performance"),
        dbc.Tab(practice_tab, label="Practice"),
        dbc.Tab(provider_tab, label="Provider"),
        dbc.Tab(patient_tab, label="Patient"),
        dbc.Tab(_quality_detail_tab(), label="Quality Measure Detail"),
        dbc.Tab(_hcc_detail_tab(), label="HCC Gaps Detail"),
    ])

    return page_shell(
        title="MSSP ACO Performance",
        subtitle=(
            "Practice and provider rollups against the MSSP benchmark, patient "
            "charts, quality measure gaps, and HCC suspect gaps for the "
            "attributed cohort."
        ),
        body=html.Div([rate_selector, tabs]),
        tuva_tables=[
            "semantic_layer.fact_member_months",
            "semantic_layer.dim_member_months",
            "semantic_layer.dim_member",
            "semantic_layer.fact_member_month_benchmark",
            "semantic_layer.fact_benchmark_aco_quarter",
            "semantic_layer.fact_member_condition_bridge",
            "semantic_layer.dim_condition",
            "semantic_layer.fact_hcc_gaps",
            "semantic_layer.fact_encounters",
            "ahrq_measures.pqi_rate",
            "ahrq_measures.pqi_denom_long",
        ],
    )
