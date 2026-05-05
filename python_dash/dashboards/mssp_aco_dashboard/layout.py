"""Layout for the MSSP ACO Performance dashboard.

Mirrors the 6 PBI pages: Program Performance Summary, Practice, Provider,
Patient, Quality Measure Detail, HCC Gaps Detail.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Input, Output, callback, dash_table, dcc, html

from tuva_dash.components import kpi_card, kpi_row, no_data_message, page_shell

from . import queries

# Module-level cache.
_MM = queries.load_member_months()
_DIM_MM = queries.load_dim_member_months()
_MEMBERS = queries.load_members()
_CONDITIONS = queries.load_member_conditions()
_HCC_GAPS = queries.load_hcc_gaps()
_ENCOUNTERS = queries.load_encounters()
_PQI_RATE = queries.load_pqi_rate()
_PQI_DENOM = queries.load_pqi_denom()

QUALITY_TARGET = 0.80


# -- formatting helpers ------------------------------------------------------

def _money(v) -> str:
    return "—" if pd.isna(v) else f"${v:,.0f}"


def _pmpm(v) -> str:
    return "—" if pd.isna(v) else f"${v:,.2f}"


def _pct(v) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.1f}%"


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


def _practice_rollup() -> pd.DataFrame:
    if _MM.empty:
        return pd.DataFrame()
    g = (
        _MM.groupby("payer_attributed_provider_practice", dropna=False)
        .agg(
            members=("person_id", "nunique"),
            member_months=("member_months", "sum"),
            paid=("total_paid", "sum"),
            avg_risk=("normalized_risk_score", "mean"),
        ).reset_index()
    )
    g["practice"] = g["payer_attributed_provider_practice"].fillna("(unattributed)")
    g["pmpm"] = g["paid"] / g["member_months"].where(g["member_months"] != 0)
    return g[["practice", "members", "member_months", "paid", "pmpm", "avg_risk"]]


def _provider_rollup(practice: str | None = None) -> pd.DataFrame:
    if _MM.empty:
        return pd.DataFrame()
    df = _MM
    if practice and practice != "(all)":
        df = df[df["payer_attributed_provider_practice"].fillna("(unattributed)") == practice]
    g = (
        df.groupby("payer_attributed_provider", dropna=False)
        .agg(
            members=("person_id", "nunique"),
            member_months=("member_months", "sum"),
            paid=("total_paid", "sum"),
            avg_risk=("normalized_risk_score", "mean"),
        ).reset_index()
    )
    g["provider"] = g["payer_attributed_provider"].fillna("(unattributed)")
    g["pmpm"] = g["paid"] / g["member_months"].where(g["member_months"] != 0)
    return g[["provider", "members", "member_months", "paid", "pmpm", "avg_risk"]]


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

    practices = _practice_rollup()
    practices_disp = practices.copy()
    practices_disp["paid"] = practices_disp["paid"].round(0)
    practices_disp["pmpm"] = practices_disp["pmpm"].round(2)
    practices_disp["avg_risk"] = practices_disp["avg_risk"].round(2)
    practices_disp = practices_disp.rename(columns={
        "practice": "Practice", "members": "Members",
        "member_months": "Member Months", "paid": "Paid",
        "pmpm": "PMPM", "avg_risk": "Avg Risk",
    })

    fig = px.bar(
        practices.sort_values("pmpm"),
        x="pmpm", y="practice", orientation="h",
        title="PMPM by attributed practice",
    )
    fig.update_layout(height=320, xaxis_tickprefix="$", xaxis_tickformat=",",
                      yaxis_title="", xaxis_title="")

    return html.Div([
        cards,
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig), md=6),
            dbc.Col([
                html.H5("Practice rollup"),
                dash_table.DataTable(
                    data=practices_disp.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in practices_disp.columns],
                    page_size=15, sort_action="native",
                    style_cell={"fontSize": 12, "padding": "4px"},
                    style_header={"fontWeight": "bold"},
                ),
            ], md=6),
        ]),
    ], className="pt-3")


# -- Practice tab (callback-driven) -----------------------------------------

@callback(
    Output("mssp-practice-content", "children"),
    Input("mssp-practice-select", "value"),
)
def _render_practice(practice):
    if not practice:
        return dbc.Alert("Pick a practice to see provider-level performance.",
                         color="info", className="mt-3")

    df = _MM[_MM["payer_attributed_provider_practice"].fillna("(unattributed)") == practice]
    members_n = df["person_id"].nunique()
    total_mm = float(df["member_months"].sum()) or 1.0
    total_paid = float(df["total_paid"].sum())
    avg_risk = float(df["normalized_risk_score"].mean()) if not df.empty else float("nan")
    quality_pct = _quality_meeting_target_pct()

    cards = kpi_row([
        kpi_card("Practice", practice),
        kpi_card("Members", f"{members_n:,}"),
        kpi_card("PMPM", _pmpm(total_paid / total_mm) if total_mm else "—"),
        kpi_card("Avg Risk",
                 f"{avg_risk:.2f}" if avg_risk == avg_risk else "—"),
        kpi_card("Quality Meeting Target", _pct(quality_pct)),
    ])

    providers = _provider_rollup(practice)
    if providers.empty:
        return [cards, no_data_message()]

    providers_disp = providers.copy()
    providers_disp["paid"] = providers_disp["paid"].round(0)
    providers_disp["pmpm"] = providers_disp["pmpm"].round(2)
    providers_disp["avg_risk"] = providers_disp["avg_risk"].round(2)
    providers_disp = providers_disp.rename(columns={
        "provider": "Provider", "members": "Members",
        "member_months": "Member Months", "paid": "Paid",
        "pmpm": "PMPM", "avg_risk": "Avg Risk",
    })

    fig = px.bar(providers.sort_values("pmpm"), x="pmpm", y="provider",
                 orientation="h", title="PMPM by provider")
    fig.update_layout(height=320, xaxis_tickprefix="$", xaxis_tickformat=",",
                      yaxis_title="", xaxis_title="")

    return [cards,
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig), md=6),
                dbc.Col([
                    html.H5("Provider rollup"),
                    dash_table.DataTable(
                        data=providers_disp.to_dict("records"),
                        columns=[{"name": c, "id": c} for c in providers_disp.columns],
                        page_size=15, sort_action="native",
                        style_cell={"fontSize": 12, "padding": "4px"},
                        style_header={"fontWeight": "bold"},
                    ),
                ], md=6),
            ])]


# -- Provider tab (callback-driven) -----------------------------------------

@callback(
    Output("mssp-provider-content", "children"),
    Input("mssp-provider-select", "value"),
)
def _render_provider(provider):
    if not provider:
        return dbc.Alert("Pick a provider to see their patient panel and quality / HCC gaps.",
                         color="info", className="mt-3")

    df = _MM[_MM["payer_attributed_provider"].fillna("(unattributed)") == provider]
    panel = df["person_id"].unique()
    panel_members = _MEMBERS[_MEMBERS["person_id"].isin(panel)]
    panel_n = len(panel)
    total_mm = float(df["member_months"].sum()) or 1.0
    total_paid = float(df["total_paid"].sum())
    avg_risk = float(df["normalized_risk_score"].mean()) if not df.empty else float("nan")

    cards = kpi_row([
        kpi_card("Provider", provider),
        kpi_card("Panel size", f"{panel_n:,}"),
        kpi_card("PMPM", _pmpm(total_paid / total_mm) if total_mm else "—"),
        kpi_card("Avg Risk",
                 f"{avg_risk:.2f}" if avg_risk == avg_risk else "—"),
    ])

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
                label += f" — {(m.get('first_name') or '').strip()} {(m.get('last_name') or '').strip()}"
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

    body = dbc.Tabs([
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
            "Practice and provider rollups, patient charts, quality "
            "measure gaps, and HCC suspect gaps for the attributed cohort."
        ),
        body=body,
        tuva_tables=[
            "semantic_layer.fact_member_months",
            "semantic_layer.dim_member_months",
            "semantic_layer.dim_member",
            "semantic_layer.fact_member_condition_bridge",
            "semantic_layer.dim_condition",
            "semantic_layer.fact_hcc_gaps",
            "semantic_layer.fact_encounters",
            "ahrq_measures.pqi_rate",
            "ahrq_measures.pqi_denom_long",
        ],
    )
