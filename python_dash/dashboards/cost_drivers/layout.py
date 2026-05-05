from tuva_dash.components import scaffold_layout


def build_layout():
    return scaffold_layout(
        title="Cost Drivers",
        subtitle="Pareto view of conditions, services, and members driving total spend.",
        pages=[
            ("Top Conditions", "Conditions ranked by attributable spend, contribution to PMPM."),
            ("Top Services", "Service categories and procedures by total paid amount."),
            ("Top Members", "High-cost member detail with concurrent risk scores."),
        ],
        tuva_tables=[
            "core.fact_claims",
            "chronic_conditions.tuva_chronic_conditions_long",
            "cost_and_utilization.*",
        ],
    )
