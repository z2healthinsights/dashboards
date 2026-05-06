"""Entry point: `python -m dashboards.cost_and_utilization`."""

from tuva_dash.theme import make_app, run

from .layout import build_layout


def main() -> None:
    app = make_app("Tuva — Cost and Utilization")
    app.layout = build_layout()
    run(app)


if __name__ == "__main__":
    main()
