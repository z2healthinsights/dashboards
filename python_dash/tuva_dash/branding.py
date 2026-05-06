"""Tuva-branded shell components.

Color palette and font come from the PBI theme files
(``Tuva_Theme*.json`` inside the .pbit archives) and are kept in sync with
``assets/branding.css`` so server-rendered styles match the CSS layer.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

# Hex values mirror :root vars in assets/branding.css
TUVA_BLUE = "#0087F6"
TUVA_BLUE_DARK = "#1A7AA9"
TUVA_TEXT = "#212121"
TUVA_TEXT_MUTED = "#9E9E9E"
TUVA_BG = "#FFFFFF"
TUVA_SECTION_BG = "#FAFAFA"
TUVA_SUCCESS = "#2977AE"
TUVA_ERROR = "#FF6334"
TUVA_BORDER = "#E5E7EB"

LOGO_SRC = "/assets/tuva_logo.png"

# Single source of truth for the dashboard catalog. The shell router and
# the home page both read from this list, so adding a new dashboard is a
# one-line change.
DASHBOARDS: list[dict] = [
    {
        "slug": "cost-and-utilization",
        "label": "Cost & Utilization",
        "blurb": "PMPM, cost per utilization, and PKPY across encounter groups.",
        "module": "dashboards.cost_and_utilization.layout",
    },
    {
        "slug": "cost-drivers",
        "label": "Cost Drivers",
        "blurb": "Cohort-filtered cost view — pick chronic conditions and see what they drive.",
        "module": "dashboards.cost_drivers.layout",
    },
    {
        "slug": "dqi-analytics",
        "label": "DQI Analytics",
        "blurb": "Tuva Data Quality Index — atomic claim flags, logical and structural tests.",
        "module": "dashboards.dqi_analytics.layout",
    },
    {
        "slug": "mssp-aco",
        "label": "MSSP ACO",
        "blurb": "Practice and provider rollups, patient charts, quality and HCC gaps.",
        "module": "dashboards.mssp_aco_dashboard.layout",
    },
    {
        "slug": "population-health",
        "label": "Population Health",
        "blurb": "Demographics, chronic conditions, inpatient, preventable events, pharmacy, risk.",
        "module": "dashboards.population_health.layout",
    },
    {
        "slug": "quality-measures",
        "label": "Quality Measures",
        "blurb": "Clinical measure performance plus AHRQ Prevention Quality Indicators.",
        "module": "dashboards.quality_measures.layout",
    },
    {
        "slug": "risk-adjusted-benchmarks",
        "label": "Risk-Adjusted Benchmarks",
        "blurb": "Actual vs expected PMPM and inpatient outcomes against benchmarks.",
        "module": "dashboards.risk_adjust_benchmark.layout",
    },
    {
        "slug": "semantic-layer",
        "label": "Semantic Layer",
        "blurb": "Browse the unified Tuva data model — tables, columns, sample rows, joins.",
        "module": "dashboards.semantic_layer.layout",
    },
]


def tuva_navbar(active_slug: str | None = None) -> dbc.Navbar:
    """The Tuva-branded top navbar shared by every page in the shell."""
    nav_links = [
        dbc.NavLink(
            d["label"],
            href=f"/{d['slug']}",
            active=(active_slug == d["slug"]),
            class_name="nav-link",
        )
        for d in DASHBOARDS
    ]

    brand = html.A(
        html.Img(src=LOGO_SRC, className="tuva-navbar-logo"),
        href="/",
        className="navbar-brand me-3",
    )

    return dbc.Navbar(
        dbc.Container(
            [
                brand,
                dbc.Nav(nav_links, navbar=True, className="ms-auto flex-wrap"),
            ],
            fluid=True,
        ),
        className="tuva-navbar",
        sticky="top",
    )
