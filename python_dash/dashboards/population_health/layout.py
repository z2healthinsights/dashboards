from tuva_dash.components import scaffold_layout


def build_layout():
    return scaffold_layout(
        title="Population Health",
        subtitle="Member demographics, chronic-condition prevalence, and quality outcomes.",
        pages=[
            ("Demographics", "Age, sex, payer mix, geography of attributed members."),
            ("Chronic Conditions", "Prevalence and combinations of chronic conditions."),
            ("Quality", "Process and outcome quality measure rates."),
            ("Risk Stratification", "Members by risk tier and high-cost cohort."),
        ],
        tuva_tables=[
            "core.dim_member",
            "core.fact_member_months",
            "chronic_conditions.tuva_chronic_conditions_long",
            "quality_measures.summary_long",
            "cms_hcc.*",
        ],
    )
