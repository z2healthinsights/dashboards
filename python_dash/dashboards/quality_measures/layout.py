from tuva_dash.components import scaffold_layout


def build_layout():
    return scaffold_layout(
        title="Quality Measures",
        subtitle="Measure rates, denominator and numerator detail across the Tuva quality library.",
        pages=[
            ("Measure Summary", "Performance against benchmarks for every active measure."),
            ("Measure Detail", "Drill into denominator/numerator/exclusions for a selected measure."),
            ("Trends", "Quarterly performance trends per measure."),
        ],
        tuva_tables=[
            "quality_measures.summary_long",
            "quality_measures.summary_wide",
            "core.dim_member",
        ],
    )
