from tuva_dash.components import scaffold_layout


def build_layout():
    return scaffold_layout(
        title="MSSP ACO Dashboard",
        subtitle="Medicare Shared Savings Program — quality, cost, and population metrics.",
        pages=[
            ("ACO Summary", "Attributed beneficiaries, benchmark vs actual, shared savings position."),
            ("Quality Measures", "MSSP measure performance against benchmarks."),
            ("Utilization", "Inpatient, ED, SNF, and post-acute use rates."),
            ("Risk Profile", "HCC risk scores and chronic condition prevalence."),
        ],
        tuva_tables=[
            "core.dim_member",
            "core.fact_member_months",
            "core.fact_claims",
            "quality_measures.summary_long",
            "cms_hcc.*",
            "chronic_conditions.tuva_chronic_conditions_long",
        ],
    )
