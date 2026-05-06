"""Layout for the Cost and Utilization dashboard.

Mirrors the 7 pages of the Power BI version:
Summary, Inpatient, Outpatient, Office Based, Other, CCSR Detail, Encounter Type.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import dash_table, dcc, html

from tuva_dash.components import kpi_card, kpi_row, no_data_message, page_shell

from . import queries

# Top-level encounter groups present in the data. The non-pharmacy groups
# get their own "deep dive" tab in PBI.
_GROUP_ALIASES = {
    "Inpatient": "inpatient",
    "Outpatient": "outpatient",
    "Office Based": "office based",
    "Other": "other",
}


# -- formatting ---------------------------------------------------------------

def _money(v: float) -> str:
    return "—" if pd.isna(v) else f"${v:,.0f}"


def _pmpm(v: float) -> str:
    return "—" if pd.isna(v) else f"${v:,.2f}"


def _pct(v: float) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.1f}%"


# -- measure helpers (PMPM and friends) ---------------------------------------

def _pmpm_value(paid: float, member_months: float) -> float:
    if not member_months:
        return float("nan")
    return paid / member_months


def _total_member_months(mm: pd.DataFrame) -> float:
    return float(mm["member_months"].sum()) if not mm.empty else 0.0


def _contributive_pmpm_by(
    df: pd.DataFrame, total_mm: float, group_col: str, paid_col: str = "paid_amount"
) -> pd.DataFrame:
    """Contributive PMPM = sum(paid for slice) / total_member_months."""
    if df.empty or not total_mm:
        return pd.DataFrame(columns=[group_col, "pmpm"])
    g = (
        df.dropna(subset=[group_col])
        .groupby(group_col, dropna=False)[paid_col]
        .sum()
        .reset_index()
    )
    g["pmpm"] = g[paid_col] / total_mm
    return g.sort_values("pmpm", ascending=True)


def _pmpm_trend(
    df: pd.DataFrame, mm: pd.DataFrame, paid_col: str = "paid_amount"
) -> pd.DataFrame:
    if df.empty or mm.empty:
        return pd.DataFrame(columns=["year_month", "pmpm"])
    paid_by_m = df.groupby("year_month")[paid_col].sum().rename("paid")
    mm_by_m = mm.groupby("year_month")["member_months"].sum().rename("mm")
    out = pd.concat([paid_by_m, mm_by_m], axis=1).fillna(0).reset_index()
    out["pmpm"] = out["paid"] / out["mm"].where(out["mm"] != 0)
    out["year_month"] = pd.to_datetime(out["year_month"], format="%Y%m", errors="coerce")
    return out.sort_values("year_month")


# -- shared chart builders ---------------------------------------------------

def _bar_top(
    df: pd.DataFrame, x: str, y: str, title: str, top_n: int = 10, currency: bool = False,
):
    if df.empty:
        return no_data_message()
    d = df.dropna(subset=[x]).sort_values(y, ascending=False).head(top_n)
    fig = px.bar(d.sort_values(y), x=y, y=x, orientation="h", title=title)
    fig.update_layout(height=380, yaxis_title="", xaxis_title="")
    if currency:
        fig.update_xaxes(tickprefix="$", tickformat=",")
    return dcc.Graph(figure=fig)


def _line(df: pd.DataFrame, x: str, y: str, title: str, currency: bool = False, pct: bool = False):
    if df.empty:
        return no_data_message()
    fig = px.line(df, x=x, y=y, title=title, markers=True)
    fig.update_layout(height=320, yaxis_title="", xaxis_title="")
    if currency:
        fig.update_yaxes(tickprefix="$", tickformat=",")
    if pct:
        fig.update_yaxes(tickformat=".0%")
    return dcc.Graph(figure=fig)


# -- Summary tab --------------------------------------------------------------

def _summary_tab(
    mm: pd.DataFrame,
    encounters: pd.DataFrame,
    claims: pd.DataFrame,
    members: pd.DataFrame,
    risk: pd.DataFrame,
):
    total_mm = _total_member_months(mm)
    total_paid = float(mm["total_paid"].sum()) if "total_paid" in mm and not mm.empty else (
        float(claims["paid_amount"].sum()) if not claims.empty else 0.0
    )
    distinct_members = mm["person_id"].nunique() if not mm.empty else 0
    pmpm = _pmpm_value(total_paid, total_mm)
    pct_female = (
        (members["sex"].str.lower() == "female").mean() if not members.empty else float("nan")
    )
    avg_risk = (
        float(risk["blended_risk_score"].mean()) if not risk.empty else float("nan")
    )

    cards = kpi_row([
        kpi_card("Members", f"{distinct_members:,}"),
        kpi_card("Total Paid", _money(total_paid)),
        kpi_card("PMPM", _pmpm(pmpm)),
        kpi_card("Avg Risk Score", f"{avg_risk:.2f}" if avg_risk == avg_risk else "—"),
        kpi_card("% Female", _pct(pct_female)),
    ])

    by_group = _contributive_pmpm_by(claims, total_mm, "encounter_group")
    by_type = _contributive_pmpm_by(claims, total_mm, "encounter_type")
    by_ccsr = _contributive_pmpm_by(claims, total_mm, "ccsr_category_description")
    by_specialty = _contributive_pmpm_by(claims, total_mm, "specialty")

    trend_df = _pmpm_trend(claims, mm)

    # 100% stacked: encounter group share of paid by month
    if not claims.empty:
        share = (
            claims.groupby(["year_month", "encounter_group"])["paid_amount"].sum().reset_index()
        )
        share["year_month"] = pd.to_datetime(share["year_month"], format="%Y%m", errors="coerce")
        share = share.sort_values("year_month")
        stacked_fig = px.area(
            share,
            x="year_month",
            y="paid_amount",
            color="encounter_group",
            groupnorm="percent",
            title="Encounter group share of paid (monthly)",
        )
        stacked_fig.update_layout(height=320, yaxis_title="share", xaxis_title="")
        stacked = dcc.Graph(figure=stacked_fig)
    else:
        stacked = no_data_message()

    return html.Div(
        [
            cards,
            dbc.Row(
                [
                    dbc.Col(_bar_top(by_group, "encounter_group", "pmpm",
                                     "Contributive PMPM by encounter group", currency=True), md=6),
                    dbc.Col(_bar_top(by_type, "encounter_type", "pmpm",
                                     "Contributive PMPM by encounter type", currency=True), md=6),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(_bar_top(by_ccsr, "ccsr_category_description", "pmpm",
                                     "Contributive PMPM by CCSR (top 10)", currency=True), md=6),
                    dbc.Col(_bar_top(by_specialty, "specialty", "pmpm",
                                     "Contributive PMPM by specialty (top 10)", currency=True), md=6),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(_line(trend_df, "year_month", "pmpm",
                                  "PMPM trend", currency=True), md=6),
                    dbc.Col(stacked, md=6),
                ]
            ),
        ],
        className="pt-3",
    )


# -- Group deep-dive tab (Inpatient / Outpatient / Office Based / Other) -----

def _group_tab(
    group_label: str,
    group_filter: str,
    mm: pd.DataFrame,
    encounters: pd.DataFrame,
    claims: pd.DataFrame,
    admissions: pd.DataFrame | None,
    ed_visits: pd.DataFrame | None,
):
    total_mm = _total_member_months(mm)
    g_claims = claims[claims["encounter_group"] == group_filter] if not claims.empty else claims
    g_enc = encounters[encounters["encounter_group"] == group_filter] if not encounters.empty else encounters

    paid = float(g_claims["paid_amount"].sum()) if not g_claims.empty else 0.0
    encounters_n = int(g_enc["encounter_id"].nunique()) if not g_enc.empty else 0
    contributive_pmpm = _pmpm_value(paid, total_mm)
    cost_per_util = (paid / encounters_n) if encounters_n else float("nan")
    pkpy = (encounters_n * 12000 / total_mm) if total_mm else float("nan")

    extra_cards = []
    if group_filter == "inpatient" and admissions is not None and not admissions.empty:
        avg_los = float(admissions["length_of_stay"].mean())
        extra_cards.append(kpi_card("Avg LOS", f"{avg_los:.1f}"))

    cards = kpi_row([
        kpi_card("Contributive PMPM", _pmpm(contributive_pmpm)),
        kpi_card("Cost per util", _money(cost_per_util)),
        kpi_card("PKPY", f"{pkpy:,.1f}" if pkpy == pkpy else "—"),
        *extra_cards,
    ])

    by_ccsr = _contributive_pmpm_by(g_claims, total_mm, "ccsr_category_description")
    by_specialty = _contributive_pmpm_by(g_claims, total_mm, "specialty")
    by_facility = (
        g_claims.dropna(subset=["facility_name"])
        .groupby("facility_name")["paid_amount"].sum().reset_index()
        if not g_claims.empty else pd.DataFrame(columns=["facility_name", "paid_amount"])
    )
    by_type_paid = (
        g_enc.dropna(subset=["encounter_type"])
        .groupby("encounter_type")["paid_amount"].sum().reset_index()
        if not g_enc.empty else pd.DataFrame(columns=["encounter_type", "paid_amount"])
    )

    pmpm_trend = _pmpm_trend(g_claims, mm)
    cost_per_util_trend = _cost_per_util_trend(g_enc)
    pkpy_trend = _pkpy_trend(g_enc, mm)

    rows = [
        cards,
        dbc.Row(
            [
                dbc.Col(_bar_top(by_ccsr, "ccsr_category_description", "pmpm",
                                 "PMPM by CCSR (top 10)", currency=True), md=6),
                dbc.Col(_bar_top(by_specialty, "specialty", "pmpm",
                                 "PMPM by specialty (top 10)", currency=True), md=6),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(_bar_top(by_facility, "facility_name", "paid_amount",
                                 "Top facilities by paid amount", currency=True), md=6),
                dbc.Col(_bar_top(by_type_paid, "encounter_type", "paid_amount",
                                 "Paid amount by encounter type", currency=True), md=6),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(_line(pmpm_trend, "year_month", "pmpm",
                              "PMPM trend", currency=True), md=6),
                dbc.Col(_line(cost_per_util_trend, "year_month", "cost_per_util",
                              "Cost per util trend", currency=True), md=6),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(_line(pkpy_trend, "year_month", "pkpy",
                              "PKPY trend"), md=6),
                dbc.Col(_inpatient_or_ed_extra(group_filter, admissions, ed_visits), md=6),
            ]
        ),
    ]

    # Inpatient-specific: top DRGs and LOS trend
    if group_filter == "inpatient" and admissions is not None and not admissions.empty:
        top_drgs = (
            admissions.dropna(subset=["drg_description"])
            .groupby("drg_description")["encounter_id"].count().reset_index()
            .rename(columns={"encounter_id": "count"})
        )
        rows.append(
            dbc.Row(
                [
                    dbc.Col(_bar_top(top_drgs, "drg_description", "count",
                                     "Top DRGs by admission count"), md=6),
                    dbc.Col(_los_trend(admissions), md=6),
                ],
                className="mt-3",
            )
        )

    return html.Div(rows, className="pt-3")


def _cost_per_util_trend(enc: pd.DataFrame) -> pd.DataFrame:
    if enc.empty:
        return pd.DataFrame(columns=["year_month", "cost_per_util"])
    g = enc.groupby("year_month").agg(
        paid=("paid_amount", "sum"),
        encounters=("encounter_id", "nunique"),
    ).reset_index()
    g["cost_per_util"] = g["paid"] / g["encounters"].where(g["encounters"] != 0)
    g["year_month"] = pd.to_datetime(g["year_month"], format="%Y%m", errors="coerce")
    return g.sort_values("year_month")


def _pkpy_trend(enc: pd.DataFrame, mm: pd.DataFrame) -> pd.DataFrame:
    if enc.empty or mm.empty:
        return pd.DataFrame(columns=["year_month", "pkpy"])
    enc_by_m = enc.groupby("year_month")["encounter_id"].nunique().rename("encounters")
    mm_by_m = mm.groupby("year_month")["member_months"].sum().rename("mm")
    out = pd.concat([enc_by_m, mm_by_m], axis=1).fillna(0).reset_index()
    out["pkpy"] = (out["encounters"] * 12000) / out["mm"].where(out["mm"] != 0)
    out["year_month"] = pd.to_datetime(out["year_month"], format="%Y%m", errors="coerce")
    return out.sort_values("year_month")


def _los_trend(admissions: pd.DataFrame):
    df = admissions.copy()
    df["admit_date"] = pd.to_datetime(df["admit_date"], errors="coerce")
    df["year_month"] = df["admit_date"].dt.to_period("M").dt.to_timestamp()
    by_m = df.groupby("year_month")["length_of_stay"].mean().reset_index()
    fig = px.line(by_m, x="year_month", y="length_of_stay",
                  title="Average LOS trend", markers=True)
    fig.update_layout(height=320, yaxis_title="days", xaxis_title="")
    return dcc.Graph(figure=fig)


def _readmission_trend(admissions: pd.DataFrame):
    if admissions.empty:
        return no_data_message()
    df = admissions.copy()
    if "index_admission_flag" in df.columns:
        df = df[df["index_admission_flag"].fillna(0).astype(int) == 1]
    df["readmit_30_flag"] = df.get("readmit_30_flag", 0)
    df["readmit_30_flag"] = pd.to_numeric(df["readmit_30_flag"], errors="coerce").fillna(0)
    df = df.dropna(subset=["discharge_date"])
    if df.empty:
        return dbc.Alert(
            "No index admissions with valid discharge dates in this dataset.",
            color="secondary", className="mt-1",
        )
    df["discharge_date"] = pd.to_datetime(df["discharge_date"], errors="coerce")
    df["year_month"] = df["discharge_date"].dt.to_period("M").dt.to_timestamp()
    by_m = (
        df.groupby("year_month")
        .agg(idx_n=("encounter_id", "count"), readmits=("readmit_30_flag", "sum"))
        .reset_index()
    )
    by_m["rate"] = by_m["readmits"] / by_m["idx_n"].where(by_m["idx_n"] != 0)
    fig = px.line(by_m, x="year_month", y="rate",
                  title="30-day readmission rate", markers=True)
    fig.update_layout(height=320, yaxis_title="", xaxis_title="", yaxis_tickformat=".0%")
    return dcc.Graph(figure=fig)


def _avoidable_ed_trend(ed_visits: pd.DataFrame, encounters: pd.DataFrame):
    if ed_visits.empty or encounters.empty:
        return no_data_message()
    enc = encounters[["encounter_id", "year_month"]]
    df = ed_visits.merge(enc, on="encounter_id", how="left")
    df["year_month"] = pd.to_datetime(df["year_month"], format="%Y%m", errors="coerce")
    by_m = (
        df.groupby("year_month")
        .agg(visits=("encounter_id", "count"), avoidable=("avoidable", "sum"))
        .reset_index()
    )
    by_m["pct"] = by_m["avoidable"] / by_m["visits"].where(by_m["visits"] != 0)
    fig = px.line(by_m, x="year_month", y="pct",
                  title="Avoidable ED %", markers=True)
    fig.update_layout(height=320, yaxis_title="", xaxis_title="", yaxis_tickformat=".0%")
    return dcc.Graph(figure=fig)


def _inpatient_or_ed_extra(group_filter, admissions, ed_visits):
    if group_filter == "inpatient" and admissions is not None and not admissions.empty:
        return _readmission_trend(admissions)
    if group_filter == "outpatient" and ed_visits is not None:
        # Pair with the encounters df that's already joined upstream
        encounters = queries.load_encounters()
        return _avoidable_ed_trend(ed_visits, encounters)
    return no_data_message()


# -- CCSR Detail tab ----------------------------------------------------------

def _ccsr_detail_tab(mm: pd.DataFrame, claims: pd.DataFrame):
    total_mm = _total_member_months(mm)
    paid = float(claims["paid_amount"].sum()) if not claims.empty else 0.0
    members = claims["person_id"].nunique() if not claims.empty else 0
    pmpm = _pmpm_value(paid, total_mm)

    cards = kpi_row([
        kpi_card("Contributive PMPM", _pmpm(pmpm)),
        kpi_card("Total Paid", _money(paid)),
        kpi_card("Members touched", f"{members:,}"),
    ])

    if claims.empty:
        return html.Div([cards, no_data_message()], className="pt-3")

    treemap_df = (
        claims.dropna(subset=["primary_diagnosis_description"])
        .groupby("primary_diagnosis_description")["paid_amount"].sum().reset_index()
    )
    tree = px.treemap(
        treemap_df.sort_values("paid_amount", ascending=False).head(40),
        path=["primary_diagnosis_description"],
        values="paid_amount",
        title="Paid amount by primary diagnosis (top 40)",
    )
    tree.update_layout(height=480)

    by_facility = (
        claims.dropna(subset=["facility_name"])
        .groupby("facility_name")["paid_amount"].sum().reset_index()
    )
    by_group_pmpm = _contributive_pmpm_by(claims, total_mm, "encounter_group")
    by_type_pmpm = _contributive_pmpm_by(claims, total_mm, "encounter_type")

    return html.Div(
        [
            cards,
            dbc.Row([dbc.Col(dcc.Graph(figure=tree), md=12)], className="mb-3"),
            dbc.Row(
                [
                    dbc.Col(_bar_top(by_facility, "facility_name", "paid_amount",
                                     "Top facilities by paid amount", currency=True), md=6),
                    dbc.Col(_bar_top(by_group_pmpm, "encounter_group", "pmpm",
                                     "Contributive PMPM by encounter group", currency=True), md=6),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(_bar_top(by_type_pmpm, "encounter_type", "pmpm",
                                     "Contributive PMPM by encounter type", currency=True), md=12),
                ],
                className="mb-3",
            ),
        ],
        className="pt-3",
    )


# -- Encounter Type tab -------------------------------------------------------

def _encounter_type_tab(mm: pd.DataFrame, claims: pd.DataFrame):
    total_mm = _total_member_months(mm)
    if claims.empty:
        return html.Div([no_data_message()], className="pt-3")

    by_type_pmpm = _contributive_pmpm_by(claims, total_mm, "encounter_type")
    by_type_paid = (
        claims.dropna(subset=["encounter_type"])
        .groupby("encounter_type")["paid_amount"].sum().reset_index()
    )
    by_ccsr_paid = (
        claims.dropna(subset=["ccsr_category_description"])
        .groupby("ccsr_category_description")["paid_amount"].sum().reset_index()
    )
    by_facility = (
        claims.dropna(subset=["facility_name"])
        .groupby("facility_name")["paid_amount"].sum().reset_index()
    )

    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(_bar_top(by_type_pmpm, "encounter_type", "pmpm",
                                     "Contributive PMPM by encounter type", top_n=20,
                                     currency=True), md=6),
                    dbc.Col(_bar_top(by_type_paid, "encounter_type", "paid_amount",
                                     "Paid by encounter type", top_n=20, currency=True), md=6),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(_bar_top(by_ccsr_paid, "ccsr_category_description", "paid_amount",
                                     "Paid by CCSR (top 15)", top_n=15, currency=True), md=6),
                    dbc.Col(_bar_top(by_facility, "facility_name", "paid_amount",
                                     "Paid by facility (top 15)", top_n=15, currency=True), md=6),
                ]
            ),
        ],
        className="pt-3",
    )


# -- entry point --------------------------------------------------------------

def build_layout() -> html.Div:
    mm = queries.load_member_months()
    encounters = queries.load_encounters()
    claims = queries.load_claims()
    admissions = queries.load_admissions()
    ed_visits = queries.load_ed_visits()
    members = queries.load_dim_member()
    risk = queries.load_risk_scores()

    tabs = [
        dbc.Tab(_summary_tab(mm, encounters, claims, members, risk), label="Summary"),
    ]
    for label, group_filter in _GROUP_ALIASES.items():
        tabs.append(
            dbc.Tab(
                _group_tab(label, group_filter, mm, encounters, claims, admissions, ed_visits),
                label=label,
            )
        )
    tabs.append(dbc.Tab(_ccsr_detail_tab(mm, claims), label="CCSR Detail"))
    tabs.append(dbc.Tab(_encounter_type_tab(mm, claims), label="Encounter Type"))

    return page_shell(
        title="Cost and Utilization",
        subtitle="PMPM, cost per utilization, PKPY, and trends across encounter groups.",
        body=dbc.Tabs(tabs),
        tuva_tables=[
            "semantic_layer.fact_member_months",
            "semantic_layer.fact_encounters",
            "semantic_layer.fact_claims",
            "semantic_layer.fact_admissions",
            "semantic_layer.fact_ed_visits",
            "semantic_layer.dim_encounter_group",
            "semantic_layer.dim_encounter_type",
            "semantic_layer.dim_member",
            "semantic_layer.fact_risk_scores",
        ],
    )
