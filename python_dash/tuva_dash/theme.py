"""Shared Dash app factory and Plotly template."""

from __future__ import annotations

from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import plotly.io as pio

from tuva_dash.config import get_settings

# Project-level assets folder (python_dash/assets) — holds the Tuva logo
# and branding.css. Computed relative to this file so it works whether
# the app runs from python_dash/ or from a venv elsewhere.
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# A muted Tuva-style palette. Override per-app by editing fig.update_layout.
TUVA_TEMPLATE = "simple_white"
TUVA_COLORWAY = [
    "#1f77b4", "#2ca02c", "#ff7f0e", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
]

pio.templates[TUVA_TEMPLATE].layout.colorway = TUVA_COLORWAY
pio.templates.default = TUVA_TEMPLATE


def make_app(title: str, suppress_callback_exceptions: bool = True) -> dash.Dash:
    """Construct a Dash app preconfigured with Bootstrap + Tuva defaults."""
    return dash.Dash(
        __name__,
        title=title,
        assets_folder=str(_ASSETS_DIR),
        external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
        suppress_callback_exceptions=suppress_callback_exceptions,
    )


def run(app: dash.Dash) -> None:
    """Start the Dash server using settings from .env."""
    settings = get_settings()
    app.run(
        host=settings.dash_host,
        port=settings.dash_port,
        debug=settings.dash_debug,
    )
