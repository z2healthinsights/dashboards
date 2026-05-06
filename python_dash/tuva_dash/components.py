"""Reusable Dash components: KPI cards, page shells, no-data placeholders."""

from __future__ import annotations

from typing import Iterable

import dash_bootstrap_components as dbc
from dash import html

from tuva_dash.config import get_settings


def kpi_card(label: str, value: str, *, sub: str | None = None, color: str = "primary") -> dbc.Card:
    """A single KPI card. PBI's `Card` and `Multi-row Card` visuals map here."""
    body = [html.H6(label, className="text-muted text-uppercase small mb-1"),
            html.H3(value, className="mb-0")]
    if sub:
        body.append(html.Small(sub, className="text-muted"))
    return dbc.Card(dbc.CardBody(body), className=f"border-{color} h-100")


def kpi_row(cards: Iterable[dbc.Card]) -> dbc.Row:
    return dbc.Row([dbc.Col(c, md=True) for c in cards], className="g-3 mb-3")


def page_shell(title: str, subtitle: str, body, tuva_tables: list[str] | None = None):
    """Standard page wrapper: header + content + footer with the tables backing the page."""
    settings = get_settings()
    badges = []
    if not settings.load_data:
        badges.append(
            dbc.Badge(
                "LOAD_DATA=false — showing empty frames",
                color="warning",
                className="ms-2",
            )
        )

    footer = []
    if tuva_tables:
        footer = [
            html.Hr(),
            html.Small(
                ["Backed by Tuva tables: "]
                + [html.Code(t, className="me-2") for t in tuva_tables],
                className="text-muted",
            ),
        ]

    return dbc.Container(
        [
            html.Div(
                [
                    html.H2([title] + badges, className="mb-0"),
                    html.P(subtitle, className="text-muted"),
                ],
                className="my-3",
            ),
            body,
            *footer,
        ],
        fluid=True,
    )


def no_data_message() -> dbc.Alert:
    return dbc.Alert(
        [
            html.Strong("No data loaded. "),
            "Set ",
            html.Code("LOAD_DATA=true"),
            " in your .env and configure the warehouse parameters to populate this view.",
        ],
        color="info",
    )


def scaffold_layout(
    title: str,
    subtitle: str,
    pages: list[tuple[str, str]],
    tuva_tables: list[str],
):
    """Layout used by dashboards that aren't fully implemented yet.

    Each `pages` entry is `(tab_label, description)`. The body shows one tab
    per page with a placeholder describing the visuals that will live there
    once the dashboard is wired up.
    """
    tabs = []
    for label, description in pages:
        tabs.append(
            dbc.Tab(
                label=label,
                children=html.Div(
                    [
                        dbc.Alert(
                            [
                                html.Strong("Scaffold. "),
                                "This page will mirror the equivalent Power BI "
                                "tab. ",
                                html.Br(),
                                html.Span(description, className="text-muted"),
                            ],
                            color="secondary",
                            className="mt-3",
                        ),
                    ]
                ),
            )
        )
    return page_shell(title, subtitle, dbc.Tabs(tabs), tuva_tables=tuva_tables)
