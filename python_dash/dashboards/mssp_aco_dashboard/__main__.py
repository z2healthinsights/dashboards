"""Entry point: `python -m dashboards.mssp_aco_dashboard`."""

from tuva_dash.theme import make_app, run

from .layout import build_layout


def main() -> None:
    app = make_app("Tuva — MSSP ACO Dashboard")
    app.layout = build_layout()
    run(app)


if __name__ == "__main__":
    main()
