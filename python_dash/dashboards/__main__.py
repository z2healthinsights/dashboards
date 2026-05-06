"""Unified Tuva Dash shell.

Run with::

    python -m dashboards

Hosts every dashboard under one process behind a Tuva-branded navbar. The
existing per-dashboard entry points (``python -m dashboards.<name>``) keep
working — this module composes them, doesn't replace them.

URL routes are driven by ``tuva_dash.branding.DASHBOARDS``. Adding a new
dashboard is a one-line append to that list.
"""

from __future__ import annotations

import importlib
from typing import Callable

from dash import Input, Output, callback, dcc, html

from tuva_dash.branding import DASHBOARDS, tuva_navbar
from tuva_dash.theme import make_app, run

# Import every dashboard's layout module up front. This triggers their
# module-level @callback registrations — required because Dash's callback
# manager is global, and callbacks must be registered before the server
# starts (suppress_callback_exceptions=True is set in tuva_dash.theme).
import dashboards.cost_and_utilization.layout    # noqa: E402,F401
import dashboards.cost_drivers.layout            # noqa: E402,F401
import dashboards.dqi_analytics.layout           # noqa: E402,F401
import dashboards.mssp_aco_dashboard.layout      # noqa: E402,F401
import dashboards.population_health.layout       # noqa: E402,F401
import dashboards.quality_measures.layout        # noqa: E402,F401
import dashboards.risk_adjust_benchmark.layout   # noqa: E402,F401
import dashboards.semantic_layer.layout          # noqa: E402,F401


# -- routes -------------------------------------------------------------------

def _resolve(module_path: str) -> Callable:
    """Return the build_layout callable for a dotted module path."""
    return getattr(importlib.import_module(module_path), "build_layout")


ROUTES: dict[str, Callable] = {
    f"/{d['slug']}": _resolve(d["module"]) for d in DASHBOARDS
}

# Lazy cache: each layout is built once on first visit, reused thereafter.
_LAYOUT_CACHE: dict[str, html.Div] = {}


def _get_layout(path: str):
    if path not in _LAYOUT_CACHE:
        _LAYOUT_CACHE[path] = ROUTES[path]()
    return _LAYOUT_CACHE[path]


# -- pages --------------------------------------------------------------------

def home_page():
    import dash_bootstrap_components as dbc

    cards = [
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.H5(d["label"], className="card-title"),
                        html.P(d["blurb"], className="card-text"),
                        dbc.Button(
                            "Open",
                            href=f"/{d['slug']}",
                            class_name="btn btn-tuva mt-2",
                        ),
                    ]
                ),
                class_name="tuva-card",
            ),
            md=4, sm=6, xs=12,
            class_name="mb-3",
        )
        for d in DASHBOARDS
    ]

    return dbc.Container(
        [
            html.Div(
                [
                    html.H2("Tuva Analytics Gallery", className="mb-1"),
                    html.P(
                        "Explore the Tuva healthcare data model through eight "
                        "Power-BI-equivalent dashboards. Pick one below or use "
                        "the navbar to jump between them.",
                        className="text-muted",
                    ),
                ],
                className="mb-4",
            ),
            dbc.Row(cards),
        ],
        fluid=True,
        class_name="tuva-page-content",
    )


def not_found_page(path: str):
    import dash_bootstrap_components as dbc

    return dbc.Container(
        dbc.Alert(
            [
                html.Strong(f"No page at {path!r}. "),
                html.A("Back to home →", href="/"),
            ],
            color="warning",
        ),
        class_name="tuva-page-content",
    )


# -- app ----------------------------------------------------------------------

app = make_app("Tuva Analytics")
app.layout = html.Div(
    [
        dcc.Location(id="tuva-shell-url", refresh=False),
        html.Div(id="tuva-shell-navbar"),
        html.Div(id="tuva-shell-content", className="tuva-page-content"),
    ]
)


@callback(
    Output("tuva-shell-content", "children"),
    Output("tuva-shell-navbar", "children"),
    Input("tuva-shell-url", "pathname"),
)
def _route(pathname):
    path = (pathname or "/").rstrip("/") or "/"
    active_slug = path.lstrip("/") if path != "/" else None
    navbar = tuva_navbar(active_slug)

    if path == "/":
        return home_page(), navbar
    if path in ROUTES:
        return _get_layout(path), navbar
    return not_found_page(path), navbar


def main() -> None:
    run(app)


if __name__ == "__main__":
    main()
