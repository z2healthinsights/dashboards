from tuva_dash.components import scaffold_layout


def build_layout():
    return scaffold_layout(
        title="Enterprise Analytics Semantic Layer",
        subtitle=(
            "Browser for the unified Tuva semantic layer — facts, dimensions, "
            "and bridge tables that back the rest of the Analytics Gallery."
        ),
        pages=[
            ("Model Overview", "List of fact and dimension tables with row counts and freshness."),
            ("Facts", "fact_admissions, fact_claims, fact_ed_visits, fact_encounters, "
                     "fact_member_months, fact_pharmacy_claims, fact_quality_measure, "
                     "fact_risk_factors, fact_risk_scores."),
            ("Dimensions", "dim_condition, dim_data_source, dim_date, dim_member, "
                           "dim_member_months, dim_encounter_group, dim_encounter_type, "
                           "dim_service_category."),
            ("Relationships", "Visualization of foreign-key relationships between facts and dimensions."),
        ],
        tuva_tables=[
            "core.fact_*",
            "core.dim_*",
            "quality_measures.*",
            "cms_hcc.*",
        ],
    )
